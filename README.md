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
        "Operation ID: 7f88a7ec-7041-4a48-9890-32e03da59330",
        "Exit Code: 0",
        "Status: Successfully completed restart operation on stack my-application-stack",
        "",
        "=== Output ==="
    ]
}

TASK [Display operation output] *******************************************************************************************************************************************************
ok: [localhost] => {
    "msg": [
        " Container my-app-redis  Restarting",
        " Container my-application-stack-api-1  Restarting",
        " Container my-app-web  Restarting",
        " Container my-app-db  Restarting",
        " Container my-app-db  Started",
        " Container my-app-web  Started",
        " Container my-app-redis  Started",
        " Container my-application-stack-api-1  Started"
    ]
}

TASK [Verify operation succeeded] *****************************************************************************************************************************************************
ok: [localhost] => {
    "changed": false,
    "msg": "✓ Test passed! Module is working correctly."
}

PLAY RECAP ****************************************************************************************************************************************************************************
localhost                  : ok=6    changed=1    unreachable=0    failed=0    skipped=0    rescued=0    ignored=0
```