#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
from ansible.module_utils.basic import AnsibleModule
from urllib.parse import urlparse
import re
import time
import ssl
import json
__metaclass__ = type

DOCUMENTATION = r'''
---
module: berth_exec
short_description: Execute commands in Docker containers via Berth terminal
description:
    - Execute commands non-interactively in Docker containers through the Berth terminal API
    - Uses the same infrastructure as interactive terminals
    - Captures command output and exit code
version_added: "1.0.0"
author:
    - "Berth Contributors"
options:
    berth_url:
        description:
            - URL of the Berth server (e.g., https://berth.example.com)
        required: true
        type: str
    api_key:
        description:
            - Berth API key for authentication (starts with brth_)
            - Can also be set via BERTH_API_KEY environment variable
        required: true
        type: str
        no_log: true
    server_id:
        description:
            - ID of the server in Berth
        required: true
        type: str
    stack_name:
        description:
            - Name of the Docker compose stack
        required: true
        type: str
    service_name:
        description:
            - Name of the service/container
        required: true
        type: str
    container_name:
        description:
            - Specific container name (optional, defaults to service)
        required: false
        type: str
        default: ""
    command:
        description:
            - Command to execute in the container
        required: true
        type: str
    validate_certs:
        description:
            - Verify SSL certificates
        required: false
        type: bool
        default: true
    timeout:
        description:
            - Timeout for command execution in seconds
        required: false
        type: int
        default: 30
requirements:
    - python >= 3.6
    - websocket-client
notes:
    - This module requires network access to your Berth server
    - API keys can be created in the Berth web UI under API Keys
    - Commands are executed non-interactively
'''

EXAMPLES = r'''
- name: List files in a container
  berth_exec:
    berth_url: "https://berth.example.com"
    api_key: "{{ berth_api_key }}"
    server_id: "1"
    stack_name: "myapp"
    service_name: "web"
    command: "ls -la /app"

- name: Check environment variables
  berth_exec:
    berth_url: "https://berth.example.com"
    api_key: "{{ berth_api_key }}"
    server_id: "1"
    stack_name: "myapp"
    service_name: "api"
    command: "env"

- name: Execute command with insecure SSL
  berth_exec:
    berth_url: "https://berth.local"
    api_key: "{{ berth_api_key }}"
    server_id: "1"
    stack_name: "myapp"
    service_name: "web"
    command: "cat /etc/hostname"
    validate_certs: false

- name: Run command in specific container
  berth_exec:
    berth_url: "https://berth.example.com"
    api_key: "{{ berth_api_key }}"
    server_id: "1"
    stack_name: "myapp"
    service_name: "web"
    container_name: "myapp-web-1"
    command: "ps aux"
'''

RETURN = r'''
changed:
    description: Always false as this is a read-only operation
    type: bool
    returned: always
    sample: false
exit_code:
    description: Exit code from the executed command
    type: int
    returned: always
    sample: 0
stdout:
    description: Standard output from the command
    type: str
    returned: always
    sample: "total 8\\ndrwxr-xr-x 2 root root 4096 Oct 12 10:50 ."
stderr:
    description: Standard error from the command (if any)
    type: str
    returned: always
    sample: ""
output:
    description: Combined output (stdout + stderr)
    type: list
    elements: str
    returned: always
    sample: ["total 8", "drwxr-xr-x 2 root root 4096 Oct 12 10:50 ."]
'''


try:
    import websocket
    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False


