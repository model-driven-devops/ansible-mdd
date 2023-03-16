# -*- coding: utf-8 -*-

# Copyright: (c) 2019. Chris Mills <chris@discreet-its.co.uk>
# GNU General Public License v3.0+
# (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
"""
netbox.py

A lookup function designed to return data from the NetBox application
"""

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = """
    name: netbox_oc
    author: Chris Mills (@cpmills1975)
    version_added: "0.1.0"
    short_description: Queries and returns elements from NetBox
    description:
        - Queries NetBox via its API to return virtually any information
          capable of being held in NetBox.
        - If wanting to obtain the plaintext attribute of a secret, I(private_key) or I(key_file) must be provided.
    options:
        _device:
            description:
                - The device name.
            required: True
        api_endpoint:
            description:
                - The URL to the NetBox instance to query
            env:
                # in order of precendence
                - name: NETBOX_API
                - name: NETBOX_URL
            required: True
        category:
            description:
                - The category to retrieve.
            required: False
        token:
            description:
                - The API token created through NetBox
                - This may not be required depending on the NetBox setup.
            env:
                # in order of precendence
                - name: NETBOX_TOKEN
                - name: NETBOX_API_TOKEN
            required: False
        validate_certs:
            description:
                - Whether or not to validate SSL of the NetBox instance
            required: False
            default: True
        private_key:
            description:
                - The private key as a string. Mutually exclusive with I(key_file).
            required: False
        key_file:
            description:
                - The location of the private key tied to user account. Mutually exclusive with I(private_key).
            required: False
    requirements:
        - pynetbox
"""

EXAMPLES = """
tasks:
  # query a list of devices
  - name: Obtain list of devices from NetBox
    debug:
      msg: >
        "Device {{ item.value.display_name }} (ID: {{ item.key }}) was
         manufactured by {{ item.value.device_type.manufacturer.name }}"
    loop: "{{ query('netbox.netbox.nb_lookup', 'devices',
                    api_endpoint='http://localhost/',
                    token='<redacted>') }}"

# This example uses an API Filter

tasks:
  # query a list of devices
  - name: Obtain list of devices from NetBox
    debug:
      msg: >
        "Device {{ item.value.display_name }} (ID: {{ item.key }}) was
         manufactured by {{ item.value.device_type.manufacturer.name }}"
    loop: "{{ query('netbox.netbox.nb_lookup', 'devices',
                    api_endpoint='http://localhost/',
                    api_filter='role=management tag=Dell'),
                    token='<redacted>') }}"
"""

RETURN = """
  _list:
    description:
      - list of composed dictionaries with key and value
    type: list
"""

import os
from pprint import pformat
from re import search, findall, IGNORECASE

from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase
from ansible.utils.display import Display
from ansible.module_utils.six import raise_from

try:
    import pynetbox
except ImportError as imp_exc:
    PYNETBOX_LIBRARY_IMPORT_ERROR = imp_exc
else:
    PYNETBOX_LIBRARY_IMPORT_ERROR = None

try:
    import requests
except ImportError as imp_exc:
    REQUESTS_LIBRARY_IMPORT_ERROR = imp_exc
else:
    REQUESTS_LIBRARY_IMPORT_ERROR = None


