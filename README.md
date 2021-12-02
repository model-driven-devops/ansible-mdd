# Cisco Model Driven Devops Ansible Collection

## Dependancies
### Environmnet Variables

- `NETBOX_API`
- `NETBOX_TOKEN`

## Playbooks

### `ciscops.mdd.nso_update_oc`

    - Update in NSO

Example:
```
ansible-playbook ciscops.mdd.nso_update_oc
```

Extra Vars:
- `dry_run` (optional): Whether to do a dry run or a commit (default: true)

### `ciscops.mdd.show_oc`

    - Show OC values for host

### `ciscops.mdd.run_check_list`

    - Run the list of checks defined in `check_list`

#### Required Data Structures

- `check_list`: List of checks to run
- `check_table`: Dictionary defining the checks

> Note: See default values in roles/check/defaults/main.yml

### `ciscops.mdd.nso_check_sync`

    - Check to see if NSO is in sync with the devices

> Note: Failure means that the device is out of sync

### `ciscops.mdd.update_netbox_from_nso`

    - Update Netbox from NSO

Example:
```
ansible-playbook ciscops.mdd.update_netbox_from_nso
```

### `ciscops.mdd.netbox_init`

    - Initialize Netbox

Example:
```
ansible-playbook ciscops.mdd.netbox_init
```

> Note: Netbox modules to not work with Ansible <4, so the entire path will need to be specified when running with Ansible <3

### `ciscops.mdd.nso_install`

- Install NSO on host

#### Requirements
- nso and neds in packages directory

### `ciscops.mdd.nso_update_packages`

- Update the MDD packages on the NSO hosts

target: The group of nso hosts

### `ciscops.mdd.netbox_init`

- Initialize Netbox

ansible-playbook ciscops.mdd.netbox_init

### `ciscops.mdd.cml_update_netbox`

- Add hosts from CML into netbox

Inventory Source: CML

Example:
```
ansible-playbook cml_update_netbox
```

### `ciscops.mdd.nso_update_netbox`

- Update Netbox devices from NSO

Example:
```
ansible-playbook nso_update_netbox
```

### `ciscops.mdd.nso_init`

- Initialize NSO

Example:
```
ansible-playbook nso_init
```

### `ciscops.mdd.nso_update_device`

- Update NSO devices from inventory source

Example:
```
ansible-playbook nso_update_netbox
```

### `ciscops.mdd.nso_sync_from`

- Run sync_from for device

Example:
```
ansible-playbook nso_sync_from
```

### `ciscops.mdd.nso_rollback_facts`

- Summary of rollbacks

Extra Vars:
- `rollback_id` (optional): List information for specific Rollback ID

### `ciscops.mdd.nso_rollback`

- Rollback to specific Rollback ID

Extra Vars:
- `rollback_id` (required): Rollback ID

### `ciscops.mdd.nso_save_rollback`

- Save a file with the current Rollback ID

Extra Vars:
- `rollback_file` (optional): The file containing the Rollback ID

### `ciscops.mdd.nso_load_rollback`

- Load a file with a Rollback ID and rollback to that ID

Extra Vars:
- `rollback_file` (optional): The file containing the Rollback ID