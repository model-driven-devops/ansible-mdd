from __future__ import (absolute_import, division, print_function)
__metaclass__ = type
from ansible.module_utils.six import raise_from
import traceback
import argparse
import json


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
  if errors:
    for error in errors:
        output += "*****************\n"
        output += str(error)
    return errors
  else:
    return None