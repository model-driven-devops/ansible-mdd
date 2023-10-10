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
    "openconfig-network-instance:local-address",
    "openconfig-system-ext:track-interface"
]


def found_full_match(string, intf_dict):
    for pattern in intf_dict:
        if bool(re.fullmatch(pattern, string)):
            return pattern

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


def intf_xlate(data, intf_dict=None):
    if not data:
        return {}

    if intf_dict is None:
        return data

    data_out = data.copy()
    xlate_value(data_out, intf_dict)

    return data_out


def intf_truncate(data, intf_dict=None):
    if not data:
        return {}

    if intf_dict is None:
        return data

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
                            # temp_ospf_interface_list = []
                            for (area_index, area) in enumerate(protocol["openconfig-network-instance:ospfv2"]["openconfig-network-instance:areas"]
                                                                ["openconfig-network-instance:area"]):
                                temp_ospf_interface_list = []
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

        # Truncate openconfig-acl interfaces
        if "openconfig-acl:acl" in oc_data and "openconfig-acl:interfaces" in oc_data["openconfig-acl:acl"]:
            temp_acl_interface_list = []
            for interface in oc_data["openconfig-acl:acl"]["openconfig-acl:interfaces"]["openconfig-acl:interface"]:
                if found_full_match(interface["openconfig-acl:id"].split(".")[0], intf_dict):
                    temp_acl_interface_list.append(interface)

            data_out["mdd:openconfig"]["openconfig-acl:acl"]["openconfig-acl:interfaces"]["openconfig-acl:interface"] = temp_acl_interface_list

    return data_out


def vlan_truncate(data, vlan_list=None):
    if not data:
        return {}

    if vlan_list is None:
        return data

    data_out = data.copy()

    if "mdd:openconfig" in data:
        oc_data = data["mdd:openconfig"]

        # Truncate VLANs from network instances
        try:
            instances = oc_data["openconfig-network-instance:network-instances"]["openconfig-network-instance:network-instance"]
            for (instance_index, instance) in enumerate(instances):
                temp_vlan_list = []
                try:
                    vlans = instance["openconfig-network-instance:vlans"]["openconfig-network-instance:vlan"]
                    for vlan in vlans:
                        if vlan["openconfig-network-instance:vlan-id"] in vlan_list:
                            temp_vlan_list.append(vlan)
                    (data_out["mdd:openconfig"]["openconfig-network-instance:network-instances"]["openconfig-network-instance:network-instance"]
                     [instance_index]["openconfig-network-instance:vlans"]["openconfig-network-instance:vlan"]) = temp_vlan_list
                except KeyError:
                    pass
        except KeyError:
            pass

        # Truncate VLANs from STP
        try:
            rapid_pvst = oc_data["openconfig-spanning-tree:stp"]["openconfig-spanning-tree:rapid-pvst"]
            try:
                temp_stp_vlan_list = []
                vlans = rapid_pvst["openconfig-spanning-tree:vlan"]
                for vlan in vlans:
                    if vlan["openconfig-spanning-tree:vlan-id"] in vlan_list:
                        temp_stp_vlan_list.append(vlan)
                (data_out["mdd:openconfig"]["openconfig-spanning-tree:stp"]["openconfig-spanning-tree:rapid-pvst"]
                 ["openconfig-spanning-tree:vlan"]) = temp_stp_vlan_list
            except KeyError:
                pass
        except KeyError:
            pass

        # Truncate VLANs from trunk interfaces
        try:
            interfaces = oc_data["openconfig-interfaces:interfaces"]["openconfig-interfaces:interface"]
            for interface_index, interface in enumerate(interfaces):
                # Check port-channel interfaces
                try:
                    temp_allowed_vlan_list = []
                    allowed_vlans = (interface["openconfig-if-aggregate:aggregation"]["openconfig-vlan:switched-vlan"]
                                     ["openconfig-vlan:config"]["openconfig-vlan:trunk-vlans"])
                    for vlan in allowed_vlans:
                        if vlan in vlan_list:
                            temp_allowed_vlan_list.append(vlan)
                    (data_out["mdd:openconfig"]["openconfig-interfaces:interfaces"]["openconfig-interfaces:interface"][interface_index]
                     ["openconfig-if-aggregate:aggregation"]["openconfig-vlan:switched-vlan"]["openconfig-vlan:config"]
                     ["openconfig-vlan:trunk-vlans"]) = temp_allowed_vlan_list
                except KeyError:
                    pass

                # Check physical interfaces
                try:
                    temp_allowed_vlan_list = []
                    allowed_vlans = (interface["openconfig-if-ethernet:ethernet"]["openconfig-vlan:switched-vlan"]
                                     ["openconfig-vlan:config"]["openconfig-vlan:trunk-vlans"])
                    for vlan in allowed_vlans:
                        if vlan in vlan_list:
                            temp_allowed_vlan_list.append(vlan)
                    (data_out["mdd:openconfig"]["openconfig-interfaces:interfaces"]["openconfig-interfaces:interface"][interface_index]
                     ["openconfig-if-ethernet:ethernet"]["openconfig-vlan:switched-vlan"]["openconfig-vlan:config"]
                     ["openconfig-vlan:trunk-vlans"]) = temp_allowed_vlan_list
                except KeyError:
                    pass

        except KeyError:
            pass

    return data_out


def delete_key(data, key_list):
    if isinstance(data, dict):
        if key_list[0] in list(data):
            if len(key_list) == 1:
                del data[key_list[0]]
            else:
                key = key_list.pop(0)
                delete_key(data[key], key_list)


def config_truncate(data, truncate_list=None):
    """Find all values from a nested dictionary for a given key."""

    if not data:
        return {}

    if truncate_list is None:
        return data

    data_out = data.copy()

    for path in truncate_list:
        delete_key(data_out, path)
    return data_out


def config_xform(data, intf_dict=None, truncate_list=None, vlan_list=None):
    data = intf_truncate(data, intf_dict)
    data = intf_xlate(data, intf_dict)
    data = config_truncate(data, truncate_list)
    data = vlan_truncate(data, vlan_list)
    return data


class FilterModule(object):

    def filters(self):
        return {
            'intf_xlate': intf_xlate,
            'intf_truncate': intf_truncate,
            'config_xform': config_xform
        }
