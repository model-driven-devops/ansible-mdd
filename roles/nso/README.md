# cisco.mdd.nso

Model-Driven Devops NSO Role

Requirements
------------

* cisco.nso collection

# Role Variables

nso_host_group: 'nso'
nso_url: "http://{{ nso_host }}:8080/jsonrpc"
nso_rest_url: "http://{{ nso_host }}:8080"
nso_package_src: "{{ lookup('env', 'PWD') }}/packages"
nso_installer_name: "nso-5.5.3.linux.x86_64.signed.bin"
nso_install_dir: /opt/ncs/current
nso_run_dir: /var/opt/ncs
nso_etc_dir: /etc/ncs
nso_tmp_dir: /tmp/nso
nso_upload_dir: /tmp/nso
nso_java_opts: "-Xmx2G -Xms1G"
nso_username: "{{ lookup('env', 'NSO_USERNAME') | default ('ubuntu', true) }}"
nso_password: "{{ lookup('env', 'NSO_PASSWORD') | default ('admin', true) }}"
nso_auth_groups:
  default:
    remote_name: "admin"
    remote_password: "admin"
nso_default_ned: cisco-ios-cli-6.77
nso_ned_dict:
  ios: "cisco-ios-cli-6.77"
nso_package_repos:
  - name: mdd
    repo: https://github.com/model-driven-devops/nso-oc-services.git
    service_list:
      - mdd

# Dependencies


* cisco.nso collection


# Playbooks

- These operations act on the NSO host itself
- The inventory should contain the NSO hosts in an `nso` group
- `--limit` can be used to limit operation to specific NSO hosts

## NSO Server Operations

### `ciscops.mdd.nso_install`

- Install NSO on host

### Requirements
- nso and neds packages in `packages` directory

### `ciscops.mdd.nso_update_packages`

- Update the MDD packages on the NSO hosts

target: The group of nso hosts

## NSO Device Operations

- These operations act on the device through the NSO host
- The inventory should include the devices in a `network` group
- `--limit` can be used to limit operation to specific devices

#### `ciscops.mdd.nso_update_oc`

    - Push OC data to the host through NSO

Example:
```
ansible-playbook ciscops.mdd.nso_update_oc
```

Extra Vars:
- `dry_run` (optional): Whether to do a dry run or a commit (default: true)

#### `ciscops.mdd.nso_sync_from`

- Run sync_from for device

Example:
```
ansible-playbook nso_sync_from
```

#### `ciscops.mdd.nso_sync_to`

- Run sync_to for device

Example:
```
ansible-playbook nso_sync_to
```

#### `ciscops.mdd.nso_check_sync`

- Check to make sure that the device is in sync with NSO
- playbook fails if device is out-of-sync

Example:
```
ansible-playbook nso_sync_to
```

#### `ciscops.mdd.nso_rollback_facts`

- Summary of rollbacks

Extra Vars:
- `rollback_id` (optional): List information for specific Rollback ID

#### `ciscops.mdd.nso_rollback`

- Rollback to specific Rollback ID

Extra Vars:
- `rollback_id` (required): Rollback ID

#### `ciscops.mdd.nso_save_rollback`

- Save a file with the current Rollback ID

Extra Vars:
- `rollback_file` (optional): The file containing the Rollback ID

#### `ciscops.mdd.nso_load_rollback`

- Load a file with a Rollback ID and rollback to that ID

Extra Vars:
- `rollback_file` (optional): The file containing the Rollback ID

### OpenConfig Data Operation

#### `ciscops.mdd.show_oc`

  - Show OC values for host

#### `ciscops.mdd.validate_data`

  - Validate OC data for host


#### `ciscops.mdd.nso_generate_oc`

  - Generate OC data from NSO

Example Playbook
----------------

Including an example of how to use your role (for instance, with variables passed in as parameters) is always nice for users too:

    - hosts: servers
      roles:
         - { role: username.rolename, x: 42 }

License
-------

BSD

Author Information
------------------

An optional section for the role authors to include contact information, or a website (HTML is not allowed).