def get_endpoint(netbox, resource):
    """
    get_endpoint(netbox, resource)
        netbox: a predefined pynetbox.api() pointing to a valid instance
                of NetBox
        resource: the resource passed to the lookup function upon which the api
              call will be identified
    """

    netbox_endpoint_map = {
        "aggregates": {"endpoint": netbox.ipam.aggregates},
        "asns": {"endpoint": netbox.ipam.asns},
        "circuit-terminations": {"endpoint": netbox.circuits.circuit_terminations},
        "circuit-types": {"endpoint": netbox.circuits.circuit_types},
        "circuits": {"endpoint": netbox.circuits.circuits},
        "circuit-providers": {"endpoint": netbox.circuits.providers},
        "cables": {"endpoint": netbox.dcim.cables},
        "cluster-groups": {"endpoint": netbox.virtualization.cluster_groups},
        "cluster-types": {"endpoint": netbox.virtualization.cluster_types},
        "clusters": {"endpoint": netbox.virtualization.clusters},
        "config": {"endpoint": netbox.users.config},
        "config-contexts": {"endpoint": netbox.extras.config_contexts},
        "connected-device": {"endpoint": netbox.dcim.connected_device},
        "contact-assignments": {"endpoint": netbox.tenancy.contact_assignments},
        "contact-groups": {"endpoint": netbox.tenancy.contact_groups},
        "contact-roles": {"endpoint": netbox.tenancy.contact_roles},
        "contacts": {"endpoint": netbox.tenancy.contacts},
        "console-connections": {"endpoint": netbox.dcim.console_connections},
        "console-port-templates": {"endpoint": netbox.dcim.console_port_templates},
        "console-ports": {"endpoint": netbox.dcim.console_ports},
        "console-server-port-templates": {
            "endpoint": netbox.dcim.console_server_port_templates
        },
        "console-server-ports": {"endpoint": netbox.dcim.console_server_ports},
        "content-types": {"endpoint": netbox.extras.content_types},
        "custom-fields": {"endpoint": netbox.extras.custom_fields},
        "custom-links": {"endpoint": netbox.extras.custom_links},
        "device-bay-templates": {"endpoint": netbox.dcim.device_bay_templates},
        "device-bays": {"endpoint": netbox.dcim.device_bays},
        "device-roles": {"endpoint": netbox.dcim.device_roles},
        "device-types": {"endpoint": netbox.dcim.device_types},
        "devices": {"endpoint": netbox.dcim.devices},
        "export-templates": {"endpoint": netbox.dcim.export_templates},
        "fhrp-group-assignments": {"endpoint": netbox.ipam.fhrp_group_assignments},
        "fhrp-groups": {"endpoint": netbox.ipam.fhrp_groups},
        "front-port-templates": {"endpoint": netbox.dcim.front_port_templates},
        "front-ports": {"endpoint": netbox.dcim.front_ports},
        "graphs": {"endpoint": netbox.extras.graphs},
        "groups": {"endpoint": netbox.users.groups},
        "image-attachments": {"endpoint": netbox.extras.image_attachments},
        "interface-connections": {"endpoint": netbox.dcim.interface_connections},
        "interface-templates": {"endpoint": netbox.dcim.interface_templates},
        "interfaces": {"endpoint": netbox.dcim.interfaces},
        "inventory-items": {"endpoint": netbox.dcim.inventory_items},
        "ip-addresses": {"endpoint": netbox.ipam.ip_addresses},
        "ip-ranges": {"endpoint": netbox.ipam.ip_ranges},
        "job-results": {"endpoint": netbox.extras.job_results},
        "journal-entries": {"endpoint": netbox.extras.journal_entries},
        "locations": {"endpoint": netbox.dcim.locations},
        "manufacturers": {"endpoint": netbox.dcim.manufacturers},
        "object-changes": {"endpoint": netbox.extras.object_changes},
        "permissions": {"endpoint": netbox.users.permissions},
        "platforms": {"endpoint": netbox.dcim.platforms},
        "power-panels": {"endpoint": netbox.dcim.power_panels},
        "power-connections": {"endpoint": netbox.dcim.power_connections},
        "power-feeds": {"endpoint": netbox.dcim.power_feeds},
        "power-outlet-templates": {"endpoint": netbox.dcim.power_outlet_templates},
        "power-outlets": {"endpoint": netbox.dcim.power_outlets},
        "power-port-templates": {"endpoint": netbox.dcim.power_port_templates},
        "power-ports": {"endpoint": netbox.dcim.power_ports},
        "prefixes": {"endpoint": netbox.ipam.prefixes},
        "provider-networks": {"endpoint": netbox.circuits.provider_networks},
        "providers": {"endpoint": netbox.circuits.providers},
        "rack-groups": {"endpoint": netbox.dcim.rack_groups},
        "rack-reservations": {"endpoint": netbox.dcim.rack_reservations},
        "rack-roles": {"endpoint": netbox.dcim.rack_roles},
        "racks": {"endpoint": netbox.dcim.racks},
        "rear-port-templates": {"endpoint": netbox.dcim.rear_port_templates},
        "rear-ports": {"endpoint": netbox.dcim.rear_ports},
        "regions": {"endpoint": netbox.dcim.regions},
        "reports": {"endpoint": netbox.extras.reports},
        "rirs": {"endpoint": netbox.ipam.rirs},
        "roles": {"endpoint": netbox.ipam.roles},
        "route-targets": {"endpoint": netbox.ipam.route_targets},
        "secret-roles": {"endpoint": netbox.secrets.secret_roles},
        "secrets": {"endpoint": netbox.secrets.secrets},
        "services": {"endpoint": netbox.ipam.services},
        "site-groups": {"endpoint": netbox.dcim.site_groups},
        "sites": {"endpoint": netbox.dcim.sites},
        "tags": {"endpoint": netbox.extras.tags},
        "tenant-groups": {"endpoint": netbox.tenancy.tenant_groups},
        "tenants": {"endpoint": netbox.tenancy.tenants},
        "tokens": {"endpoint": netbox.users.tokens},
        "topology-maps": {"endpoint": netbox.extras.topology_maps},
        "users": {"endpoint": netbox.users.users},
        "virtual-chassis": {"endpoint": netbox.dcim.virtual_chassis},
        "virtual-machines": {"endpoint": netbox.virtualization.virtual_machines},
        "virtualization-interfaces": {"endpoint": netbox.virtualization.interfaces},
        "vlan-groups": {"endpoint": netbox.ipam.vlan_groups},
        "vlans": {"endpoint": netbox.ipam.vlans},
        "vrfs": {"endpoint": netbox.ipam.vrfs},
        "webhooks": {"endpoint": netbox.extras.webhooks},
    }

    major, minor, patch = map(int, pynetbox.__version__.split("."))

    if major >= 6 and minor >= 4 and patch >= 0:
        netbox_endpoint_map["wireless-lan-groups"] = {
            "endpoint": netbox.wireless.wireless_lan_groups
        }
        netbox_endpoint_map["wireless-lan-groups"] = {
            "endpoint": netbox.wireless.wireless_lan_groups
        }
        netbox_endpoint_map["wireless-lan"] = {"endpoint": netbox.wireless.wireless_lan}
        netbox_endpoint_map["wireless-links"] = {
            "endpoint": netbox.wireless.wireless_links
        }

    else:
        if "wireless" in resource:
            Display().v(
                "pynetbox version %d.%d.%d does not support wireless app; please update to v6.4.0 or newer."
                % (major, minor, patch)
            )

    return netbox_endpoint_map[resource]["endpoint"]


