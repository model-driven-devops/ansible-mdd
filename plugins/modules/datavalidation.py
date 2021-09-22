#!/usr/bin/env python

import argparse
import ipaddress
import json
from jsonschema import validate, Draft7Validator, FormatChecker, draft7_format_checker, validators
from jsonschema.exceptions import ValidationError

from ansible.module_utils.basic import AnsibleModule

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