#!/usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: berth_stack
short_description: Manage Docker stacks via Berth API
description:
    - Control Docker compose stacks through the Berth management API
    - Supports operations like restart, start, stop, pull, up, down
    - Streams operation output in real-time via WebSocket
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
    operation:
        description:
            - Operation to perform on the stack
        required: true
        choices: ['up', 'down', 'start', 'stop', 'restart', 'pull']
        type: str
    options:
        description:
            - Additional docker-compose options (e.g., ['-d', '--build'])
        required: false
        type: list
        elements: str
        default: []
    services:
        description:
            - Specific services to operate on (empty = all services)
        required: false
        type: list
        elements: str
        default: []
    validate_certs:
        description:
            - Verify SSL certificates
        required: false
        type: bool
        default: true
    timeout:
        description:
            - Timeout for operation completion in seconds
        required: false
        type: int
        default: 600
requirements:
    - python >= 3.6
    - websocket-client
notes:
    - This module requires network access to your Berth server
    - API keys can be created in the Berth web UI under API Keys
    - Operations are streamed in real-time and may take some time
'''

EXAMPLES = r'''
- name: Restart a specific container in a stack
  berth_stack:
    berth_url: "https://berth.example.com"
    api_key: "{{ berth_api_key }}"
    server_id: "1"
    stack_name: "myapp"
    operation: "restart"
    services:
      - "web"

- name: Pull latest images and recreate stack
  berth_stack:
    berth_url: "https://berth.example.com"
    api_key: "{{ berth_api_key }}"
    server_id: "1"
    stack_name: "myapp"
    operation: "up"
    options:
      - "-d"
      - "--pull"
      - "--force-recreate"

- name: Stop entire stack
  berth_stack:
    berth_url: "https://berth.example.com"
    api_key: "{{ berth_api_key }}"
    server_id: "1"
    stack_name: "myapp"
    operation: "stop"

- name: Start services with insecure SSL
  berth_stack:
    berth_url: "https://berth.local"
    api_key: "{{ berth_api_key }}"
    server_id: "1"
    stack_name: "myapp"
    operation: "start"
    validate_certs: false

- name: Pull images for specific services
  berth_stack:
    berth_url: "https://berth.example.com"
    api_key: "{{ berth_api_key }}"
    server_id: "1"
    stack_name: "myapp"
    operation: "pull"
    services:
      - "web"
      - "db"
'''

RETURN = r'''
operation_id:
    description: ID of the operation that was started
    type: str
    returned: always
    sample: "abc123-def456-ghi789"
changed:
    description: Whether the operation was executed
    type: bool
    returned: always
    sample: true
message:
    description: Human-readable message about the result
    type: str
    returned: always
    sample: "Successfully completed restart operation on stack myapp"
exit_code:
    description: Exit code from the docker-compose operation
    type: int
    returned: always
    sample: 0
output:
    description: Output from the operation (stdout/stderr)
    type: list
    elements: str
    returned: always
    sample: ["Starting container web...", "Container web started"]
