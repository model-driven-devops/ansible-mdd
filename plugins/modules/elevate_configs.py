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
    ansible_inventory:
        description: Where the ansible inventory is located
        required: true
        type: dict
    mdd_data_patterns:
        description: List of data patterns
        required: true
        type: list
        elements: str
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

try:
    from contextlib import suppress
except ImportError:
    HAS_SUPPRESS = False
    YAML_IMPORT_ERROR = traceback.format_exc()
else:
    HAS_SUPPRESS = True


class Elevate:
    """Elevates the configs for a network"""

    def __init__(self, mdd_data_dir, temp_dir, is_test_run, ansible_inventory, mdd_data_patterns):

        self.mdd_data_dir = mdd_data_dir
        self.is_test_run = is_test_run
        self.temp_dir = temp_dir
        self.mdd_data_patterns = mdd_data_patterns
        self.ansible_inventory = ansible_inventory['_meta']['hostvars']
        self.separator = '__*__'
        self.at_bottom_dir = False
        self.created_files = {}
        self.all_tags = []
        self.device_list = []
        self.tag_key = 'mdd_tags'
        self.main_key = 'mdd_data'
        self.yaml_network_data = {}
        self.forward_associated_tags = {}
        self.current_level = 0
        self.unelevated_files = {}

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
        return tags[-1]

    def get_tags(self, meta_tag):
        """Creates a list from the meta tag by splitting it"""

        return meta_tag.split(self.separator)

    def get_file_key(self, path, file, tag):
        """Creates a key based on the path to the file and the associated tag"""

        return path + '/' + file + self.separator + tag

    def check_unable_elevate(self, parent_dir, file, tag):
        """Determines to not elevate a file given a tag if the tag and associated file are in the self.unelevated_files dictionary with a lower level"""

        for file_tag, levels in self.unelevated_files.items():
            if parent_dir in file_tag and file in file_tag and tag in file_tag:
                for level in levels:
                    if level < self.current_level:
                        return True
        return False

    def matches_file_pattern(self, filename):
        """Determines if a file matches the mdd patterns"""
        for pattern in self.mdd_data_patterns:
            if fnmatch(filename, pattern):
                return True
        return False

    def elevate_level(self, rel_path):
        """Finds common configs in a directory's child directories and elevates them to the current directory"""

        # How this function operates
        # Get the first dir and use the files in there as base files
        # for each base file:
        #   for each dir in path
        #       if base file name in here, grab config
        #   elevate config (single file) if applicable

        path = os.path.join(self.mdd_data_dir, rel_path)
        if rel_path == "":  # don't iterate through top level directory
            return
        if path not in self.forward_associated_tags:
            return

        tags = {}
        parent_dir_name = path.rsplit("/", 1)[1]
        par_dir = path.rsplit("/", 1)[0]

        if self.at_bottom_dir:
            for tags, device_list in self.forward_associated_tags[path].items():
                anchor_device = path + "/" + device_list[0]
                if len(device_list) == 1:
                    # if it's the only device with that tag just elevate everything
                    for file in os.scandir(anchor_device):
                        if not self.matches_file_pattern(file.name):
                            continue

                        file_name = str(file.name)
                        destination_path = path + "/" + file_name

                        if os.path.exists(destination_path):  # append to file
                            with open(destination_path, 'a', encoding='utf-8') as write_file, open(file.path, 'r', encoding='utf-8') as read_file:
                                yaml.safe_dump_all(yaml.safe_load_all(read_file), write_file, sort_keys=False, explicit_start=True)

                        else:  # copy everything
                            with open(destination_path, 'a', encoding='utf-8') as write_file, open(file.path, 'r', encoding='utf-8') as read_file:
                                shutil.copyfileobj(read_file, write_file)

                        # remove old file
                        os.remove(file.path)
                        self.created_files[destination_path] = None

                        self.forward_associated_tags.setdefault(par_dir, {}).setdefault(path, {}).setdefault(file_name, []).append(tags)

                else:  # not a singular file
                    for file in os.scandir(anchor_device):

                        if not self.matches_file_pattern(file.name):
                            continue

                        file_name = file.name
                        file_path = file.path
                        flattened_fc_dict = []

                        with open(file_path, 'r', encoding='utf-8') as read_file:
                            file_data = yaml.safe_load(read_file)  # know only 1 document in file
                            flattened_fc_dict.append({"data": self.flatten_dict(file_data, ""), "file": file_path})
                        del file_data

                        for device in device_list[1:]:
                            device_path = path + "/" + device + "/" + file_name  # we are guessing the file exists somewhere else
                            if os.path.exists(device_path):
                                with open(device_path, 'r', encoding='utf-8') as read_file:
                                    file_data = yaml.safe_load(read_file)
                                    flattened_fc_dict.append({"data": self.flatten_dict(file_data, ""), "file": device_path})
                                del file_data

                        common_keys = {}
                        keys_to_remove = []
                        for dict_item in flattened_fc_dict[1:]:
                            for key in dict_item['data'].keys():
                                if key in flattened_fc_dict[0]['data'] and dict_item['data'][key] == flattened_fc_dict[0]['data'][key]:
                                    common_keys.update({key: dict_item['data'][key]})
                                    if key != self.tag_key:
                                        keys_to_remove.append(key)

                        for key in keys_to_remove:
                            for x, item in enumerate(flattened_fc_dict):
                                del item['data'][key]

                        result = self.unflatten_dict(common_keys)
                        destination_path = path + "/" + file_name
                        if self.main_key in result:
                            with open(destination_path, 'a', encoding='utf-8') as write_file:
                                yaml.safe_dump(result, write_file, sort_keys=False, explicit_start=True)
                            self.created_files[destination_path] = None
                        else:
                            self.unelevated_files.setdefault(self.get_file_key(path, file_name, tags), []).append(self.current_level)

                        for val in flattened_fc_dict:
                            val_data = self.unflatten_dict(val["data"])

                            if self.main_key not in val_data:
                                os.remove(val['file'])
                                with suppress(KeyError):
                                    del self.created_files[val['file']]
                            else:
                                with open(val['file'], 'w', encoding='utf-8') as write_file:
                                    yaml.safe_dump(val_data, write_file, sort_keys=False, explicit_start=True)

                        self.forward_associated_tags.setdefault(par_dir, {}).setdefault(path, {}).setdefault(file_name, []).append(tags)

        else:
            dirs_list = []
            for dirs in self.forward_associated_tags[path].keys():
                dirs_list.append(dirs)

            anchor_dir = dirs_list[0]
            if len(dirs_list) == 1:  # solo, auto elevate everything
                for file in self.forward_associated_tags[path][anchor_dir].keys():
                    tags = self.forward_associated_tags[path][anchor_dir][file]

                    if self.check_unable_elevate(parent_dir_name, file, tags[0]):
                        continue

                    file_path = anchor_dir + "/" + file
                    destination_path = path + "/" + file

                    if os.path.exists(destination_path):  # append
                        with open(destination_path, 'a', encoding='utf-8') as write_file, open(file_path, 'r', encoding='utf-8') as read_file:
                            yaml.safe_dump_all(yaml.safe_load_all(read_file), write_file, sort_keys=False, explicit_start=True)
                    else:  # just copy files
                        with open(destination_path, 'a', encoding='utf-8') as write_file, open(file_path, 'r', encoding='utf-8') as read_file:
                            shutil.copyfileobj(read_file, write_file)

                    # remove old file
                    os.remove(file_path)
                    self.created_files[destination_path] = None
                    with suppress(ValueError, AttributeError):
                        del self.created_files[file_path]

                    self.forward_associated_tags.setdefault(par_dir, {}).setdefault(path, {}).setdefault(file, []).extend(tags)

            else:
                for file in self.forward_associated_tags[path][anchor_dir]:

                    if not self.matches_file_pattern(file):
                        continue

                    file_tags = self.forward_associated_tags[path][anchor_dir][file]
                    fc_solo = []
                    flattened_fc_dict = {}
                    files_to_delete = []
                    configs_to_write = {}
                    solo_auto_delete = True

                    # get all common tags between the files
                    common_tags = file_tags
                    for dir_item in dirs_list[1:]:
                        if file not in self.forward_associated_tags[path][dir_item]:
                            continue
                        comp_file_tags = self.forward_associated_tags[path][dir_item][file]
                        common_tags = [tag for tag in common_tags if tag in comp_file_tags]

                    file_path = anchor_dir + "/" + file
                    with open(file_path, 'r', encoding='utf-8') as read_file:
                        file_data = yaml.safe_load_all(read_file)
                        for data in file_data:
                            if self.check_unable_elevate(parent_dir_name, file, data[self.tag_key][0]):
                                # Do not try to elevate something if the same config was not elevated somewhere else
                                configs_to_write.setdefault(file_path, []).append(data)
                                solo_auto_delete = False

                            elif data[self.tag_key][0] in common_tags:
                                # Put in dictionary to be compared
                                flattened_fc_dict.setdefault(data[self.tag_key][0], []).append({"data": self.flatten_dict(data, ""), "file": file_path})
                                solo_auto_delete = False

                            else:  # Parts not common so just elevate this stuff
                                fc_solo.append({"data": data, "file": file_path})

                        del file_data

                        if solo_auto_delete:
                            files_to_delete.append(file_path)

                    for dir_item in dirs_list[1:]:
                        # we are guessing the file exists somewhere else?
                        # but also maybe not cause we kinda know it exists cause we made it
                        # I think this approach is safe
                        if file not in self.forward_associated_tags[path][dir_item]:
                            continue

                        comp_file_tags = self.forward_associated_tags[path][dir_item][file]
                        common_tags = [tag for tag in file_tags if tag in comp_file_tags]

                        file_path_comp = dir_item + "/" + file
                        with open(file_path_comp, 'r', encoding='utf-8') as read_file:
                            file_data = yaml.safe_load_all(read_file)
                            for data in file_data:
                                if self.check_unable_elevate(parent_dir_name, file, data[self.tag_key][0]):
                                    # Do not try to elevate something if the same config was not elevated somewhere else
                                    configs_to_write.setdefault(file_path_comp, []).append(data)
                                    solo_auto_delete = False
                                elif data[self.tag_key][0] in common_tags:  # Can we safely assume it will only have 1 tag? Ask Kris
                                    flattened_fc_dict.setdefault(data[self.tag_key][0], []).append(
                                        {"data": self.flatten_dict(data, ""), "file": file_path_comp})
                                    solo_auto_delete = False
                                else:
                                    fc_solo.append({"data": data, "file": file_path_comp})

                            del file_data

                            if solo_auto_delete:
                                files_to_delete.append(file_path_comp)

                    common_keys = {}
                    keys_to_remove = {}
                    results = {}
                    for meta_tag, tagged_configs in flattened_fc_dict.items():
                        for config in tagged_configs[1:]:
                            for key in config['data'].keys():
                                if key in tagged_configs[0]['data'] and config['data'][key] == tagged_configs[0]['data'][key]:
                                    common_keys.setdefault(meta_tag, {}).update({key: config['data'][key]})
                                    if key != self.tag_key:
                                        keys_to_remove.setdefault(meta_tag, []).append(key)

                    for meta_key, keys in keys_to_remove.items():
                        for key in keys:
                            for x, item in enumerate(flattened_fc_dict[meta_key]):
                                del item['data'][key]
                    for meta_tag, flattened_result in common_keys.items():
                        results[meta_tag] = self.unflatten_dict(flattened_result)
                        results[meta_tag][self.tag_key] = [meta_tag]

                    tags = []
                    destination_path = path + "/" + file
                    with open(destination_path, 'a', encoding='utf-8') as write_file:
                        self.created_files[destination_path] = None
                        for meta_tag, config in results.items():
                            if self.main_key in config:
                                yaml.safe_dump(config, write_file, sort_keys=False, explicit_start=True)
                                tags.extend(config['mdd_tags'])
                            else:
                                self.unelevated_files.setdefault(self.get_file_key(path, file, meta_tag), []).append(self.current_level)
                        for config in fc_solo:
                            yaml.safe_dump(config['data'], write_file, sort_keys=False, explicit_start=True)
                            tags.extend(config['data']['mdd_tags'])

                    self.forward_associated_tags.setdefault(par_dir, {}).setdefault(path, {}).setdefault(file, []).extend(tags)

                    # Below handles with removing stuff out of the old files
                    # Determine if any part of the config left in each config
                    for meta_tag, dictionaries in flattened_fc_dict.items():
                        for val in dictionaries:
                            val_data = self.unflatten_dict(val["data"])
                            configs_to_write.setdefault(val['file'], [])

                            if self.main_key in val_data:
                                configs_to_write[val['file']].append(val_data)

                    # write back configs or delete file
                    for file_path_write, configs in configs_to_write.items():
                        if len(configs) == 0:  # nothing to write back - remove file
                            os.remove(file_path_write)
                            with suppress(KeyError):
                                del self.created_files[file_path_write]
                        else:
                            with open(file_path_write, 'w', encoding='utf-8') as write_file:
                                yaml.safe_dump_all(configs, write_file, sort_keys=False, explicit_start=True)

                    # Remove all unnecessary files
                    for del_file in files_to_delete:
                        os.remove(del_file)
                        with suppress(KeyError):
                            del self.created_files[del_file]

        del self.forward_associated_tags[path]

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
                    if key in result_flattened and result_flattened[key] == val:  # If we find the key in the config anchor dict

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
                    tags = ["all"]

                result[self.tag_key] = tags
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

            # Sort the configs by number of tags
            print_to_file[1:] = sorted(print_to_file[1:], key=lambda x: len(x[self.tag_key]), reverse=True)

            # Write result back to the file
            with open(filepath, 'w', encoding='utf-8') as file:
                yaml.safe_dump_all(print_to_file, file, explicit_start=True, sort_keys=False)

    def associate_tags(self):
        """Creates a dictionary of tags with devices that have those tags"""

        for device_data in self.device_list:
            device = device_data['name']
            path = device_data['path']
            if device in self.ansible_inventory and 'tags' in self.ansible_inventory[device]:
                tag = ", ".join(sorted(self.ansible_inventory[device]['tags']))
                parent_dir = '/'.join(path.split('/')[:-1])

                if tag not in self.all_tags:
                    self.all_tags.append(tag)

                self.forward_associated_tags.setdefault(parent_dir, {}).setdefault(tag, []).append(device)

        del self.ansible_inventory

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
                self.current_level = 0
                # append to the device list
            elif not hit_bottom_dir:
                # continue till hit bottom dir
                parent_keys.append(key)
                self.iterate_directory_helper(value, parent_keys, hit_bottom_dir)  # iterate through child dictionaries
                parent_keys.pop()
        self.elevate_level(self.get_parent_path(parent_keys))
        self.current_level += 1
        hit_bottom_dir = False
        self.at_bottom_dir = False

    def generate_directory_structure(self, path):
        """Generates a dirctory structure in the form of a dictionary from a given path"""

        result = {}
        if os.path.isdir(path):
            for file in os.scandir(path):
                if file.is_dir():
                    gen_result = self.generate_directory_structure(file.path)
                    if not gen_result:
                        self.device_list.append({"name": file.name, 'path': file.path})
                    result[file.name] = gen_result
        return result

    def elevate(self):
        """Starts the elevations process"""

        # Used for test runs. Creates a temp dir for test runs
        self.remove_and_create_temp_dir()

        # Recreated the directory structure as a dictionary
        self.yaml_network_data = self.generate_directory_structure(self.mdd_data_dir)

        # Associate tags with their devices
        self.associate_tags()
        self.iterate_directory(self.yaml_network_data)
        self.aggregate_results(self.created_files)


def main():
    """Runs the elevation process"""

    arguments = dict(
        mdd_data_dir=dict(required=True, type='str'),
        is_test_run=dict(required=True, type='bool'),
        temp_dir=dict(required=True, type='str'),
        ansible_inventory=dict(required=True, type='dict'),
        mdd_data_patterns=dict(required=True, type='list')
    )

    module = AnsibleModule(argument_spec=arguments, supports_check_mode=False)

    # Import yaml
    if not HAS_YAML:
        module.fail_json(msg=missing_required_lib('yaml'))

    if not HAS_SUPPRESS:
        module.fail_json(msg=missing_required_lib('suppress'))

    Elevate(module.params['mdd_data_dir'],
            module.params['temp_dir'],
            module.params['is_test_run'],
            module.params['ansible_inventory'],
            module.params['mdd_data_patterns'])
    module.exit_json(changed=True, failed=False, debug=debug)


if __name__ == '__main__':
    main()
