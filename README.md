# Berth Ansible Module

### See ./tests/ for example usage

### ./tests/test-playbook.yml example

```
$ tests git:(main) ✗ ansible-playbook test-playbook.yml

PLAY [Test Berth Ansible Module] ******************************************************************************************************************************************************

TASK [Validate required environment variables] ****************************************************************************************************************************************
ok: [localhost] => {
    "changed": false,
    "msg": "All assertions passed"
}

TASK [Display test configuration] *****************************************************************************************************************************************************
ok: [localhost] => {
    "msg": [
        "Berth URL: https://localhost:4443",
        "Server ID: 1",
        "Stack Name: my-application-stack",
        "Validate Certs: false"
    ]
}

TASK [Test operation - Restart stack] *************************************************************************************************************************************************
changed: [localhost]

TASK [Display operation result] *******************************************************************************************************************************************************
ok: [localhost] => {
    "msg": [
        "=== Operation Completed ===",
        "Operation ID: 283a4f6e-3f07-4332-ac81-0b7165601332",
        "Exit Code: 0",
        "Status: Successfully completed restart operation on stack my-application-stack",
        "",
        "=== Output ==="
    ]
}

TASK [Display operation output] *******************************************************************************************************************************************************
ok: [localhost] => {
    "msg": [
        " Container my-app-web  Restarting",
        " Container my-application-stack-api-1  Restarting",
        " Container my-app-db  Restarting",
        " Container my-app-redis  Restarting",
        " Container my-app-web  Started",
        " Container my-app-db  Started",
        " Container my-app-redis  Started",
        " Container my-application-stack-api-1  Started"
    ]
}

TASK [Verify operation succeeded] *****************************************************************************************************************************************************
ok: [localhost] => {
    "changed": false,
    "msg": "✓ Test passed! Module is working correctly."
}

TASK [Test exec - List files in container] ********************************************************************************************************************************************
ok: [localhost]

TASK [Display exec result] ************************************************************************************************************************************************************
ok: [localhost] => {
    "msg": [
        "=== Exec Command Completed ===",
        "Exit Code: 0",
        "Output:",
        "total 18\r\ndrwxr-xr-x    2 root     root             2 Oct 12 10:50 .\r\ndrwxr-xr-x    1 root     root             4 Oct 12 10:50 ..\r\n"
    ]
}

TASK [Test exec - Get environment variables] ******************************************************************************************************************************************
ok: [localhost]

TASK [Display environment result] *****************************************************************************************************************************************************
ok: [localhost] => {
    "msg": [
        "=== Environment Variables ===",
        "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin\r\n"
    ]
}

TASK [Verify exec commands succeeded] *************************************************************************************************************************************************
ok: [localhost] => {
    "changed": false,
    "msg": "✓ Exec tests passed! Command execution is working correctly."
}

PLAY RECAP ****************************************************************************************************************************************************************************
localhost                  : ok=11   changed=1    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
```