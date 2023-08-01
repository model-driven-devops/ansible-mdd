#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2017 Cisco and/or its affiliates.
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
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.
#

from __future__ import (absolute_import, division, print_function)

__metaclass__ = type

ANSIBLE_METADATA = {'metadata_version': '1.1', 'status': ['preview'], 'supported_by': 'community'}
DOCUMENTATION = r"""
---
module: mdd_combine
short_description: Generate host-specific MDD Data
description:
  - Generate host-specific MDD Data
author:
  - Steven Mosher (@stmosher)
requirements:
  - copy
  - jinja2
  - os
  - re
  - yaml
version_added: '0.1.0'
options:
    mdd_root:
        description: The root directory of the MDD Data
        required: true
        type: str
    host:
        description: The host for which the data is to be generated
        required: true
        type: str
    filespec_list:
        description: List of filespecs to identify configuration file, e.g. "[oc-*.yml]"
        required: true
        type: list
        elements: str
    tags:
        description: The tags for which to made the MDD Data
        required: false
        type: list
        elements: str
    list_key_map:
        description: The key list dict for the context-aware sorting
        required: false
        type: dict
    default_weight:
        description: The default weight for data that does not specify
        default: 1000
        type: int
    hostvars:
        description: hostvars to be used in jinja templating
        required: true
        type: dict
"""

RETURN = r'''
mdd_data:
    description: The host-specific configuration data
    returned: success
    type: dict
    sample:
metadata:
    description: The metadata for the generated configuration data
    returned: changed
    type: dict
    sample:
'''

EXAMPLES = r"""
- name: Generate Configurations
  hosts: network
  connection: local
  gather_facts: no
  tasks:
    - name: Generate the MDD Data.
      mdd_combine:
        mdd_data_root: "{{ mdd_data_root }}"
        host: "{{ inventory_hostname }}"
        tags: "{{ tags }}"
        filespec_list: "{{ filespec_list }}"
        hostvars: "{{ hostvars[inventory_hostname] }}"
      register: mdd_output

    - debug:
        var: mdd_output

    - name: Combine the MDD Data
      set_fact:
        mdd_data: "{{ mdd_output.mdd_data }}"
      when: mdd_output is defined
"""

import copy
import os
import re
import traceback
import fnmatch
from jinja2 import Environment, FileSystemLoader
from ansible.module_utils.basic import AnsibleModule, missing_required_lib

YAML_IMPORT_ERROR = 0

try:
    import yaml
except ImportError:
    HAS_YAML = False
    YAML_IMPORT_ERROR = traceback.format_exc()
else:
    HAS_YAML = True