def get_interface_type(interface):
    # interface_type_map = {
    #     "virtual":"softwareLoopback",
    #     "lag":"ieee8023adLag"
    # }
    # if interface_type in interface_type_map:
    #     return interface_type_map[interface_type]
    # else:
    #     return "ethernetCsmacd"

    interface_type = interface["type"]["value"]

    if interface_type == "virtual":
        if search("vlan", interface["name"], IGNORECASE):
            return "l3ipvlan"
        elif search("loopback", interface["name"], IGNORECASE):
            return "softwareLoopback"
    # If this is a 'dot' subinterface
    elif search(r"\.", interface["name"]):
        return "ethernetCsmacd"
    elif interface_type == "lag":
        return "l2vlan"
    elif interface["mode"] is not None:
        if interface["mode"]["value"] == "tagged":
            return "l2vlan"
        if interface["mode"]["value"] == "access":
            return "l2vlan"
    else:
        return "ethernetCsmacd"


def make_netbox_call(nb_endpoint, filters=None):
    """
    Wrapper for calls to NetBox and handle any possible errors.

    Args:
        nb_endpoint (object): The NetBox endpoint object to make calls.

    Returns:
        results (object): Pynetbox result.

    Raises:
        AnsibleError: Ansible Error containing an error message.
    """
    try:
        if filters:
            results = nb_endpoint.filter(**filters)
        else:
            results = nb_endpoint.all()
    except pynetbox.RequestError as e:
        if e.req.status_code == 404 and "plugins" in e:
            raise AnsibleError(
                "{0} - Not a valid plugin endpoint, please make sure to provide valid plugin endpoint.".format(
                    e.error
                )
            )
        else:
            raise AnsibleError(e.error)

    return results


