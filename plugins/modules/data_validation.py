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
module: data_validation
short_description: Validate data against a schema
description:
  - Validate data against a schema
author:
  - Josh Lothian (@stevenca)
requirements:
  - jsonschema
  - ipaddress
  - yaml
version_added: '0.1.0'
options:
    data:
        description: The data to check against the schema
        required: true
        type: dict
    schema:
        description: The schema used to check the data
        required: false
        type: dict
    schema_file:
        description: The file containint the schema used to check the data
        required: false
        type: str
"""

EXAMPLES = r"""
- name: Build the topology
  hosts: localhost
  gather_facts: no
  tags:
    - cml
    - virl
    - network
  tasks:
    - name: Validate data against schema
      datavalidation:
        data: "{{ parsed_output }}"
        schema: "{{ lookup('file', schema_file) | from_yaml }}"
      register: validation_output
"""

import argparse
import json
import traceback
import os
from ansible.module_utils.basic import AnsibleModule, missing_required_lib

try:
    from jsonschema import validate, Draft7Validator, FormatChecker, draft7_format_checker, validators
    from jsonschema.exceptions import ValidationError
except ImportError:
    HAS_JSONSCHEMA = False
    JSONSCHEMA_IMPORT_ERROR = traceback.format_exc()
else:
    HAS_JSONSCHEMA = True

try:
    import ipaddress
except ImportError:
    HAS_IPADDRESS = False
    IPADDRESS_IMPORT_ERROR = traceback.format_exc()
else:
    HAS_IPADDRESS = True

try:
    import yaml
except ImportError:
    HAS_YAML = False
    YAML_IMPORT_ERROR = traceback.format_exc()
else:
    HAS_YAML = True


def in_subnet(validator, value, instance, schema):
    if not ipaddress.ip_address(instance) in ipaddress.ip_network(value):
        yield ValidationError("{0} not in subnet {1}".format(instance, value))


def is_ip_address(checker, instance):
    try:
        ipaddress.ip_address(instance)
    except ValueError:
        return False
    return True


def validate_schema(data, schema):
    Draft7Validator.META_SCHEMA['definitions']['simpleTypes']['enum'].append('ipaddress')
    all_validators = dict(Draft7Validator.VALIDATORS)
    all_validators['in_subnet'] = in_subnet
    type_checker = Draft7Validator.TYPE_CHECKER.redefine_many({"ipaddress": is_ip_address})
    MDDValidator = validators.extend(Draft7Validator, type_checker=type_checker, validators=all_validators)
    mdd_validator = MDDValidator(schema=schema)
    errors = mdd_validator.iter_errors(data)
    error_list = []
    for error in errors:
        error_list.append("{0}: {1}".format(error.json_path, error.message))

    return error_list


def main():

    arguments = dict(
        data=dict(required=True, type='dict'),
        schema=dict(required=False, type='dict'),
        schema_file=dict(required=False, type='str')
    )
    module = AnsibleModule(argument_spec=arguments, supports_check_mode=False)

    if not HAS_JSONSCHEMA:
        # Needs: from ansible.module_utils.basic import missing_required_lib
        module.fail_json(msg=missing_required_lib('jsonschema'), exception=JSONSCHEMA_IMPORT_ERROR)

    if not HAS_IPADDRESS:
        # Needs: from ansible.module_utils.basic import missing_required_lib
        module.fail_json(msg=missing_required_lib('ipaddress'), exception=IPADDRESS_IMPORT_ERROR)

    if not HAS_YAML:
        # Needs: from ansible.module_utils.basic import missing_required_lib
        module.fail_json(msg=missing_required_lib('yaml'), exception=IPADDRESS_IMPORT_ERROR)

    data = module.params['data']
    schema = {}
    if module.params['schema_file']:
        schema_file = module.params['schema_file']
        # Read in the datafile
        if not os.path.exists(schema_file):
            raise Exception("Cannot find file {0}".format(schema_file))
        with open(schema_file) as f:
            if schema_file.endswith('.yaml') or schema_file.endswith('.yml'):
                schema = yaml.safe_load(f)
            else:
                schema = json.load(f)
        base_dir = os.path.dirname(schema_file)
        os.chdir(base_dir)
    elif module.params['schema']:
        schema = module.params['schema']
    else:
        raise Exception("Need either schema_file or schema")

    if module.params['schema_file']:
        schema_title = os.path.basename(schema_file)
    elif 'title' in schema:
        schema_title = schema['title']
    else:
        schema_title = '<input>'

    error_list = validate_schema(data, schema)
    if error_list:
        error_string = ','.join(error_list)
        module.fail_json(msg="Schema Failed: {0}".format(error_string), failed_schema=schema_title, x_error_list=error_list)
    else:
        module.exit_json(changed=False, failed=False)


if __name__ == '__main__':
    main()