default_list_key_map = {
    'mdd:openconfig:openconfig-acl:acl:openconfig-acl:acl-sets:openconfig-acl:acl-set$': 'openconfig-acl:name',
    'mdd:openconfig:openconfig-interfaces:interfaces:openconfig-interfaces:interface$': 'openconfig-interfaces:name',
    'mdd:openconfig:openconfig-network-instance:network-instances:openconfig-network-instance:network-instance$': 'openconfig-network-instance:name',
    'mdd:openconfig:openconfig-network-instance:network-instances:openconfig-network-instance:network-instance:[a-zA-Z0-9_-]+:openconfig-network-instance:protocols:openconfig-network-instance:protocol$': 'openconfig-network-instance:name',  # noqa: E501
    'mdd:openconfig:openconfig-network-instance:network-instances:openconfig-network-instance:network-instance:[a-zA-Z0-9_-]+:openconfig-network-instance:protocols:openconfig-network-instance:protocol:[a-zA-Z0-9_-]+:openconfig-network-instance:bgp:openconfig-network-instance:global:openconfig-network-instance:afi-safis:openconfig-network-instance:afi-safi$': 'openconfig-network-instance:afi-safi-name',  # noqa: E501
    'mdd:openconfig:openconfig-network-instance:network-instances:openconfig-network-instance:network-instance:[a-zA-Z0-9_-]+:openconfig-network-instance:protocols:openconfig-network-instance:protocol:[a-zA-Z0-9_-]+:openconfig-network-instance:ospfv2:openconfig-network-instance:areas:openconfig-network-instance:area$': 'openconfig-network-instance:identifier',  # noqa: E501
    'mdd:openconfig:openconfig-network-instance:network-instances:openconfig-network-instance:network-instance:[a-zA-Z0-9_-]+:openconfig-network-instance:vlans:openconfig-network-instance:vlan$': 'openconfig-network-instance:vlan-id',  # noqa: E501
    'mdd:openconfig:openconfig-routing-policy:routing-policy:openconfig-routing-policy:defined-sets:openconfig-bgp-policy:bgp-defined-sets:openconfig-bgp-policy:ext-community-sets:openconfig-bgp-policy:ext-community-set$': 'openconfig-bgp-policy:ext-community-set-name',  # noqa: E501
    'mdd:openconfig:openconfig-routing-policy:routing-policy:openconfig-routing-policy:defined-sets:openconfig-routing-policy:filespec_list-sets:openconfig-routing-policy:filespec_list-set$': 'openconfig-routing-policy:name',  # noqa: E501
    'mdd:openconfig:openconfig-routing-policy:routing-policy:openconfig-routing-policy:defined-sets:openconfig-routing-policy:tag-sets:openconfig-routing-policy:tag-set$': 'openconfig-routing-policy:name',  # noqa: E501v
    'mdd:openconfig:openconfig-routing-policy:routing-policy:openconfig-routing-policy:policy-definitions:openconfig-routing-policy:policy-definition$': 'openconfig-routing-policy:name',  # noqa: E501
    'mdd:openconfig:openconfig-system:system:openconfig-system-ext:services:openconfig-system-ext:key-chains:openconfig-system-ext:key-chain$': 'openconfig-system-ext:name',  # noqa: E501
    'mdd:openconfig:openconfig-system:system:openconfig-system-ext:services:openconfig-system-ext:nat:openconfig-system-ext:inside:openconfig-system-ext:source:openconfig-system-ext:local-addresses-access-lists:openconfig-system-ext:local-addresses-access-list$': 'openconfig-system-ext:local-addresses-access-list-name',  # noqa: E501
    'mdd:openconfig:openconfig-system:system:openconfig-system-ext:services:openconfig-system-ext:nat:openconfig-system-ext:pools:openconfig-system-ext:pool$': 'openconfig-system-ext:name',  # noqa: E501
    'mdd:openconfig:openconfig-system:system:openconfig-system-ext:services:openconfig-system-ext:object-tracking:openconfig-system-ext:object-track$': 'openconfig-system-ext:id',  # noqa: E501
    'mdd:openconfig:openconfig-system:system:openconfig-system:logging:openconfig-system:remote-servers:openconfig-system:remote-server$': 'openconfig-system:host'  # noqa: E501
}


def get_merge_key(path, list_key_map):
    for k, v in list_key_map.items():
        if re.search(k, path):
            return v
    return None


def merge_dicts(all_configs, module):
    def _merge(result_cfgs, v, path=None, filepath=None, hierarchy_level=None, playbook_tags=None, weight=None):
        path = path or []
        for k, v in v.items():
            if isinstance(v, dict):
                if k in result_cfgs and isinstance(result_cfgs[k], dict):
                    result_cfgs[k] = _merge(result_cfgs[k], v, path + [str(k)], filepath, hierarchy_level,
                                            playbook_tags,
                                            weight)
                else:
                    result_cfgs[k] = _merge({}, v, path + [str(k)], filepath, hierarchy_level, playbook_tags, weight)
            else:
                # if key not there, add
                if k not in result_cfgs:
                    result_cfgs[k] = (v, filepath, playbook_tags, hierarchy_level, weight)
                # if key found multiple places at same hierarchy level, error
                elif k in result_cfgs and hierarchy_level == result_cfgs[k][3] and result_cfgs[k][0]:
                    if filepath == result_cfgs[k][1]:
                        module.fail_json(
                            msg="Merge Error: key {1} was found multiple times at the same hierarchy level (level: {2}) in file {3}.".format(
                                k, result_cfgs[k][3], filepath))
                    else:
                        module.fail_json(
                            msg="Merge Error: key {1} was found multiple times at the same hierarchy level (level: {2}) in files {3} and {4}.".format(
                                k, result_cfgs[k][3], filepath, result_cfgs[k][1]))
                    module.exit_json(changed=False, failed=True)
                # if key exists but weight is higher, replace
                elif k in result_cfgs and weight > result_cfgs[k][4]:
                    result_cfgs[k] = (v, filepath, playbook_tags, hierarchy_level, weight)
        return result_cfgs

    result_configs = {}
    for i in all_configs:
        result_configs = _merge(result_configs, i['config'], filepath=i['filepath'], hierarchy_level=i['level'],
                                playbook_tags=i['tags'], weight=i['weight'])
    return result_configs