def interfaces_to_oc(interface_data, ipv4_by_intf, fhrp_by_intf):
    interface_dict = {}
    vrf_interfaces = {}

    oc_interfaces_data = {
        "openconfig-interfaces:interfaces": {
            "openconfig-interfaces:interface": []
        }
    }
    for interface in interface_data:
        # Derive the parent interface and index if exists
        interface_name = interface["name"]
        interface_name_parts = interface_name.split(".")
        interface_parent = interface_name_parts.pop(0)
        if interface_name_parts:
            interface_index = int(interface_name_parts.pop(0))
        else:
            interface_index = 0
        interface_type = get_interface_type(interface)

        # Use the description if it exists, otherwise, try to
        # create one
        if interface["description"]:
            interface_description = interface["description"]
        elif interface["connected_endpoint"] is not None:
            if interface["connected_endpoint"].get("device"):
                connected_device = interface["connected_endpoint"]["device"]["display"]
                connected_port = interface["connected_endpoint"]["display"]
                interface_description = "{0}:{1}".format(connected_device, connected_port)
        else:
            interface_description = ''

        # Create the interface list if it is not there
        if interface_parent not in interface_dict:
            interface_dict[interface_parent] = {
                "openconfig-interfaces:name": interface_parent,
                "openconfig-interfaces:config": {}
            }
        # If this is the parent, fill in the parent config
        if interface_index == 0:
            interface_dict[interface_name]["openconfig-interfaces:config"] = {
                "openconfig-interfaces:description": interface_description,
                "openconfig-interfaces:enabled": interface["enabled"],
                "openconfig-interfaces:name": interface_name,
                "openconfig-interfaces:type": interface_type
            }
        if interface["mtu"]:
            interface_dict[interface_name]["openconfig-interfaces:config"]["openconfig-interfaces:mtu"] = interface["mtu"]

        if interface_type in ["ethernetCsmacd", "softwareLoopback"] and (interface["count_ipaddresses"] > 0 or interface_index > 0):
            # This is a Layer 3 interface
            # Create the subinterface structure if it does not exist
            if not interface_dict[interface_parent].get("openconfig-interfaces:subinterfaces"):
                interface_dict[interface_parent]["openconfig-interfaces:subinterfaces"] = {
                    "openconfig-interfaces:subinterface": []
                }
            subinterface = {
                "openconfig-interfaces:index": interface_index,
                "openconfig-interfaces:config": {
                    "openconfig-interfaces:description": interface_description,
                    "openconfig-interfaces:enabled": interface["enabled"],
                    "openconfig-interfaces:index": interface_index,
                }
            }
        # Check to see if an IP address(s) exists for this interface
            if interface["id"] in ipv4_by_intf:
                subinterface["openconfig-if-ip:ipv4"] = {
                    "openconfig-if-ip:config": {
                        "openconfig-if-ip:dhcp-client": False,
                        "openconfig-if-ip:enabled": True
                    }
                }
                for id, value in ipv4_by_intf[interface["id"]].items():
                    # If this interface is configured for DHCP, set dhcp-client to True and skip IP address section
                    if value["status"]["value"] == "dhcp":
                        subinterface["openconfig-if-ip:ipv4"]["openconfig-if-ip:config"]["openconfig-if-ip:dhcp-client"] = True
                    else:
                        subinterface["openconfig-if-ip:ipv4"]["openconfig-if-ip:addresses"] = {
                            "openconfig-if-ip:address": []
                        }
                        ip_address, ip_prefix = value["address"].split("/")
                        address = {
                            "openconfig-if-ip:ip": ip_address,
                            "openconfig-if-ip:config": {
                                "openconfig-if-ip:ip": ip_address,
                                "openconfig-if-ip:prefix-length": ip_prefix
                            }

                        }
                        if interface["id"] in fhrp_by_intf:
                            vrrp = {
                                "openconfig-if-ip:vrrp": {
                                    "openconfig-if-ip:vrrp-group": []
                                }
                            }
                            for group_id, group in fhrp_by_intf[interface["id"]].items():
                                vip, vip_mask = group["ip_addresses"][0]["address"].split("/")
                                vrrp_group = {
                                    "openconfig-if-ip:virtual-router-id": group["group_id"],
                                    "openconfig-if-ip:config": {
                                        "openconfig-if-ip:priority": group["priority"],
                                        "openconfig-if-ip:virtual-address": [
                                            vip
                                        ],
                                        "openconfig-if-ip:virtual-router-id": group["group_id"]
                                    }
                                }
                                vrrp["openconfig-if-ip:vrrp"]["openconfig-if-ip:vrrp-group"].append(vrrp_group)
                            address.update(vrrp)
                            Display().vvvvv(pformat(address))
                        subinterface["openconfig-if-ip:ipv4"]["openconfig-if-ip:addresses"]["openconfig-if-ip:address"].append(address)
                    # If this IP address is in a VRF, then we need to contruct a list for later
                    if value["vrf"] is not None:
                        if value["vrf"]["name"] not in vrf_interfaces:
                            vrf_interfaces[value["vrf"]["name"]] = []
                        vrf_interface = {
                            "openconfig-network-instance:id": interface_name,
                            "openconfig-network-instance:interface": interface_parent,
                            "openconfig-network-instance:subinterface": interface_index
                        }
                        vrf_interfaces[value["vrf"]["name"]].append(vrf_interface)

                    if value["status"]["value"] == "dhcp":
                        subinterface["openconfig-if-ip:ipv4"]["openconfig-if-ip:config"]["openconfig-if-ip:dhcp-client"] = True

            if interface["untagged_vlan"] is not None:
                subinterface["openconfig-vlan:vlan"] = {
                    "openconfig-vlan:config": {
                        "openconfig-vlan:vlan-id": interface["untagged_vlan"]["vid"]
                    }
                }
            interface_dict[interface_parent]["openconfig-interfaces:subinterfaces"]["openconfig-interfaces:subinterface"].append(subinterface)
        elif interface_type == "l2vlan":
            interface_dict[interface_parent]["openconfig-interfaces:config"]["openconfig-interfaces:type"] = "l2vlan"
            interface_dict[interface_parent]["openconfig-if-ethernet:ethernet"] = {
                # "openconfig-vlan:config": {},
                "openconfig-vlan:switched-vlan": {}
            }
            switched_vlan = {
                "openconfig-vlan:config": {}
            }
            # This is a Layer 2 interface
            if interface["mode"]["value"] == "access":
                switched_vlan["openconfig-vlan:config"]["openconfig-vlan:interface-mode"] = "ACCESS"
                if interface["untagged_vlan"] is not None:
                    switched_vlan["openconfig-vlan:config"]["openconfig-vlan:access-vlan"] = interface["untagged_vlan"]["vid"]
            if interface["mode"]["value"] == "tagged":
                switched_vlan["openconfig-vlan:config"]["openconfig-vlan:interface-mode"] = "TRUNK"
                if interface["untagged_vlan"] is not None:
                    switched_vlan["openconfig-vlan:config"]["openconfig-vlan:native-vlan"] = interface["untagged_vlan"]["vid"]
                if interface["tagged_vlans"] is not None:
                    allowed_vlans = []
                    for vlan in interface["tagged_vlans"]:
                        allowed_vlans.append(str(vlan["vid"]))
                    switched_vlan["openconfig-vlan:config"]["openconfig-vlan:trunk-vlans"] = allowed_vlans
            interface_dict[interface_parent]["openconfig-if-ethernet:ethernet"]["openconfig-vlan:switched-vlan"] = switched_vlan
        elif interface_type == "l3ipvlan":
            interface_dict[interface_parent]["openconfig-interfaces:config"]["openconfig-interfaces:type"] = "l3ipvlan"
            # interface_dict[interface_parent]["openconfig-if-ethernet:ethernet"] = {
            #     # "openconfig-vlan:config": {},
            #     "openconfig-vlan:routed-vlan": {}
            # }
            routed_vlan = {
                "openconfig-vlan:config": {},
                "openconfig-if-ip:ipv4": {}
            }
            if interface["untagged_vlan"] is not None:
                routed_vlan["openconfig-vlan:config"] = {
                    "vlan": interface["untagged_vlan"]["vid"]
                }
            else:
                vid = findall(r'\d+', interface["name"])
                if vid != "":
                    routed_vlan["openconfig-vlan:config"] = {
                        "vlan": vid[0]
                    }
            if interface["id"] in ipv4_by_intf:
                routed_vlan["openconfig-if-ip:ipv4"] = {
                    "openconfig-if-ip:config": {
                        "openconfig-if-ip:dhcp-client": False,
                        "openconfig-if-ip:enabled": True
                    },
                    "openconfig-if-ip:addresses": {
                        "openconfig-if-ip:address": []
                    }
                }
                for id, value in ipv4_by_intf[interface["id"]].items():
                    ip_address, ip_prefix = value["address"].split("/")
                    address = {
                        "openconfig-if-ip:ip": ip_address,
                        "openconfig-if-ip:config": {
                            "openconfig-if-ip:ip": ip_address,
                            "openconfig-if-ip:prefix-length": ip_prefix
                        }
                    }
                    routed_vlan["openconfig-if-ip:ipv4"]["openconfig-if-ip:addresses"]["openconfig-if-ip:address"].append(address)
                    # If this IP address is in a VRF, then we need to contruct a list for later
                    if value["vrf"] is not None:
                        if value["vrf"]["name"] not in vrf_interfaces:
                            vrf_interfaces[value["vrf"]["name"]] = []
                        vrf_interface = {
                            "openconfig-network-instance:id": interface_name,
                            "openconfig-network-instance:interface": interface_parent,
                            "openconfig-network-instance:subinterface": interface_index
                        }
                        vrf_interfaces[value["vrf"]["name"]].append(vrf_interface)
            interface_dict[interface_parent]["openconfig-vlan:routed-vlan"] = routed_vlan
    # Need to take the dict and make it into a list
    for key, value in interface_dict.items():
        oc_interfaces_data["openconfig-interfaces:interfaces"]["openconfig-interfaces:interface"].append(value)
    # Process the VRF interface structure that was created earlier
    if vrf_interfaces:
        oc_interfaces_data["openconfig-network-instance:network-instances"] = {
            "openconfig-network-instance:network-instance": []
        }
        for vrf, interfaces in vrf_interfaces.items():
            vrf_instance = {
                "openconfig-network-instance:name": vrf,
                "openconfig-network-instance:config": {
                    "openconfig-network-instance:name": vrf,
                    "openconfig-network-instance:type": 'L3VRF',
                    "openconfig-network-instance:enabled": True,
                    "openconfig-network-instance:enabled-address-families": [
                        "IPV4",
                        "IPV6"
                    ]
                },
                "openconfig-network-instance:interfaces": {
                    "openconfig-network-instance:interface": []
                }
            }
            for interface in interfaces:
                vrf_instance_interfaces = {
                    "openconfig-network-instance:id": interface["openconfig-network-instance:id"],
                    "openconfig-network-instance:config": interface
                }
                vrf_instance["openconfig-network-instance:interfaces"]["openconfig-network-instance:interface"].append(vrf_instance_interfaces)
            oc_interfaces_data["openconfig-network-instance:network-instances"]["openconfig-network-instance:network-instance"].append(vrf_instance)
    return oc_interfaces_data


