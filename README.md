# Ansible Collection - ciscops.mdd

## Playbooks
`ciscops.mdd.update_oc`:
    - Starts NSO
    - Updates OC packages

Example:
```
ansible-playbook -i inventory/netbox.yml ciscops.mdd.update_oc
```
Extra Vars:
- dry_run: Whether to do a dry run or a commit (default: true)
- models: The openconfig models to push
    - system
    - interfaces

`ciscops.mdd.nso_check_sync`:
    - Check to see if NSO is in sync with the devices

> Note: Failure means that the device is out of sync

