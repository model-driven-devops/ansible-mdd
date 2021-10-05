# Ansible Collection - ciscops.mdd

## Dependancies
### Environmnet Variables
- `NETBOX_API`
- `NETBOX_TOKEN`

## Playbooks
`ciscops.mdd.nso_[update,show]_oc`:

    - Update/Show OC in NSO

Example:
```
ansible-playbook -i inventory/netbox.yml ciscops.mdd.nso_update_oc
ansible-playbook -i inventory/netbox.yml ciscops.mdd.nso_show_oc
```
Extra Vars:
- dry_run: Whether to do a dry run or a commit (default: true)
- models: The openconfig models to push
    - system
    - interfaces

`ciscops.mdd.nso_check_sync`:

    - Check to see if NSO is in sync with the devices

> Note: Failure means that the device is out of sync

`ciscops.mdd.update_netbox_from_nso`:

    - Update Netbox from NSO

Example:
```
ansible-playbook -i inventory/netbox.yml ciscops.mdd.update_netbox_from_nso
```


`ciscops.mdd.netbox_init`:

    - Initialize Netbox

Example:
```
ansible-playbook ciscops.mdd.netbox_init
```

> Note: Netbox modules to not work with Ansible <4, so the entire path will need to be specified when running with Ansible <3