def list_to_dict(my_list, m_key):
    my_dict = {}
    for i in my_list:
        key = str(i[m_key])
        my_dict[key] = i
    return my_dict


def dict_to_list(my_dict):
    my_list = list(my_dict.values())
    return my_list


def dictify_merge_lists(list_of_configs, list_key_map):
    new_list = []

    def _to_dict(convert_cfgs, v, path=None):
        path = path or []
        for k, v in v.items():
            if isinstance(v, dict):
                if k in convert_cfgs and isinstance(convert_cfgs[k], dict):
                    convert_cfgs[k] = _to_dict(convert_cfgs[k], v, path + [str(k)])
                else:
                    convert_cfgs[k] = _to_dict({}, v, path + [str(k)])
            elif isinstance(v, list):
                merge_key = get_merge_key(":".join(path + [str(k)]), list_key_map)
                if merge_key:
                    v = list_to_dict(v, merge_key)
                    convert_cfgs[k] = _to_dict({}, v, path + [str(k)])
                elif all(isinstance(item, dict) for item in v):
                    convert_cfgs[k] = [_to_dict({}, x, path + [str(k)]) for x in v]
                else:
                    convert_cfgs[k] = v
            else:
                convert_cfgs[k] = v
        return convert_cfgs

    for i in list_of_configs:
        i['config'] = _to_dict({}, i['config'])
        new_list.append(i)
    return new_list


def undictify_merge_lists(d, list_key_map):
    p = find_paths(d, list_key_map)
    for i in p:
        path = i[0]
        path_reference = return_nested_dict(d, path)
        changes = dict_to_list(path_reference)
        update_nested_dict(d, path, changes)
    return d


def replace_tuples(cfgs):
    if isinstance(cfgs, dict):
        for k, v in cfgs.items():
            if isinstance(v, tuple):
                cfgs[k] = v[0]
            else:
                replace_tuples(v)
    elif isinstance(cfgs, list):
        for index, item in enumerate(cfgs):
            if isinstance(item, tuple):
                cfgs[index] = item[0]
            else:
                replace_tuples(item)
    return cfgs


def find_paths(d, list_key_map, path=None):
    if path is None:
        path = []
    special_paths = []

    def _find_paths(d, path=None):
        if path is None:
            path = []
        if isinstance(d, dict):
            for k, v in d.items():
                if not v:
                    merge_key = get_merge_key(":".join(path + [str(k)]), list_key_map)
                    if merge_key:
                        special_paths.append(("/:/".join(path + [str(k)]), len(path)))
                else:
                    merge_key = get_merge_key(":".join(path), list_key_map)
                    if merge_key:
                        special_paths.append(("/:/".join(path), len(path)))
                    _find_paths(v, path + [str(k)])

    _find_paths(d)
    set_special_paths = set(special_paths)
    paths = [(i[0].split("/:/"), i[1]) for i in set_special_paths]
    sorted_paths = sorted(paths, key=lambda x: x[1], reverse=True)
    return sorted_paths


def return_nested_dict(root_dict, keys_list):
    return_dict = root_dict
    for key in keys_list:
        return_dict = return_dict[key]
    return return_dict


def update_nested_dict(root_dict, keys_list, new_value):
    last_key = keys_list[-1]
    rest_of_keys = keys_list[:-1]
    nested_dict = root_dict
    for key in rest_of_keys:
        nested_dict = nested_dict[key]
    nested_dict[last_key] = new_value


