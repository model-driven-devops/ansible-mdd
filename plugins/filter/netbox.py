from __future__ import absolute_import, division, print_function
__metaclass__ = type


def netbox_intf_to_oc(netbox_interfaces):
    interface_dict = {}
    oc_data = {
        'openconfig-interfaces:interfaces': {}
    }
    for interface in netbox_interfaces:
        interface_name = interface["value"]["name"].split(".")
        # Create the interface list if it is not there
        if not interface_dict.get(interface_name[0]):
            interface_dict[interface_name[0]] = {
                "config": {},
                "name": interface_name[0]
            }
        # If this is the parent, fill in the parent config
        if len(interface_name) == 1:
            interface_dict[interface_name[0]]["config"] = {
                "description": interface["value"]["description"],
                "enabled": interface["value"]["enabled"],
                "name": interface_name[0],
                "type": "ethernetCsmacd"
            }
        # This is a Subinterface
        elif len(interface_name) == 2:
            subinterface = {
                "config": {
                    "description": interface["value"]["description"],
                    "enabled": interface["value"]["enabled"],
                    "index": interface_name[1],
                },
                "index": interface_name[1]
            }
            if not interface_dict[interface_name[0]].get("subinterfaces"):
                interface_dict[interface_name[0]]["subinterfaces"] = {
                    "subinterface": []
                }
            interface_dict[interface_name[0]]["subinterfaces"]["subinterface"].append(subinterface)

    return interface_dict


class FilterModule(object):
    def filters(self):
        return {
            'netbox_intf_to_oc': netbox_intf_to_oc
        }
