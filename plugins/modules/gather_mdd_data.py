#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2023 Cisco and/or its affiliates.
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see http://www.gnu.org/licenses/.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

ANSIBLE_METADATA = {'metadata_version': '1.1', 'status': ['preview'], 'supported_by': 'community'}

DOCUMENTATION = r"""
---
module: gather_mdd_data
short_description: finds all the correct mdd data for a given tag
description:
  - evalutates mdd data on tags and returns only correclty tagged data
  - this is to deal with the introduction of merged data files where config files
  - can now have multiple files defined in them, each starting with ---
author:
  - Kris Stickney (@kstickne)
  - Paul Pajerski (@ppajersk)
options:
    mdd_file_data:
        description:
        - The directory of the mdd data
        required: true
        type: list
        elements: dict
    tags:
        description:
        - The tags associated with a device
        required: true
        type: list
        elements: str
"""

EXAMPLES = r"""
- name: Gather the MDD Data
  gather_mdd_data:
    mdd_file_data: "{{ file_list_dict }}"
    tags: "{{ tags }}"
  register: result
"""

from ansible.module_utils.basic import AnsibleModule

debug = []

def gather(file_data, tags):
    """Gathers the data for a given tag"""
    result = []

    for file in file_data:
        all_tags = True
        for tag in tags:
          if tag not in file['mdd_tags']:
            all_tags = False
            break

        if 'all' in file['mdd_tags'] or all_tags:
            result.append(file['mdd_data'])

    return result


def main():
    """Runs the gather process"""

    arguments = dict(
        mdd_file_data=dict(required=True, type='list', elements='dict'),
        tags=dict(required=True, type='list', elements='str')
    )

    module = AnsibleModule(argument_spec=arguments, supports_check_mode=False)
    data = gather(module.params['mdd_file_data'], module.params['tags'])
    module.exit_json(changed=True, failed=False, mdd_data=data, debug=debug)


if __name__ == '__main__':
    main()
