from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.utils.unsafe_proxy import AnsibleUnsafeText
import yaml


class MyDumper(yaml.Dumper):
    def increase_indent(self, flow=False, indentless=False):
        return super(MyDumper, self).increase_indent(flow, False)


def convert_ansible_unsafe_text_to_safe(data):
    if isinstance(data, dict):
        return {convert_ansible_unsafe_text_to_safe(k): convert_ansible_unsafe_text_to_safe(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_ansible_unsafe_text_to_safe(item) for item in data]
    elif isinstance(data, AnsibleUnsafeText):
        return str(data)
    else:
        return data


def to_even_nicer_yaml(config_data):
    ansible_safe_config_data = convert_ansible_unsafe_text_to_safe(config_data)
    return yaml.dump(ansible_safe_config_data, Dumper=MyDumper, default_flow_style=False, explicit_start=True,
                     sort_keys=False)


class FilterModule(object):

    def filters(self):
        return {
            'to_even_nicer_yaml': to_even_nicer_yaml
        }
