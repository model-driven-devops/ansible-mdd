from __future__ import absolute_import, division, print_function
__metaclass__ = type

import re

# The list of keys that will be searched to see is replacement is needed
keys_to_replace = [
    "openconfig-interfaces:name",
    "openconfig-network-instance:id",
    "openconfig-network-instance:interface",
    "openconfig-spanning-tree:name",
    "openconfig-system-ext:global-interface-name"
]


def multi_replace_regex(string, replacements, ignore_case=False, first_match=True):
    for pattern, repl in replacements.items():
        string, matches = re.subn(pattern, repl, string, flags=re.I if ignore_case else 0)
        if first_match and matches:
            return string
    return string


def xlate_value(data, intf_dict):
    """Find all values from a nested dictionary for a given key."""
    if isinstance(data, dict):
        for key in data:
            if isinstance(data[key], str) and key in keys_to_replace:
                data[key] = multi_replace_regex(data[key], intf_dict)
            else:
                xlate_value(data[key], intf_dict)
    elif isinstance(data, list):
        for item in data:
            xlate_value(item, intf_dict)
    else:
        return


def intf_xlate(data, intf_dict):
    if not data:
        return {}

    data_out = data.copy()
    xlate_value(data_out, intf_dict)

    return data_out


def intf_truncate(data, intf_dict):
    if not data:
        return {}

    regex_list = intf_dict.keys()
    temp_interface_list = []
    temp_stp_interface_list = []
    data_out = data.copy()

    if "mdd:openconfig" in data:
        oc_data = data["mdd:openconfig"]
        # Truncate interfaces

        if "openconfig-interfaces:interfaces" in oc_data and "openconfig-interfaces:interface" in oc_data["openconfig-interfaces:interfaces"]:
            for interface in oc_data["openconfig-interfaces:interfaces"]["openconfig-interfaces:interface"]:
                if any(re.match(regex, interface["openconfig-interfaces:name"]) for regex in regex_list):
                    temp_interface_list.append(interface)
            data_out["mdd:openconfig"]["openconfig-interfaces:interfaces"]["openconfig-interfaces:interface"] = temp_interface_list
        # Truncate STP interfaces
        if "openconfig-spanning-tree:stp" in oc_data and "openconfig-spanning-tree:interfaces" in oc_data["openconfig-spanning-tree:stp"]:
            for interface in oc_data["openconfig-spanning-tree:stp"]["openconfig-spanning-tree:interfaces"]["openconfig-spanning-tree:interface"]:
                if any(re.match(regex, interface["openconfig-spanning-tree:name"]) for regex in regex_list):
                    temp_stp_interface_list.append(interface)
            data_out["mdd:openconfig"]["openconfig-spanning-tree:stp"]["openconfig-spanning-tree:interfaces"]["openconfig-spanning-tree:interface"] = \
                temp_stp_interface_list

    return data_out


def intf_xform(data, intf_dict):
    data = intf_truncate(data, intf_dict)
    data = intf_xlate(data, intf_dict)
    return data


class FilterModule(object):

    def filters(self):
        return {
            'intf_xlate': intf_xlate,
            'intf_truncate': intf_truncate,
            'intf_xform': intf_xform
        }
