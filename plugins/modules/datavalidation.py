#!/usr/bin/python
from __future__ import (absolute_import, division, print_function)
__metaclass__ = type
import argparse
import json
import traceback
from ansible.module_utils.basic import AnsibleModule


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
    yield ValidationError("{} not in subnet {}".format(instance, value)) 

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
  type_checker = Draft7Validator.TYPE_CHECKER.redefine_many({
      "ipaddress": is_ip_address
  })
  #MDDValidator = validators.create(
  #    meta_schema=Draft7Validator.META_SCHEMA,
  #    validators=all_validators,
  #    type_checker=type_checker,
  #)
  MDDValidator = validators.extend(Draft7Validator, type_checker=type_checker, validators=all_validators)
  mdd_validator = MDDValidator(schema=schema)
  # validate the input file against the supplied schema
  #validate(instance=input, schema=schema, cls=MDDValidator, format_checker=draft7_format_checker)
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

  arguments = dict(
    data = dict(required=True, type=dict),
    schema = dict(required=True, type=dict),
    monk=dict(required=False),
  )

  module = AnsibleModule(
    argument_spec=arguments,
    supports_check_mode=False
  )

  if not HAS_JSONSCHEMA:
      # Needs: from ansible.module_utils.basic import missing_required_lib
      module.fail_json(
          msg=missing_required_lib('jsonschema'),
          exception=JSONSCHEMA_IMPORT_ERROR)

  if not HAS_IPADDRESS:
      # Needs: from ansible.module_utils.basic import missing_required_lib
      module.fail_json(
          msg=missing_required_lib('ipaddress'),
          exception=IPADDRESS_IMPORT_ERROR)

  data = module.params['data']
  schema = module.params['schema']
  print("*****************")
  #print(module.params)
  print(type(schema))
  print(type(data))
  print("*****************")

  result = validate_schema(data, schema)
  if result is None:
    module.exit_json(changed=False)
  else:
    module.fail_json(msg=result)

if __name__ == '__main__':
  main()
