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

#TODO: Write test cases

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
from ansible.module_utils.basic import AnsibleModule

debug = []              # global variable for debugging
FILES_CREATED = False   # global variable for determining if anything was actually elevated
files_created = []

class Elevate:
    def __init__(self, mdd_data_dir, mdd_data_patterns, file_level, is_test_run):
        self.mdd_data_dir = mdd_data_dir
        self.mdd_data_patterns = mdd_data_patterns
        self.file_level = file_level # we need to add one so that level 1 in playbook will correspond with with keys under mdd_data
        self.is_test_run = is_test_run
        self.file_pattern = ''
        self.device_tag = ''
        self.separator = '__*__'
        self.files_created = []
        self.at_bottom_dir = False
        self.elevate()

    def clean_dictionary(self, dictionary : dict) -> None:
        """gets rid of unnecessary keys"""
        parent_keys = []
        self.clean_dictionary_helper(parent_keys, dictionary, dictionary)

    def clean_dictionary_helper(self, parent_keys : list, parent_dictionary : dict, child_dictionary : dict) -> None:
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


    def unflatten_dict(self, flattened_dictionary : dict) -> dict:
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


    def flatten_dict(self, dictionary : dict, prefix : str = '') -> dict:
        """Takes a nested dictionary and convertes it to a single-depth dictionary with keys indicating the levels"""

        flattened = {}
        for key, value in dictionary.items():
            if isinstance(value, dict) and bool(value):
                flattened.update(self.flatten_dict(value, prefix + key + self.separator))
            else:
                flattened[prefix + key] = value
        return flattened


    def find_common_key_value_pairs(self, dicts : list) -> dict:
        """Find common keys between a list of dictionaries"""

        if not bool(dicts):
            return {}

        common_pairs = self.flatten_dict(dicts[0])

        for dictionary in dicts[1:]:
            flattened_dict = self.flatten_dict(dictionary)
            common_pairs = self.intersect_dicts(common_pairs, flattened_dict)

        return common_pairs


    def intersect_dicts(self, dict1 : dict, dict2 : dict) -> dict:
        """Finds the intersection between two dictionaries"""

        intersection = {}
        for key in dict1:
            if key in dict2 and dict1[key] == dict2[key]:
                intersection[key] = dict1[key]
        return intersection


    def find_common_configs(self, configs: list) -> dict:
        """Returns the common configs"""

        return self.unflatten_dict(self.find_common_key_value_pairs(configs))


    def extract_keys_recursive(self, dictionary : dict, level : int, current_level : int = 0, parent_keys : str = "") -> list:
        """Returns a list of dictionaries with the keys being a string combination of the parent keys
            and the value being the level's value.
            If the level depth is larger than the nested dictionary's depth, it stops at the lowest level"""

        keys = []
        if current_level == level:
            for key in dictionary:
                new_key = parent_keys + self.separator + key if parent_keys else key
                keys.append({'key': new_key, 'depth': current_level, 'value' : dictionary[key]})
            return keys

        for key, value in dictionary.items():
            if isinstance(value, dict) and value != {}:
                new_parent_keys = parent_keys + self.separator + key if parent_keys else key
                keys.extend(self.extract_keys_recursive(value, level, current_level + 1, new_parent_keys))
            elif current_level < level:
                new_key = parent_keys + self.separator + key if parent_keys else key
                keys.append({'key': new_key, 'depth': current_level, 'value' : dictionary[key]})

        return keys

    def elevate_level(self, rel_path : str) -> None:
        """Finds common configs in a directory's child directories and elevates them to the current directory"""

        ## How this function operates
        # for each dir (given by dictionary? or can just get all dirs - will there be extra?) in path:
            # get all yml files
            # put into one yml file in path (Put all hq in one file, or just all hq-rt1 in one?)
        # compare files
        # delete similar configs
        # make elevated config files
        global FILES_CREATED

        if rel_path == "": # don't iterate through top level directory
            return

        configs = []
        changed_files = {}
        ignored_msgs = []
        path = os.path.join(self.mdd_data_dir, rel_path)

        # iterate through each child dir
        for file in os.scandir(path):
            if not file.is_dir(): # only want directories #TODO: need to check if dir in network?
                continue

            # if not fnmatch(file.name, "*-" + self.device_tag + "*"): # For switches
            #     continue

            # get all yml config files and put into one dictionary
            config = {}
            contains_yml_files = False
            for child_file in os.scandir(file.path):

                if not fnmatch(child_file.name, self.file_pattern):
                    continue

                contains_yml_files = True
                with open(child_file.path, 'r', encoding='utf-8') as file:
                    data = self.flatten_dict(yaml.safe_load(file))
                    config = self.flatten_dict(config)
                    config.update(data)
                    config = self.unflatten_dict(config)

                    changed_files[child_file.path] = { 'data': data, 'filename': child_file.name }

            if bool(config):
                configs.append(config)

            if not contains_yml_files:
                ignored_msgs.append(f"   Ignoring {file.name} Reason: Does not contain any files matching the patterns: {self.mdd_data_patterns}") # if directory contains no oc files

        # get common configs
        result = self.find_common_configs(configs)

        # Delete common configs from lower config files
        flattened_result = self.flatten_dict(result)

        used_paths = []
        used_devices = []
        final_message = {}
        for file_path, config in changed_files.items():
            has_changed = False
            used_configs = []
            config_data = self.flatten_dict(config['data'])

            if not self.is_test_run or (self.is_test_run and not self.at_bottom_dir):
                # only delete configs if not a test run or not at the bottom directory during a test run
                # checking for bottom directory because if user does not like the update, can just delete the elevated configs files
                # but don't want to have to go back and re-input what we took out from the original config files

                # delete common configs
                for key in flattened_result:
                    if key in config_data: # remove any elevated configs
                        has_changed = True
                        del config_data[key]

                # empty - delete file
                if not bool(config_data):
                    os.remove(file_path)
                else:
                    # just overwrite old files with updated data
                    with open(file_path, 'w') as file:
                        file.write("---\n")
                        yaml.safe_dump(self.unflatten_dict(config_data), file, sort_keys=False)

            file_path_cleaned = file_path.replace(config['filename'], "")
            device_name = file_path_cleaned.split('/')[-2]

            # if changed, make a printout explaining elevation changes
            if has_changed:
                file_path_cleaned = '/'.join(file_path_cleaned.split('/')[:-2] + [''])
                directory_cleaned = file_path_cleaned.split('/')[-2]

                if file_path_cleaned not in used_paths:
                    used_paths.append(file_path_cleaned)
                    final_message.update({ f"{file_path_cleaned}": f"Configs for {directory_cleaned} level" })

                if device_name not in used_devices:
                    used_devices.append(device_name)
                    if directory_cleaned in final_message.keys():
                        message_value = final_message[directory_cleaned]
                        message_value += f", {device_name}"
                        final_message[directory_cleaned] = message_value
                    else:
                        final_message.update({ f"{directory_cleaned}" : f"   Configs elevated to ({directory_cleaned}) level from: {device_name}" })

                if config['filename'] not in used_configs:
                    elevate_type = "Elevated parts of file "
                    if not bool(config_data):
                        elevate_type = "Elevated entire file "

                    used_configs.append(config['filename'])
                    final_message.update({ f"{directory_cleaned}_{config['filename']}" : f"       {elevate_type}{config['filename']}" })
                else:
                    append_msg = final_message[directory_cleaned]
                    append_msg += f", {device_name}"
                    final_message[directory_cleaned] = append_msg

        for key, message in final_message.items():
            debug.append(message)


        # make into separate config files
        if bool(result):
            debug.append(f"file level: {self.file_level}")

            list_of_keys = self.extract_keys_recursive(result, self.file_level)
            sorted_keys = sorted(list_of_keys, key=lambda x: x['depth'])

            # debug.append("")
            # for key in sorted_keys:
            #     debug.append(key['key'] + " " + str(key['depth']))
            # debug.append("")

            # Remove duplicate top level keys so file names are shortened
            keys_hierarchies_simplified = [key_dict['key'].split(self.separator) for key_dict in sorted_keys]
            self.remove_duplicates(keys_hierarchies_simplified)

            # create separate files
            count = 0
            for key_dict, keys_hierarchy in zip(sorted_keys, keys_hierarchies_simplified):
                FILES_CREATED = True
                keys_hierarchy_dict = key_dict['key'].split(self.separator)
                data = self.create_nested_dict(keys_hierarchy_dict, key_dict['value'])

                filename = "-".join(key.rsplit(':', 1)[-1] for key in keys_hierarchy)

                file_parts = self.file_pattern.split('*')
                file_path = f"{path}/{file_parts[0]}{filename}{file_parts[1]}"

                debug.append(f"creating file {filename}")
                self.files_created.append(file_path)
                with open(file_path, 'w') as file:
                    file.write("---\n")
                    yaml.safe_dump(data, file, sort_keys=False)

                count += 1

        if FILES_CREATED:
            for message in ignored_msgs:
                debug.append(message)
            debug.append("")


    def get_parent_path(self, parent_keys : list) -> None:
        """Returns absolute path for file based on the list"""

        path = ""
        for key in parent_keys:
            path += "/" + key
        return path[1:]


    def iterate_directory(self, child_dict : dict) -> None:
        """Iterates through the network's directory from bottom up"""

        parent_keys = []
        hit_bottom_dir = False
        self.iterate_directory_helper(child_dict, parent_keys, hit_bottom_dir)


    def iterate_directory_helper(self, child_dict : dict, parent_keys : list, hit_bottom_dir : bool) -> None:
        """Recursive function helper for iterate_directory()"""

        for key, value in child_dict.items():
            if isinstance(value, dict) and not bool(value) and not hit_bottom_dir:
                # means is empty and therefore hit bottom directory
                hit_bottom_dir = True
                self.at_bottom_dir = True
            elif not hit_bottom_dir:
                # continue till hit bottom dir
                parent_keys.append(key)
                self.iterate_directory_helper(value, parent_keys, hit_bottom_dir) # iterate through child dictionaries
                parent_keys.pop()
        hit_bottom_dir = False
        self.elevate_level(self.get_parent_path(parent_keys))
        self.at_bottom_dir = False


    def generate_directory_structure(self, path : str) -> dict:
        """Generates a dirctory structure in the form of a dictionary from a given path"""
        result = {}
        if os.path.isdir(path):
            files = os.listdir(path)
            for file in files:
                sub_path = os.path.join(path, file)
                if os.path.isdir(sub_path):
                    result[file] = self.generate_directory_structure(sub_path)
        return result


    def create_nested_dict(self, keys : list, value : any) -> dict:
        """Creates a nested dictionary from the list and assigns value to the inermost key"""
        nested_dict = {}
        current_dict = nested_dict

        for key in keys[:-1]:
            current_dict.setdefault(key, {})
            current_dict = current_dict[key]

        current_dict[keys[-1]] = value

        return nested_dict


    def remove_duplicates(self, lst: list) -> None:
        """Iterates through a list of lists and deletes items that are the same in the same order"""

        while len(lst[0]) > 1 and all(sublist[0] == lst[0][0] for sublist in lst): # > 1 so file will always have a name, else could get rid of all entries
            for sublist in lst:
                sublist.pop(0)


    def elevate(self) -> None:
        """Starts the elevations process"""

        # Find all the common configs
        yaml_network_data = self.generate_directory_structure(self.mdd_data_dir)
        debug.append(yaml_network_data)

        for file_pattern in self.mdd_data_patterns:
            self.file_pattern = file_pattern

            for tag in ["sw"]: # This is temporary as the tags feature is being implemented
                self.device_tag = tag
                self.iterate_directory(yaml_network_data)

        if not FILES_CREATED:
            debug.append("Configs already elevated to highest level")

        if self.is_test_run:
            global files_created
            for file in self.files_created:
                if os.path.exists(file):
                    #os.remove(file)
                    files_created.append(file)



def main():
    """Runs the elevation process"""
    arguments = dict(
        mdd_data_dir=dict(required=True, type='str'),
        mdd_data_patterns=dict(required=True, type='list'),
        file_level=dict(required=True, type='int'),
        is_test_run=dict(required=True, type='bool')
    )

    module = AnsibleModule(argument_spec=arguments, supports_check_mode=False)

    if module.params['file_level'] < 0:
        module.fail_json(msg="File level needs to be 0 and above")

    Elevate( module.params['mdd_data_dir'], module.params['mdd_data_patterns'], module.params['file_level'], module.params['is_test_run'])
    module.exit_json(changed=True, failed=False, debug=debug, files_created=files_created)


if __name__ == '__main__':
    main()
