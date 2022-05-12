ciscops.mdd.oc
=========

A set of tasks that constructs a complete OC representation from a collection of fragments organized hierarchically.  More data that is organized closer to the
device overrides data that is more generic.

Requirements
------------

See the requirements files for the ciscops.mdd collection

Role Variables
--------------

- `oc_data_root`: The root of the OC data directory hierarchy
- `oc_group_list`: The group list with which to construct the
directory hierarchy.
- `oc_file_patterns`: The list of file patterns to look for


A description of the settable variables for this role should go here, including any variables that are in defaults/main.yml, vars/main.yml, and any variables that can/should be set via parameters to the role. Any variables that are read from other roles and/or the global scope (ie. hostvars, group vars, etc.) should be mentioned here as well.

Dependencies
------------

A list of other roles hosted on Galaxy should go here, plus any details in regards to parameters that may need to be set for other roles, or variables that are used from other roles.

Example Playbook
----------------

Including an example of how to use your role (for instance, with variables passed in as parameters) is always nice for users too:

    - hosts: network
      connection: local
      gather_facts: no
      roles:
        - ciscops.mdd.oc
      tasks:
        - debug:
            var: mdd_data

License
-------

BSD

Author Information
------------------

An optional section for the role authors to include contact information, or a website (HTML is not allowed).