def combine(config_list, list_key_map, module):
    # Ensure configs are sorted by device level to org level
    sorted_list = sorted(config_list, key=lambda x: x['level'])  # this is in ascending order

    # Convert Merge Lists to dicts
    for_merging_configs = dictify_merge_lists(sorted_list, list_key_map)

    # Do the merging
    merge_results = merge_dicts(for_merging_configs, module)

    # Convert the Merge List dicts back to lists
    config_with_meta_data = undictify_merge_lists(merge_results, list_key_map)

    # Replace tuple meta data
    config_with_meta_data_copy = copy.deepcopy(config_with_meta_data)
    final_config = replace_tuples(config_with_meta_data_copy)

    return final_config, config_with_meta_data


def intersection(lst1, lst2):
    return list(set(lst1) & set(lst2))


def matches_filespec(filename, filespec_list):
    for filespec in filespec_list:
        if fnmatch.fnmatch(filename, filespec):
            return True
    return False


def find_and_read_configs(top_dir, device_name, filespec_list, default_weight, tags=None, module=None, hostvars=None):
    if tags is None:
        tags = []
    tags.append('all')  # every device gets an "all" tag
    configs = []
    hierarchy_level = 0
    for root, dirs, files in os.walk(top_dir):
        if device_name in dirs:
            current_dir = os.path.join(root, device_name)
            while current_dir != top_dir:
                for filename in os.listdir(current_dir):
                    if matches_filespec(filename, filespec_list):
                        env = Environment(loader=FileSystemLoader(current_dir))
                        with open(os.path.join(current_dir, filename), 'r') as f:
                            try:
                                template = env.from_string(f.read())
                                config_rendered = template.render(hostvars)
                                yaml_configs = yaml.safe_load_all(config_rendered)
                                for yaml_config in yaml_configs:
                                    file_tags = yaml_config.get('mdd_tags',
                                                                ['all'])  # if no mdd_tags, then file gets 'all' tag
                                    matched_tags = intersection(tags, file_tags)
                                    if matched_tags:
                                        configs.append(
                                            {
                                                'config': yaml_config.get('mdd_data', {}),
                                                'filepath': f.name,
                                                'tags': matched_tags,
                                                'weight': yaml_config.get('weight', default_weight),
                                                'level': hierarchy_level
                                            }
                                        )
                            except yaml.YAMLError:
                                module.fail_json(
                                    msg="An error occurred loading file {1}".format(os.path.join(current_dir, filename)))
                                module.exit_json(changed=False, failed=True)

                hierarchy_level += 1
                current_dir = os.path.dirname(current_dir)
            break
    return configs


def main():
    arguments = dict(
        mdd_root=dict(required=True, type='str'),
        host=dict(required=True, type='str'),
        filespec_list=dict(required=True, type='list', elements='str'),
        default_weight=dict(type='int', default=1000),
        tags=dict(required=False, type='list', elements='str'),
        hostvars=dict(required=True, type='dict'),
        # The list_key_map argument is not a secret and does not require `no_log`.
        list_key_map=dict(required=False, type='dict', no_log=False)
    )
    module = AnsibleModule(argument_spec=arguments, supports_check_mode=False)

    if not HAS_YAML:
        # Needs: from ansible.module_utils.basic import missing_required_lib
        module.fail_json(msg=missing_required_lib('yaml'), exception=YAML_IMPORT_ERROR)

    mdd_root = module.params['mdd_root']
    host = module.params['host']
    filespec_list = module.params['filespec_list']
    tags = module.params['tags']

    hostvars = module.params['hostvars']

    if module.params['list_key_map']:
        list_key_map = module.params['list_key_map']
    else:
        list_key_map = default_list_key_map

    if module.params['default_weight']:
        default_weight = module.params['default_weight']
    else:
        default_weight = 1000

    mdd_data = {}
    mdd_metadata = {}
    module.debug('POOP')
    configs_list = find_and_read_configs(mdd_root, host, filespec_list, default_weight, tags, module, hostvars)
    mdd_data, metadata = combine(configs_list, list_key_map, module)
    module.exit_json(changed=False, mdd_data=mdd_data, mdd_metadata=metadata, failed=False)


if __name__ == '__main__':
    main()
