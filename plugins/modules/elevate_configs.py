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
#

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

ANSIBLE_METADATA = {'metadata_version': '1.1', 'status': ['preview'], 'supported_by': 'community'}

DOCUMENTATION = r"""
---
module: elevate_configs
short_description: elevates common configs in a network
description:
  - elevates any common configs to the highest level of commonality in a directory
author:
  - Kris Stickney (@kstickne)
  - Paul Pajerski (@ppajersk)
options:
    mdd_data_dir:
        description:
        - The directory of the mdd data
        - When using this, always set the input to mdd_data_root in the playbook
        required: true
        type: str
    is_test_run:
        description:
        - Determines if the elevation process will happen in the temp_dir
        - Allows user to see the results and approve/disaprove before commiting to mdd_data directory
        - Default is False
        - You can specify True by adding -e "test=true" when running the ansible playbook
        required: true
        type: bool
    temp_dir:
        description: The directory where the elevate process will happen if is_test_run == True
        required: true
        type: str
"""

EXAMPLES = r"""
- name: Elevate configs
  hosts: localhost
  gather_facts: false
  roles:
    - ciscops.mdd.data
  tasks:
    - name: elevate
      elevate_configs:
        mdd_data_dir: "{{ mdd_data_root }}"
        is_test_run: "{{ is_test_run }}"
        temp_dir: "{{ temp_dir }}"
      register: elevate_result
    - debug:
        var: result.debug
"""

import os
import traceback
from fnmatch import fnmatch
import shutil
from ansible.module_utils.basic import AnsibleModule, missing_required_lib

debug = []              # global variable for debugging

try:
    import yaml
except ImportError:
    HAS_YAML = False
    YAML_IMPORT_ERROR = traceback.format_exc()
else:
    HAS_YAML = True