class LookupModule(LookupBase):
    """
    LookupModule(LookupBase) is defined by Ansible
    """

    def run(self, terms, variables=None, **kwargs):
        if PYNETBOX_LIBRARY_IMPORT_ERROR:
            raise_from(
                AnsibleError("pynetbox must be installed to use this plugin"),
                PYNETBOX_LIBRARY_IMPORT_ERROR,
            )

        if REQUESTS_LIBRARY_IMPORT_ERROR:
            raise_from(
                AnsibleError("requests must be installed to use this plugin"),
                REQUESTS_LIBRARY_IMPORT_ERROR,
            )

        netbox_api_token = (
            kwargs.get("token")
            or os.getenv("NETBOX_TOKEN")
            or os.getenv("NETBOX_API_TOKEN")
        )
        netbox_api_endpoint = (
            kwargs.get("api_endpoint")
            or os.getenv("NETBOX_API")
            or os.getenv("NETBOX_URL")
        )
        netbox_ssl_verify = kwargs.get("validate_certs", True)
        netbox_private_key = kwargs.get("private_key")
        netbox_private_key_file = kwargs.get("key_file")
        netbox_api_filter = kwargs.get("api_filter")
        netbox_device = terms.pop()
        resources = ['interfaces']

        if not isinstance(resources, list):
            resources = [resources]

        try:
            session = requests.Session()
            session.verify = netbox_ssl_verify

            netbox = pynetbox.api(
                netbox_api_endpoint,
                token=netbox_api_token if netbox_api_token else None,
                private_key=netbox_private_key,
                private_key_file=netbox_private_key_file,
            )
            netbox.http_session = session
        except FileNotFoundError:
            raise AnsibleError(
                "%s cannot be found. Please make sure file exists."
                % netbox_private_key_file
            )

        oc_data = {}
        results = []
        for resource in resources:
            try:
                endpoint = get_endpoint(netbox, resource)
            except KeyError:
                raise AnsibleError(
                    "Unrecognised resource %s. Check documentation" % resource
                )

            Display().vvvv(
                "NetBox lookup for %s to %s using token %s device %s"
                % (resource, netbox_api_endpoint, netbox_api_token, netbox_device)
            )

            filter = {"device": [netbox_device]}
            Display().vvvv("filter is %s" % filter)

            # Make call to NetBox API and capture any failures
            nb_data = make_netbox_call(endpoint, filters=filter)

            for data in nb_data:
                data = dict(data)
                Display().vvvvv(pformat(data))
                results.append(data)

            if resource == "interfaces":
                # If we are getting interfaces, we also need to get ip-addresses and fhrp-groups
                ipv4_by_intf = {}
                ipv6_by_intf = {}
                ipaddresses_by_id = {}
                endpoint = get_endpoint(netbox, "ip-addresses")
                ipaddresses = make_netbox_call(endpoint, filters=filter)
                for ipaddress in ipaddresses:
                    ipaddress = dict(ipaddress)
                    interface_id = None
                    Display().vvvvv(pformat(ipaddress))
                    if ipaddress.get("assigned_object_id"):
                        interface_id = ipaddress["assigned_object_id"]
                        ip_id = ipaddress["id"]
                    elif ipaddress.get("interface"):
                        interface_id = ipaddress["interface"]["id"]
                    if interface_id is not None:
                        ip_id = ipaddress["id"]
                        # We need to copy the ipaddress entry to preserve the original in case caching is used.
                        ipaddress_copy = ipaddress.copy()
                        ipaddresses_by_id[ip_id] = ipaddress_copy
                        if ipaddress["family"] == 6:
                            if interface_id not in ipv6_by_intf:
                                ipv6_by_intf[interface_id] = {}
                            ipv6_by_intf[interface_id][ip_id] = ipaddress_copy
                        else:
                            if interface_id not in ipv4_by_intf:
                                ipv4_by_intf[interface_id] = {}
                            ipv4_by_intf[interface_id][ip_id] = ipaddress_copy

                fhrp_by_intf = {}
                endpoint = get_endpoint(netbox, "fhrp-group-assignments")
                group_assignments = make_netbox_call(endpoint, filters=filter)
                for group_assignment in group_assignments:
                    group_assignment = dict(group_assignment)
                    if group_assignment.get("interface_id"):
                        interface_id = group_assignment["interface_id"]
                    if interface_id is not None:
                        group_id = group_assignment["group"]["group_id"]
                        if interface_id not in fhrp_by_intf:
                            fhrp_by_intf[interface_id] = {}
                        fhrp_by_intf[interface_id].update({group_id: {"priority": group_assignment["priority"]}})
                endpoint = get_endpoint(netbox, "fhrp-groups")
                fhrp_groups = make_netbox_call(endpoint, filters=filter)
                for fhrp_group in fhrp_groups:
                    fhrp_group = dict(fhrp_group)
                    if fhrp_group.get("group_id"):
                        for id in fhrp_by_intf.keys():
                            for group_id in fhrp_by_intf[id].keys():
                                if fhrp_group["group_id"] == group_id:
                                    fhrp_group_copy = fhrp_group.copy()
                                    fhrp_by_intf[id][group_id].update(fhrp_group_copy)
                oc_data.update(interfaces_to_oc(results, ipv4_by_intf, fhrp_by_intf))
        return oc_data