'''

import json
import ssl
import time
from urllib.parse import urlparse
from ansible.module_utils.basic import AnsibleModule

try:
    import websocket
    HAS_WEBSOCKET = True
except ImportError:
    HAS_WEBSOCKET = False

try:
    from urllib.request import Request, urlopen
    from urllib.error import HTTPError, URLError
except ImportError:
    from urllib2 import Request, urlopen, HTTPError, URLError


class BerthStackOperator:
    """Handles Berth stack operations via REST API and WebSocket streaming"""

    def __init__(self, module):
        self.module = module
        self.berth_url = module.params['berth_url'].rstrip('/')
        self.api_key = module.params['api_key']
        self.server_id = module.params['server_id']
        self.stack_name = module.params['stack_name']
        self.operation = module.params['operation']
        self.options = module.params['options']
        self.services = module.params['services']
        self.validate_certs = module.params['validate_certs']
        self.timeout = module.params['timeout']

        self.output_lines = []
        self.success = None
        self.exit_code = None
        self.operation_id = None

    def start_operation(self):
        """Start the operation via REST API"""
        url = f"{self.berth_url}/api/v1/servers/{self.server_id}/stacks/{self.stack_name}/operations"

        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }

        payload = {
            'command': self.operation,
            'options': self.options,
            'services': self.services
        }

        data = json.dumps(payload).encode('utf-8')
        request = Request(url, data=data, headers=headers)

        try:
            if not self.validate_certs:
                context = ssl._create_unverified_context()
                response = urlopen(request, timeout=30, context=context)
            else:
                response = urlopen(request, timeout=30)

            result = json.loads(response.read().decode('utf-8'))
            self.operation_id = result.get('operationId')

            if not self.operation_id:
                self.module.fail_json(msg="No operation ID returned from server")

            return self.operation_id

        except HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ''
            self.module.fail_json(
                msg=f"Failed to start operation: HTTP {e.code}",
                details=error_body
            )
        except URLError as e:
            self.module.fail_json(msg=f"Failed to connect to Berth server: {str(e)}")
        except Exception as e:
            self.module.fail_json(msg=f"Unexpected error starting operation: {str(e)}")

    def stream_operation(self):
        """Stream operation output via WebSocket"""
        parsed_url = urlparse(self.berth_url)
        ws_scheme = 'wss' if parsed_url.scheme == 'https' else 'ws'
        ws_url = f"{ws_scheme}://{parsed_url.netloc}/ws/api/servers/{self.server_id}/stacks/{self.stack_name}/operations/{self.operation_id}"

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

            start_time = time.time()

            while True:
                # Check timeout
                if time.time() - start_time > self.timeout:
                    ws.close()
                    self.module.fail_json(
                        msg=f"Operation timed out after {self.timeout} seconds",
                        operation_id=self.operation_id,
                        output=self.output_lines
                    )

                try:
                    message = ws.recv()
                    if not message:
                        continue

                    msg_data = json.loads(message)
                    msg_type = msg_data.get('type', '')

                    if msg_type in ['stdout', 'stderr']:
                        data = msg_data.get('data', '')
                        if data:
                            self.output_lines.append(data.rstrip('\n'))

                    elif msg_type == 'progress':
                        data = msg_data.get('data', '')
                        if data:
                            timestamp = msg_data.get('timestamp', '')
                            self.output_lines.append(f"[{timestamp}] {data}")

                    elif msg_type == 'complete':
                        self.success = msg_data.get('success', False)
                        self.exit_code = msg_data.get('exitCode', 1 if not self.success else 0)
                        ws.close()
                        return

                    elif msg_type == 'error':
                        error_msg = msg_data.get('data', 'Unknown error')
                        ws.close()
                        self.module.fail_json(
                            msg=f"Operation error: {error_msg}",
                            operation_id=self.operation_id,
                            output=self.output_lines
                        )

                except websocket.WebSocketTimeoutException:
                    continue
                except websocket.WebSocketException as e:
                    ws.close()
                    self.module.fail_json(
                        msg=f"WebSocket error: {str(e)}",
                        operation_id=self.operation_id,
                        output=self.output_lines
                    )

        except Exception as e:
            self.module.fail_json(
                msg=f"Failed to connect to WebSocket: {str(e)}",
                operation_id=self.operation_id
            )

    def execute(self):
        """Execute the full operation: start and stream"""
        # Start the operation
        self.start_operation()

        # Stream the output
        self.stream_operation()

        # Build result message
        services_str = f" on services {', '.join(self.services)}" if self.services else ""
        message = f"Successfully completed {self.operation} operation on stack {self.stack_name}{services_str}"

        if not self.success:
            message = f"Failed {self.operation} operation on stack {self.stack_name}{services_str}"

        return {
            'changed': True,
            'operation_id': self.operation_id,
            'message': message,
            'exit_code': self.exit_code,
            'output': self.output_lines,
            'failed': not self.success
        }


def main():
    module = AnsibleModule(
        argument_spec=dict(
            berth_url=dict(type='str', required=True),
            api_key=dict(type='str', required=True, no_log=True),
            server_id=dict(type='str', required=True),
            stack_name=dict(type='str', required=True),
            operation=dict(
                type='str',
                required=True,
                choices=['up', 'down', 'start', 'stop', 'restart', 'pull']
            ),
            options=dict(type='list', elements='str', default=[]),
            services=dict(type='list', elements='str', default=[]),
            validate_certs=dict(type='bool', default=True),
            timeout=dict(type='int', default=600)
        ),
        supports_check_mode=False
    )

    if not HAS_WEBSOCKET:
        module.fail_json(msg='The websocket-client Python module is required. Install with: pip install websocket-client')

    operator = BerthStackOperator(module)
    result = operator.execute()

    if result.get('failed'):
        module.fail_json(**result)
    else:
        module.exit_json(**result)


if __name__ == '__main__':
    main()
