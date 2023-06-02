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

# TODO: Write test cases

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
        description: The directory of the mdd data
        - When using this, always set the input to "{{ mdd_data_root }}" in the playbook
        - Like this mdd_data_dir: "{{ mdd_data_root }}"
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
      register: result
    - debug:
        var: result.debug
"""

import os
from fnmatch import fnmatch
import yaml
import shutil
from ansible.module_utils.basic import AnsibleModule

debug = []              # global variable for debugging
FILES_CREATED = False   # global variable for determining if anything was actually elevated


class Elevate:
    def __init__(self, mdd_data_dir, mdd_data_patterns, temp_dir, file_level: int = None, is_test_run: bool = False):
        self.mdd_data_dir = mdd_data_dir
        self.mdd_data_patterns = mdd_data_patterns
        self.file_level = file_level  # we need to add one so that level 1 in playbook will correspond with with keys under mdd_data
        self.is_test_run = is_test_run
        self.temp_dir = temp_dir
        self.file_pattern = ''
        self.device_tag = ''
        self.separator = '__*__'
        self.file_parts = ''
        self.at_bottom_dir = False
        self.first = True

        self.elevate()

    def get_parent_path(self, parent_keys: list) -> None:
        """Returns absolute path for file based on the list"""

        path = ""
        for key in parent_keys:
            path += "/" + key
        return path[1:]

    def clean_dictionary(self, dictionary: dict) -> None:
        """gets rid of unnecessary keys"""
        parent_keys = []
        self.clean_dictionary_helper(parent_keys, dictionary, dictionary)

    def clean_dictionary_helper(self, parent_keys: list, parent_dictionary: dict, child_dictionary: dict) -> None:
        """Recursive helper function for clean_dictionary()"""

        for key, value in list(child_dictionary.items()):
            if key == "tags":
                # Remove the tags
                del child_dictionary[key]

            if key in ('hosts', 'children'):
                # Move the value one up in the dictionary
                parent_dictionary[parent_keys[-1]] = value

            if isinstance(value, dict):
                # Go through and clean the lower dictionarys
                parent_keys.append(key)
                self.clean_dictionary_helper(parent_keys, child_dictionary, value)
                parent_keys.pop()

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

    def extract_keys_recursive(self, dictionary: dict, level: int, current_level: int = 0, parent_keys: str = "") -> list:
        """Returns a list of dictionaries with the keys being a string combination of the parent keys
            and the value being the level's value.
            If the level depth is larger than the nested dictionary's depth, it stops at the lowest level"""

        keys = []
        if current_level == level:
            for key in dictionary:
                new_key = parent_keys + self.separator + key if parent_keys else key
                keys.append({'key': new_key, 'depth': current_level, 'value': dictionary[key]})
            return keys

        for key, value in dictionary.items():
            if isinstance(value, dict) and value != {}:
                new_parent_keys = parent_keys + self.separator + key if parent_keys else key
                keys.extend(self.extract_keys_recursive(value, level, current_level + 1, new_parent_keys))
            elif current_level < level:
                new_key = parent_keys + self.separator + key if parent_keys else key
                keys.append({'key': new_key, 'depth': current_level, 'value': dictionary[key]})

        return keys

    def remove_and_create_temp_dir(self) -> None:
        """Removes the temp directory. If it is a test run, copies mdd-data into the tmp dir"""

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

        if self.is_test_run:
            # copy directory into temp directory
            shutil.copytree(self.mdd_data_dir, self.temp_dir)
            self.mdd_data_dir = self.temp_dir

    def find_file_level(self, config, files, level=0):
        if not isinstance(config, dict):
            return -1

        for key in config:
            if key.split(':')[-1] in files:
                return level

        for value in config.values():
            result = self.find_file_level(value, files, level + 1)
            if result != -1:
                return result

        return -1

    def get_meta_tag(self, tags):
        return self.separator.join(tags)

    def get_tags(self, meta_tag):
        return meta_tag.split(self.separator)

    def elevate_level(self, rel_path: str) -> None:
        """Finds common configs in a directory's child directories and elevates them to the current directory"""

        # How this function operates
        # Get the first dir and use the files in there as base files
        # for each base file:
        #   for each dir in path
        #       if base file name in here, grab config
        #   elevate config (single file) if applicable
        global FILES_CREATED

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

                for file_path, config in changed_files.items():
                    config_data = self.flatten_dict(config['data'])

                    # delete common configs
                    for key in flattened_result:
                        if key in config_data:  # remove any elevated configs
                            del config_data[key]

                    # empty - delete file
                    if not bool(config_data):  # since we combine files, if a config is empty, remove if from the file
                        if os.path.exists(file_path):
                            with open(file_path, 'r') as file:
                                data_dicts = yaml.safe_load_all(file)
                                results_to_write = []
                                for data in data_dicts:
                                    if 'mdd_tags' in data and self.get_meta_tag(data['mdd_tags']) != meta_tag:
                                        results_to_write.append(data)
                                if results_to_write:
                                    with open(file_path, 'w') as file:
                                        for result_data in results_to_write:
                                            file.write("---\n")
                                            yaml.safe_dump(result_data, file, sort_keys=False)
                                elif "mdd_data" in result:  # add a flag here
                                    debug.append(file_path + str(result))
                                    os.remove(file_path)
                    else:
                        # just overwrite old files with updated data
                        open_type = 'w'
                        if os.path.exists(file_path):
                            open_type = 'a'
                        # if os.path.exists(file_path):
                        with open(file_path, 'w') as file:
                            non_elevated_data = self.unflatten_dict(config_data)
                            non_elevated_data['mdd_tags'] = self.get_tags(meta_tag)
                            file.write("---\n")
                            yaml.safe_dump(non_elevated_data, file, sort_keys=False)

                if bool(result):
                    file_path = f"{path}/{anchor_file.name}"
                    open_type = 'w'
                    if os.path.exists(file_path):
                        open_type = 'a'
                    with open(file_path, open_type) as file:
                        result['mdd_tags'] = self.get_tags(meta_tag)
                        file.write("---\n")
                        yaml.safe_dump(result, file, sort_keys=False)

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
                self.at_bottom_dir = True
            elif not hit_bottom_dir:
                # continue till hit bottom dir
                parent_keys.append(key)
                self.iterate_directory_helper(value, parent_keys, hit_bottom_dir)  # iterate through child dictionaries
                parent_keys.pop()
        hit_bottom_dir = False
        self.elevate_level(self.get_parent_path(parent_keys))
        self.at_bottom_dir = False

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
        mdd_data_patterns=dict(required=True, type='list'),
        file_level=dict(required=True, type='int', default=None),
        is_test_run=dict(required=True, type='bool'),
        temp_dir=dict(required=True, type='str')
    )

    module = AnsibleModule(argument_spec=arguments, supports_check_mode=False)

    # if module.params['file_level'] is not None and module.params['file_level'] < 0:
    #     module.fail_json(msg="File level needs to be 0 and above")

    Elevate(module.params['mdd_data_dir'], module.params['mdd_data_patterns'],
            module.params['temp_dir'], module.params['file_level'], module.params['is_test_run'])
    module.exit_json(changed=True, failed=False, debug=debug)


if __name__ == '__main__':
    main()
