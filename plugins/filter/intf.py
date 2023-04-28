from __future__ import absolute_import, division, print_function
__metaclass__ = type

import re

# The list of keys that will be searched to see if replacement is needed
keys_to_replace = [
    "openconfig-interfaces:name",
    "openconfig-network-instance:id",
    "openconfig-network-instance:interface",
    "openconfig-spanning-tree:name",
    "openconfig-system-ext:global-interface-name",
    "openconfig-acl:id",
    "openconfig-acl:interface",
    "openconfig-system-ext:ssh-source-interface",
    "openconfig-network-instance:interface-id",
    "openconfig-network-instance:index",
    "openconfig-network-instance:local-address"
]

def found_full_match(string, intf_dict):
    for pattern in intf_dict:
        if bool(re.fullmatch(pattern, string)): return pattern

    return None

def interface_name_replace(original_str, intf_dict):
    pattern = found_full_match(original_str.split(".")[0], intf_dict)

    if pattern:
        return re.sub(pattern, intf_dict[pattern], original_str)
    
    return original_str


def xlate_value(data, intf_dict):
    """Find all values from a nested dictionary for a given key."""
    if isinstance(data, dict):
        for key in data:
            if isinstance(data[key], str) and key in keys_to_replace:
                data[key] = interface_name_replace(data[key], intf_dict)
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
                if found_full_match(interface["openconfig-interfaces:name"].split(".")[0], intf_dict):
                    temp_interface_list.append(interface)
            data_out["mdd:openconfig"]["openconfig-interfaces:interfaces"]["openconfig-interfaces:interface"] = temp_interface_list

        # Truncate STP interfaces
        if "openconfig-spanning-tree:stp" in oc_data and "openconfig-spanning-tree:interfaces" in oc_data["openconfig-spanning-tree:stp"]:
            for interface in oc_data["openconfig-spanning-tree:stp"]["openconfig-spanning-tree:interfaces"]["openconfig-spanning-tree:interface"]:
                if found_full_match(interface["openconfig-spanning-tree:name"].split(".")[0], intf_dict):
                    temp_stp_interface_list.append(interface)
            (data_out["mdd:openconfig"]["openconfig-spanning-tree:stp"]["openconfig-spanning-tree:interfaces"]
             ["openconfig-spanning-tree:interface"]) = temp_stp_interface_list

        # Truncate network instance OSPF interfaces
        if "openconfig-network-instance:network-instances" in oc_data and ("openconfig-network-instance:network-instance" in
                                                                           oc_data["openconfig-network-instance:network-instances"]):
            for (instance_index, instance) in enumerate(oc_data["openconfig-network-instance:network-instances"]
                                                        ["openconfig-network-instance:network-instance"]):
                if "openconfig-network-instance:protocols" in instance:
                    for (prot_index, protocol) in enumerate(instance["openconfig-network-instance:protocols"]["openconfig-network-instance:protocol"]):
                        if "openconfig-network-instance:ospfv2" in protocol and ("openconfig-network-instance:areas" in
                                                                                 protocol["openconfig-network-instance:ospfv2"]):
                            temp_ospf_interface_list = []
                            for (area_index, area) in enumerate(protocol["openconfig-network-instance:ospfv2"]["openconfig-network-instance:areas"]
                                                                ["openconfig-network-instance:area"]):
                                if "openconfig-network-instance:interfaces" in area:
                                    for interface in area["openconfig-network-instance:interfaces"]["openconfig-network-instance:interface"]:
                                        if found_full_match(interface["openconfig-network-instance:id"].split(".")[0], intf_dict):
                                            temp_ospf_interface_list.append(interface)
                                    (data_out["mdd:openconfig"]["openconfig-network-instance:network-instances"]
                                     ["openconfig-network-instance:network-instance"][instance_index]["openconfig-network-instance:protocols"]
                                     ["openconfig-network-instance:protocol"][prot_index]["openconfig-network-instance:ospfv2"]
                                     ["openconfig-network-instance:areas"]["openconfig-network-instance:area"][area_index]
                                     ["openconfig-network-instance:interfaces"]["openconfig-network-instance:interface"]) = temp_ospf_interface_list

        # Truncate network-instance interfaces
        if "openconfig-network-instance:network-instances" in oc_data and ("openconfig-network-instance:network-instance" in
                                                                           oc_data["openconfig-network-instance:network-instances"]):
            for (instance_index, instance) in enumerate(oc_data["openconfig-network-instance:network-instances"]
                                                        ["openconfig-network-instance:network-instance"]):
                if "openconfig-network-instance:interfaces" in instance:
                    temp_instance_interface_list = []

                    for interface in instance["openconfig-network-instance:interfaces"]["openconfig-network-instance:interface"]:
                        if found_full_match(interface["openconfig-network-instance:id"].split(".")[0], intf_dict):
                            temp_instance_interface_list.append(interface)

                    (data_out["mdd:openconfig"]["openconfig-network-instance:network-instances"]["openconfig-network-instance:network-instance"]
                     [instance_index]["openconfig-network-instance:interfaces"]["openconfig-network-instance:interface"]) = temp_instance_interface_list

        # Truncate network-instance MPLS interfaces
        if "openconfig-network-instance:network-instances" in oc_data and ("openconfig-network-instance:network-instance" in
                                                                           oc_data["openconfig-network-instance:network-instances"]):
            for (instance_index, instance) in enumerate(oc_data["openconfig-network-instance:network-instances"]
                                                        ["openconfig-network-instance:network-instance"]):
                if (len(instance.get("openconfig-network-instance:mpls", {})
                        .get("openconfig-network-instance:global", {})
                        .get("openconfig-network-instance:interface-attributes", {})
                        .get("openconfig-network-instance:interface", [])) > 0):
                    temp_mpls_interface_list = []

                    for interface in (instance["openconfig-network-instance:mpls"]["openconfig-network-instance:global"]
                                      ["openconfig-network-instance:interface-attributes"]["openconfig-network-instance:interface"]):
                        if found_full_match(interface["openconfig-network-instance:interface-id"].split(".")[0], intf_dict):
                            temp_mpls_interface_list.append(interface)

                    (data_out["mdd:openconfig"]["openconfig-network-instance:network-instances"]["openconfig-network-instance:network-instance"]
                     [instance_index]["openconfig-network-instance:mpls"]["openconfig-network-instance:global"]
                     ["openconfig-network-instance:interface-attributes"]["openconfig-network-instance:interface"]) = temp_mpls_interface_list

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
