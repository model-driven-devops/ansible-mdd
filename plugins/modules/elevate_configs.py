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
        self.at_bottom_dir = False
        self.created_files = []
        self.all_tags = []
        self.tag_key = 'mdd_tags'
        self.main_key = 'mdd_data'

        self.elevate()

    def get_parent_path(self, parent_keys):
        """Returns absolute path for file based on the list"""

        path = ""
        for key in parent_keys:
            path += "/" + key
        return path[1:]

    def unflatten_dict(self, flattened_dictionary):
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

    def flatten_dict(self, dictionary, prefix):
        """Takes a nested dictionary and convertes it to a single-depth dictionary with keys indicating the levels"""

        flattened = {}
        for key, value in dictionary.items():
            if isinstance(value, dict) and bool(value):
                flattened.update(self.flatten_dict(value, prefix + key + self.separator))
            else:
                flattened[prefix + key] = value
        return flattened

    def find_common_key_value_pairs(self, dicts):
        """Find common keys between a list of dictionaries"""

        if not bool(dicts):
            return {}

        common_pairs = self.flatten_dict(dicts[0], "")

        for dictionary in dicts[1:]:
            flattened_dict = self.flatten_dict(dictionary, "")
            common_pairs = self.intersect_dicts(common_pairs, flattened_dict)

        return common_pairs

    def intersect_dicts(self, dict1, dict2):
        """Finds the intersection between two dictionaries"""

        intersection = {}
        for key in dict1:
            if key in dict2 and dict1[key] == dict2[key]:
                intersection[key] = dict1[key]
        return intersection

    def find_common_configs(self, configs):
        """Returns the common configs"""

        return self.unflatten_dict(self.find_common_key_value_pairs(configs))

    def remove_and_create_temp_dir(self):
        """Removes the temp directory. If it is a test run, copies mdd-data into the tmp dir"""

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

        if self.is_test_run:
            # copy directory into temp directory
            shutil.copytree(self.mdd_data_dir, self.temp_dir)
            self.mdd_data_dir = self.temp_dir

    def get_meta_tag(self, tags):
        """Creates a one meta tag from the list joined by a separator"""

        # return self.separator.join(tags)
        return tags[-1]  # TODO this is a hack, please fix : )

    def get_tags(self, meta_tag):
        """Creates a list from the meta tag by splitting it"""

        return meta_tag.split(self.separator)

    def elevate_level(self, rel_path):
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

        # Only do if file in all directories
        # valid_files = {}
        # first_time = True
        # for dir in dir_files:  # obtain a base - where would do tags
        #     # get tags
        #     for file in os.scandir(dir.path):
        #         if file.is_file() and fnmatch(file.name, '*.yml'):
        #             if first_time:
        #                 valid_files.setdefault(file.name, []).append(dir.name)
        #             else:
        #                 if file.name not in valid_files:
        #                     continue
        #                 else:
        #                     valid_files[file.name].append(dir.name)

        #             with open(file.path, 'r', encoding='utf-8') as data_file:
        #                 data_dicts = yaml.safe_load_all(data_file)
        #                 for data in data_dicts:
        #                     if self.tag_key in data:
        #                         tags.setdefault(self.get_meta_tag(data[self.tag_key]), []).append(dir)

        #     first_time = False

        # for filename, directories in list(valid_files.items()):
        #     if len(directories) != len(dir_files):
        #         del valid_files[filename]

        for dir in dir_files:  # obtain a base - where would do tags
            # get tags
            for file in os.scandir(dir.path):
                if file.is_file() and fnmatch(file.name, '*.yml'):
                    with open(file.path, 'r', encoding='utf-8') as data_file:
                        data_dicts = yaml.safe_load_all(data_file)
                        for data in data_dicts:
                            if self.tag_key in data:
                                tags.setdefault(self.get_meta_tag(data[self.tag_key]), []).append(dir)  # TODO this fails when elevate is run sequentially
                                if self.at_bottom_dir:
                                    self.all_tags = sorted(list(set(self.all_tags).union(set(data[self.tag_key]))), key=lambda x: x.lower())
                    break

        # # If not all directories contain that tag, don't do it
        # if not self.at_bottom_dir:
        #     for meta_tag, directories in list(tags.items()):
        #         if len(directories) != len(dir_files):
        #             del tags[meta_tag]

        for meta_tag, directories in tags.items():
            # get anchor
            anchor_files = []
            for file in os.scandir(directories[-1].path):
                if file.is_file() and fnmatch(file.name, '*.yml'):  # and file.name in valid_files: # TODO: ADDED
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
                                    if self.tag_key in data and self.get_meta_tag(data[self.tag_key]) == meta_tag:
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
                flattened_result = self.flatten_dict(result, "")
                for file_path, config in changed_files.items():  # remove from old file
                    config_data = self.flatten_dict(config['data'], "")

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
                                    config_data[self.tag_key] = self.get_tags(meta_tag)
                                    write_configs.append(config_data)
                            else:
                                write_configs.append(data)

                    if len(write_configs) == 0:
                        os.remove(file_path)
                        if file_path in self.created_files:
                            self.created_files.remove(file_path)
                    else:
                        with open(file_path, 'w') as file:
                            yaml.safe_dump_all(write_configs, file, sort_keys=False, explicit_start=True)

                if self.tag_key in result:
                    del result[self.tag_key]

                if bool(result):  # write to elevated file
                    file_path = str(path) + "/" + str(anchor_file.name)
                    open_type = 'w'
                    if os.path.exists(file_path):
                        open_type = 'a'
                    else:
                        self.created_files.append(file_path)
                    with open(file_path, open_type) as file:
                        result[self.tag_key] = self.get_tags(meta_tag)
                        file.write("---\n")
                        yaml.safe_dump(result, file, sort_keys=False)

    # This method is stupd and complicated so I will explain it
    def aggregate_results(self, filepaths):
        """Goes through each file and combines the results"""
        for filepath in filepaths:  # Iterate through all the files we just creatd
            data_configs = []
            with open(filepath, 'r', encoding='utf-8') as file:
                configs = yaml.safe_load_all(file)
                for config in configs:
                    data_configs.append(config)

            # Our first step is to find all the common elements and put it at the top of each file
            result = self.find_common_configs(data_configs)  # find all the common configs
            result_flattened = self.flatten_dict(result, "")

            tags = []
            final_configs = []
            for config in data_configs:  # Look through all the configs
                data_config_tags = config[self.tag_key]
                flattened_subsection = self.flatten_dict(config, "")
                remove_keys = []
                for key, val in flattened_subsection.items():
                    if key in result_flattened:  # If we find the key in the config anchor dict

                        for check_tag in data_config_tags:
                            if check_tag not in tags:
                                tags.append(check_tag)

                        remove_keys.append(key)  # Remove it from the old config dict

                for key in remove_keys:  # Remove the keys later because we can't edit a list mid iteration
                    del flattened_subsection[key]

                unflattened_result = self.unflatten_dict(flattened_subsection)
                if self.main_key in unflattened_result:
                    # If the result isn't empty use it
                    # because we might be deleting all the keys in a dict, and mdd_tags would remain
                    final_configs.append(unflattened_result)

            print_to_file = []
            if tags and result:
                if sorted(tags) == sorted(self.all_tags):  # If all tags are present, change tags to "all"
                    tags = "all"

                result[self.tag_key] = [tags]
                print_to_file.append(result)  # Put the configs commonality at the front of the list

            current_configs = []
            # We need to merge all matching configs from here, any duplicates will be pushed together
            # and their tags combined
            for config in final_configs:  # For all the remaining configs
                mdd_data = config[self.main_key]
                mdd_tags = config[self.tag_key]

                if mdd_data not in current_configs:  # Add the dict to the list
                    current_configs.append(mdd_data)
                    print_to_file.append({self.main_key: mdd_data, self.tag_key: mdd_tags})
                else:  # If the data already exists, append the tags
                    for res_item in print_to_file:
                        if res_item[self.main_key] == mdd_data:
                            for tag in mdd_tags:
                                res_item[self.tag_key].append(tag)

            # Write result back to the file
            with open(filepath, 'w', encoding='utf-8') as file:
                yaml.safe_dump_all(print_to_file, file, explicit_start=True, sort_keys=False)

    def iterate_directory(self, child_dict):
        """Iterates through the network's directory from bottom up"""

        parent_keys = []
        hit_bottom_dir = False
        self.iterate_directory_helper(child_dict, parent_keys, hit_bottom_dir)

    def iterate_directory_helper(self, child_dict, parent_keys, hit_bottom_dir):
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
        self.elevate_level(self.get_parent_path(parent_keys))
        hit_bottom_dir = False
        self.at_bottom_dir = False

    def generate_directory_structure(self, path):
        """Generates a dirctory structure in the form of a dictionary from a given path"""

        result = {}
        if os.path.isdir(path):
            files = os.listdir(path)
            for file in files:
                sub_path = os.path.join(path, file)
                if os.path.isdir(sub_path):
                    result[file] = self.generate_directory_structure(sub_path)
        return result

    def elevate(self):
        """Starts the elevations process"""

        # Used for test runs. Creates a temp dir for test runs
        self.remove_and_create_temp_dir()

        # Recreated the directory structure as a dictionary
        yaml_network_data = self.generate_directory_structure(self.mdd_data_dir)

        # Elevate the configs
        self.iterate_directory(yaml_network_data)

        # Clean the elevated configs, aggregating common results
        # like configs in each file will be move to the top
        # and matching configs will be merged afterwards
        self.aggregate_results(self.created_files)


def main():
    """Runs the elevation process"""

    arguments = dict(
        mdd_data_dir=dict(required=True, type='str'),
        is_test_run=dict(required=True, type='bool'),
        temp_dir=dict(required=True, type='str')
    )

    module = AnsibleModule(argument_spec=arguments, supports_check_mode=False)

    # Import yaml
    if not HAS_YAML:
        module.fail_json(msg=missing_required_lib('yaml'))

    Elevate(module.params['mdd_data_dir'], module.params['temp_dir'], module.params['is_test_run'])
    module.exit_json(changed=True, failed=False, debug=debug)


if __name__ == '__main__':
    main()
