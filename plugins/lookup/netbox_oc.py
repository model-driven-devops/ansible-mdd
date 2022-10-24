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
import functools
from pprint import pformat

from ansible.errors import AnsibleError
from ansible.plugins.lookup import LookupBase
from ansible.parsing.splitter import parse_kv, split_args
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


def get_interface_type(interface_type):
    interface_type_map = {
        "virtual": "softwareLoopback",
        "lag": "ieee8023adLag"
    }
    if interface_type in interface_type_map:
        return interface_type_map[interface_type]
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


def interfaces_to_oc(interface_data, ipv4_by_intf):
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
        interface_type = get_interface_type(interface["type"]["value"])

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
                "config": {},
                "name": interface_parent
            }
        # If this is the parent, fill in the parent config
        if interface_index == 0:
            interface_dict[interface_name]["config"] = {
                "description": interface_description,
                "enabled": interface["enabled"],
                "name": interface_name,
                "type": interface_type
            }
        if interface["mtu"]:
            interface_dict[interface_name]["config"]["mtu"] = interface["mtu"]

        if interface["count_ipaddresses"] > 0 or interface_index > 0:
            # This is a Layer 3 interface
            # Create the subinterface strcuture if it does not exist
            if not interface_dict[interface_parent].get("subinterfaces"):
                interface_dict[interface_parent]["subinterfaces"] = {
                    "subinterface": []
                }
            subinterface = {
                "config": {
                    "description": interface_description,
                    "enabled": interface["enabled"],
                    "index": interface_index,
                },
                "index": interface_index
            }
            # Check to see if an IP address(s) exists for this interface
            if interface["id"] in ipv4_by_intf:
                subinterface["openconfig-if-ip:ipv4"] = {
                    "config": {
                        "dhcp-client": False,
                        "enabled": True
                    },
                    "addresses": {
                        "address": []
                    }
                }
                for id, value in ipv4_by_intf[interface["id"]].items():
                    ip_address, ip_prefix = value["address"].split("/")
                    address = {
                        "config": {
                            "ip": ip_address,
                            "prefix-length": ip_prefix
                        },
                        "ip": ip_address
                    }
                    subinterface["openconfig-if-ip:ipv4"]["addresses"]["address"].append(address)
                    # If this IP address is in a VRF, then we need to contruct a list for later
                    if value["vrf"] is not None:
                        if value["vrf"]["name"] not in vrf_interfaces:
                            vrf_interfaces[value["vrf"]["name"]] = []
                        vrf_interface = {
                            "id": interface_name,
                            "interface": interface_parent,
                            "subinterface": interface_index
                        }
                        vrf_interfaces[value["vrf"]["name"]].append(vrf_interface)

            if interface["untagged_vlan"] is not None:
                subinterface["openconfig-vlan:vlan"] = {
                    "config": {
                        "vlan-id": interface["untagged_vlan"]["vid"]
                    }
                }
            interface_dict[interface_parent]["subinterfaces"]["subinterface"].append(subinterface)
        elif interface["mode"]:
            interface_dict[interface_parent]["config"]["type"] = "l2vlan"
            interface_dict[interface_parent]["openconfig-if-ethernet:ethernet"] = {
                "config": {},
                "openconfig-vlan:switched-vlan": {}
            }
            switched_vlan = {
                "config": {}
            }
            # This is a Layer 2 interface
            if interface["mode"]["value"] == "access":
                switched_vlan["config"]["interface-mode"] = "ACCESS"
                if interface["untagged_vlan"] is not None:
                    switched_vlan["config"]["access-vlan"] = interface["untagged_vlan"]["vid"]
            if interface["mode"]["value"] == "tagged":
                switched_vlan["config"]["interface-mode"] = "TRUNK"
                if interface["untagged_vlan"] is not None:
                    switched_vlan["config"]["native-vlan"] = interface["untagged_vlan"]["vid"]
                if interface["tagged_vlans"] is not None:
                    allowed_vlans = []
                    for vlan in interface["tagged_vlans"]:
                        allowed_vlans.append(str(vlan["vid"]))
                    switched_vlan["config"]["trunk-vlans"] = allowed_vlans
            interface_dict[interface_parent]["openconfig-if-ethernet:ethernet"]["openconfig-vlan:switched-vlan"] = switched_vlan
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
                "name": vrf,
                "config": {
                    "name": vrf,
                    "type": 'L3VRF',
                    "enabled": True,
                    "enabled-address-families": [
                        "IPV4"
                    ]
                },
                "interfaces": {
                    "interface": []
                }
            }
            for interface in interfaces:
                vrf_instance_interfaces = {
                    "id": interface["id"],
                    "config": interface
                }
                vrf_instance["interfaces"]["interface"].append(vrf_instance_interfaces)
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
                # If we are getting interfaces, we also need to get ip-addresses
                ipv4_by_intf = {}
                ipv6_by_intf = {}
                ipaddresses_by_id = {}
                endpoint = get_endpoint(netbox, "ip-addresses")
                ipaddresses = make_netbox_call(endpoint, filters=filter)
                for ipaddress in ipaddresses:
                    ipaddress = dict(ipaddress)
                    Display().vvvvv(pformat(ipaddress))
                    if ipaddress.get("assigned_object_id"):
                        interface_id = ipaddress["assigned_object_id"]
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
                oc_data.update(interfaces_to_oc(results, ipv4_by_intf))

        return oc_data