class BerthExecOperator:
    """Handles command execution in containers via Berth terminal WebSocket"""

    # Regex to strip ANSI escape codes
    ANSI_ESCAPE_REGEX = re.compile(
        r'\x1b\[[0-9;?]*[a-zA-Z]|\x1b\][^\x07]*\x07')

    def __init__(self, module):
        self.module = module
        self.berth_url = module.params['berth_url'].rstrip('/')
        self.api_key = module.params['api_key']
        self.server_id = module.params['server_id']
        self.stack_name = module.params['stack_name']
        self.service_name = module.params['service_name']
        self.container_name = module.params['container_name']
        self.command = module.params['command']
        self.validate_certs = module.params['validate_certs']
        self.timeout = module.params['timeout']

        self.session_id = None
        self.output_lines = []
        self.exit_code = None
        self.command_sent = False

    def strip_ansi_codes(self, text):
        """Remove ANSI escape sequences from text"""
        return self.ANSI_ESCAPE_REGEX.sub('', text)

    def should_skip_output(self, output):
        """Determine if output should be filtered out"""
        if not self.command_sent:
            # Skip initial prompt
            if output.startswith('/app #'):
                return True
        else:

            if self.command in output or \
               output.startswith('/app #') or \
               output.startswith('exit'):
                return True
        return False

    def execute_command(self):
        """Execute command via terminal WebSocket"""
        parsed_url = urlparse(self.berth_url)
        ws_scheme = 'wss' if parsed_url.scheme == 'https' else 'ws'
        ws_url = f"{ws_scheme}://{parsed_url.netloc}/ws/api/servers/{self.server_id}/terminal"

        headers = {
            'Authorization': f'Bearer {self.api_key}'
        }

        sslopt = None
        if ws_scheme == 'wss' and not self.validate_certs:
            sslopt = {"cert_reqs": ssl.CERT_NONE}

        try:
            ws = websocket.create_connection(
                ws_url,
                header=[f"{k}: {v}" for k, v in headers.items()],
                sslopt=sslopt,
                timeout=self.timeout
            )

            start_msg = {
                'type': 'terminal_start',
                'stack_name': self.stack_name,
                'service_name': self.service_name,
                'container_name': self.container_name,
                'cols': 80,
                'rows': 24
            }
            ws.send(json.dumps(start_msg))

            start_time = time.time()
            session_ready = False

            while True:

                if time.time() - start_time > self.timeout:
                    ws.close()
                    self.module.fail_json(
                        msg=f"Command execution timed out after {
                            self.timeout} seconds",
                        output=self.output_lines)

                try:
                    message = ws.recv()
                    if not message:
                        continue

                    msg_data = json.loads(message)
                    msg_type = msg_data.get('type', '')

                    if msg_type == 'success':

                        self.session_id = msg_data.get('session_id')
                        session_ready = True

                        time.sleep(0.2)

                        input_msg = {
                            'type': 'terminal_input',
                            'session_id': self.session_id,
                            'input': list((self.command + '\n').encode())
                        }
                        ws.send(json.dumps(input_msg))
                        self.command_sent = True

                        time.sleep(0.1)

                        exit_msg = {
                            'type': 'terminal_input',
                            'session_id': self.session_id,
                            'input': list('exit\n'.encode())
                        }
                        ws.send(json.dumps(exit_msg))

                    elif msg_type == 'terminal_output':
                        if session_ready:

                            import base64
                            output_bytes = msg_data.get('output', '')
                            if output_bytes:
                                decoded = base64.b64decode(output_bytes).decode(
                                    'utf-8', errors='replace')

                                cleaned = self.strip_ansi_codes(decoded)

                                if cleaned and not self.should_skip_output(
                                        cleaned):
                                    self.output_lines.append(cleaned)

                    elif msg_type == 'terminal_close':

                        self.exit_code = msg_data.get('exit_code', 0)
                        ws.close()

                        time.sleep(0.1)
                        return

                    elif msg_type == 'error':
                        error_msg = msg_data.get('error', 'Unknown error')
                        context = msg_data.get('context', '')
                        full_error = f"{error_msg}: {context}" if context else error_msg
                        ws.close()
                        self.module.fail_json(
                            msg=f"Terminal error: {full_error}",
                            output=self.output_lines
                        )

                except websocket.WebSocketTimeoutException:
                    continue
                except websocket.WebSocketException as e:
                    ws.close()
                    self.module.fail_json(
                        msg=f"WebSocket error: {str(e)}",
                        output=self.output_lines
                    )

        except Exception as e:
            self.module.fail_json(
                msg=f"Failed to connect to terminal WebSocket: {str(e)}"
            )

    def execute(self):
        """Execute the command and return results"""
        self.execute_command()

        stdout = ''.join(self.output_lines)

        return {
            'changed': False,
            'exit_code': self.exit_code if self.exit_code is not None else 0,
            'stdout': stdout,
            'stderr': '',
            'output': self.output_lines,
            'failed': self.exit_code != 0 if self.exit_code is not None else False}


def main():
    module = AnsibleModule(
        argument_spec=dict(
            berth_url=dict(type='str', required=True),
            api_key=dict(type='str', required=True, no_log=True),
            server_id=dict(type='str', required=True),
            stack_name=dict(type='str', required=True),
            service_name=dict(type='str', required=True),
            container_name=dict(type='str', default=''),
            command=dict(type='str', required=True),
            validate_certs=dict(type='bool', default=True),
            timeout=dict(type='int', default=30)
        ),
        supports_check_mode=False
    )

    if not HAS_WEBSOCKET:
        module.fail_json(
            msg='The websocket-client Python module is required. Install with: pip install websocket-client')

    operator = BerthExecOperator(module)
    result = operator.execute()

    if result.get('failed'):
        module.fail_json(**result)
    else:
        module.exit_json(**result)


if __name__ == '__main__':
    main()
