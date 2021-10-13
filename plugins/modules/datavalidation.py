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
module: datavalidation
short_description: Validate data against a schema
description:
  - Validate data against a schema
author:
  - Josh Lothian (@stevenca)
requirements:
  - jsonschema
  - ipaddress
version_added: '0.1.0'
options:
    data:
        description: The data to check against the schema
        required: true
        type: dict
    schema:
        description: The schema used to check the data
        required: true
        type: dict
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
    # MDDValidator = validators.create(
    #     meta_schema=Draft7Validator.META_SCHEMA,
    #     validators=all_validators,
    #     type_checker=type_checker,
    # )
    MDDValidator = validators.extend(Draft7Validator, type_checker=type_checker, validators=all_validators)
    mdd_validator = MDDValidator(schema=schema)
    # validate the input file against the supplied schema
    # validate(instance=input, schema=schema, cls=MDDValidator, format_checker=draft7_format_checker)
    errors = mdd_validator.iter_errors(data)
    output = ""
    for error in errors:
        output += "*****************\n"
        output += str(error)

    if output == "":
        return None
    else:
        return output


def main():

    arguments = dict(data=dict(required=True, type='dict'), schema=dict(required=True, type='dict'))

    module = AnsibleModule(argument_spec=arguments, supports_check_mode=False)

    if not HAS_JSONSCHEMA:
        # Needs: from ansible.module_utils.basic import missing_required_lib
        module.fail_json(msg=missing_required_lib('jsonschema'), exception=JSONSCHEMA_IMPORT_ERROR)

    if not HAS_IPADDRESS:
        # Needs: from ansible.module_utils.basic import missing_required_lib
        module.fail_json(msg=missing_required_lib('ipaddress'), exception=IPADDRESS_IMPORT_ERROR)

    data = module.params['data']
    schema = module.params['schema']
    module.debug("*****************")
    # print(module.params)
    module.debug(type(schema))
    module.debug(type(data))
    module.debug("*****************")

    result = validate_schema(data, schema)
    if result is None:
        module.exit_json(changed=False)
    else:
        module.fail_json(msg=result)


if __name__ == '__main__':
    main()