class Elevate:
    def __init__(self, mdd_data_dir, temp_dir, is_test_run):

        self.mdd_data_dir = mdd_data_dir
        self.is_test_run = is_test_run
        self.temp_dir = temp_dir
        self.separator = '__*__'

        self.elevate()

    def get_parent_path(self, parent_keys) -> None:
        """Returns absolute path for file based on the list"""

        path = ""
        for key in parent_keys:
            path += "/" + key
        return path[1:]

    def unflatten_dict(self, flattened_dictionary: dict) -> dict:
        """Takes a flattened dictionary and converts it back to a nested dictionary based on the levels indicated in the keys"""

        if not bool(flattened_dictionary):
            return {}

        result = {}
        for key, value in flattened_dictionary.items():
            parts = key.split(self.separator)
            current_dict = result

            for part in parts[:-1]:
                if part not in current_dict:
                    current_dict[part] = {}
                current_dict = current_dict[part]

            current_dict[parts[-1]] = value

        return result

    def flatten_dict(self, dictionary: dict, prefix: str = '') -> dict:
        """Takes a nested dictionary and convertes it to a single-depth dictionary with keys indicating the levels"""

        flattened = {}
        for key, value in dictionary.items():
            if isinstance(value, dict) and bool(value):
                flattened.update(self.flatten_dict(value, prefix + key + self.separator))
            else:
                flattened[prefix + key] = value
        return flattened

    def find_common_key_value_pairs(self, dicts: list) -> dict:
        """Find common keys between a list of dictionaries"""

        if not bool(dicts):
            return {}

        common_pairs = self.flatten_dict(dicts[0])

        for dictionary in dicts[1:]:
            flattened_dict = self.flatten_dict(dictionary)
            common_pairs = self.intersect_dicts(common_pairs, flattened_dict)

        return common_pairs

    def intersect_dicts(self, dict1: dict, dict2: dict) -> dict:
        """Finds the intersection between two dictionaries"""

        intersection = {}
        for key in dict1:
            if key in dict2 and dict1[key] == dict2[key]:
                intersection[key] = dict1[key]
        return intersection

    def find_common_configs(self, configs: list) -> dict:
        """Returns the common configs"""

        return self.unflatten_dict(self.find_common_key_value_pairs(configs))

    def remove_and_create_temp_dir(self) -> None:
        """Removes the temp directory. If it is a test run, copies mdd-data into the tmp dir"""

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

        if self.is_test_run:
            # copy directory into temp directory
            shutil.copytree(self.mdd_data_dir, self.temp_dir)
            self.mdd_data_dir = self.temp_dir

    def get_meta_tag(self, tags: list) -> str:
        """Creates a one meta tag from the list joined by a separator"""

        return self.separator.join(tags)

    def get_tags(self, meta_tag: str) -> list:
        """Creates a list from the meta tag by splitting it"""

        return meta_tag.split(self.separator)

    def elevate_level(self, rel_path: str) -> None:
        """Finds common configs in a directory's child directories and elevates them to the current directory"""

        # How this function operates
        # Get the first dir and use the files in there as base files
        # for each base file:
        #   for each dir in path
        #       if base file name in here, grab config
        #   elevate config (single file) if applicable

        if rel_path == "":  # don't iterate through top level directory
            return

        path = os.path.join(self.mdd_data_dir, rel_path)

        dir_files = [file for file in os.scandir(path) if file.is_dir()]
        tags = {}
        for dir in dir_files:  # obtain a base - where would do tags
            # get tags
            for file in os.scandir(dir.path):
                if file.is_file() and fnmatch(file.name, '*.yml'):
                    with open(file.path, 'r', encoding='utf-8') as data_file:
                        data_dicts = yaml.safe_load_all(data_file)
                        for data in data_dicts:
                            if 'mdd_tags' in data:
                                tags.setdefault(self.get_meta_tag(data['mdd_tags']), []).append(dir)
                    break

        for meta_tag, directories in tags.items():
            # get anchor
            anchor_files = []
            for file in os.scandir(directories[-1]):
                if file.is_file() and fnmatch(file.name, '*.yml'):
                    anchor_files.append(file)

            for anchor_file in anchor_files:  # files in anchor directory
                configs = []
                changed_files = {}
                file_in_all_dirs = True

                for dir in directories:  # iterate through original directory

                    file_in_here = False
                    for yml_file in os.scandir(dir.path):  # just here to get all files - like could do a anchor_file.name in dir
                        if not yml_file.is_file():
                            continue

                        if anchor_file.name in yml_file.name and fnmatch(yml_file.name, '*.yml'):  # TODO: add matches pattern?
                            with open(yml_file.path, 'r', encoding='utf-8') as data_file:
                                data_dicts = yaml.safe_load_all(data_file)
                                for data in data_dicts:
                                    if 'mdd_tags' in data and self.get_meta_tag(data['mdd_tags']) == meta_tag:
                                        configs.append(data)
                                        changed_files[yml_file.path] = {'data': data, 'filename': yml_file.name}
                                        break
                                file_in_here = True
                            break

                    if not file_in_here:  # make sure the file was in all directories # TODO: Modify for tags
                        file_in_all_dirs = False
                        break

                if not file_in_all_dirs:
                    continue

                # get common configs
                result = self.find_common_configs(configs)

                # Delete common configs from lower config files
                flattened_result = self.flatten_dict(result)
                for file_path, config in changed_files.items():  # remove from old file
                    config_data = self.flatten_dict(config['data'])

                    # delete common configs
                    for key in flattened_result:
                        if key in config_data:  # remove any elevated configs
                            del config_data[key]

                    # empty - delete file
                    write_configs = []
                    with open(file_path, 'r') as file:
                        data_configs = yaml.safe_load_all(file)

                        for data in data_configs:
                            if config['data'] == data:
                                if bool(config_data):
                                    config_data = self.unflatten_dict(config_data)
                                    config_data['mdd_tags'] = self.get_tags(meta_tag)
                                    write_configs.append(config_data)
                            else:
                                write_configs.append(data)

                    if len(write_configs) == 0:
                        os.remove(file_path)
                    else:
                        with open(file_path, 'w') as file:
                            yaml.safe_dump_all(write_configs, file, sort_keys=False, explicit_start=True)

                if bool(result):  # write to elevated file
                    file_path = str(path) + "/" + str(anchor_file.name)
                    open_type = 'w'
                    if os.path.exists(file_path):
                        open_type = 'a'
                    with open(file_path, open_type) as file:
                        result['mdd_tags'] = self.get_tags(meta_tag)
                        file.write("---\n")
                        yaml.safe_dump(result, file, sort_keys=False)

                    # # below is if we want to merge tags - would have to change above algorithm when comparing to account for meta_tag being different
                    # # Would have to do if tags in all_tags
                    # result['mdd_tags'] = self.get_tags(meta_tag)
                    # if os.path.exists(file_path):
                    #     with open(file_path, 'r') as file:
                    #         data_dicts = yaml.safe_load_all(file)

                    #         results_to_write = []
                    #         for data in data_dicts:
                    #             if data['mdd_data'] == result['mdd_data']:
                    #                 result['mdd_tags'].extend(data['mdd_tags'])
                    #             else:
                    #                 results_to_write.append(data)
                    #         results_to_write.append(result)

                    #     with open(file_path, 'w') as file:
                    #         for result_data in results_to_write:
                    #             file.write("---\n")
                    #             yaml.safe_dump(result_data, file, sort_keys=False)

                    # else:
                    #     with open(file_path, 'w') as file:
                    #         file.write("---\n")
                    #         yaml.safe_dump(result, file, sort_keys=False)

    def iterate_directory(self, child_dict: dict) -> None:
        """Iterates through the network's directory from bottom up"""

        parent_keys = []
        hit_bottom_dir = False
        self.iterate_directory_helper(child_dict, parent_keys, hit_bottom_dir)

    def iterate_directory_helper(self, child_dict: dict, parent_keys: list, hit_bottom_dir: bool) -> None:
        """Recursive function helper for iterate_directory()"""

        for key, value in child_dict.items():
            if isinstance(value, dict) and not bool(value) and not hit_bottom_dir:
                # means is empty and therefore hit bottom directory
                hit_bottom_dir = True
            elif not hit_bottom_dir:
                # continue till hit bottom dir
                parent_keys.append(key)
                self.iterate_directory_helper(value, parent_keys, hit_bottom_dir)  # iterate through child dictionaries
                parent_keys.pop()
        hit_bottom_dir = False
        self.elevate_level(self.get_parent_path(parent_keys))

    def generate_directory_structure(self, path: str) -> dict:
        """Generates a dirctory structure in the form of a dictionary from a given path"""

        result = {}
        if os.path.isdir(path):
            files = os.listdir(path)
            for file in files:
                sub_path = os.path.join(path, file)
                if os.path.isdir(sub_path):
                    result[file] = self.generate_directory_structure(sub_path)
        return result

    def elevate(self) -> None:
        """Starts the elevations process"""

        self.remove_and_create_temp_dir()

        # Find all the common configs
        yaml_network_data = self.generate_directory_structure(self.mdd_data_dir)

        self.iterate_directory(yaml_network_data)


def main():
    """Runs the elevation process"""

    arguments = dict(
        mdd_data_dir=dict(required=True, type='str'),
        is_test_run=dict(required=True, type='bool', default=False),
        temp_dir=dict(required=True, type='str')
    )

    module = AnsibleModule(argument_spec=arguments, supports_check_mode=False)

    if not HAS_YAML:
        module.fail_json(msg=missing_required_lib('yaml'))

    Elevate(module.params['mdd_data_dir'], module.params['temp_dir'], module.params['is_test_run'])
    module.exit_json(changed=True, failed=False, debug=debug)


if __name__ == '__main__':
    main()
