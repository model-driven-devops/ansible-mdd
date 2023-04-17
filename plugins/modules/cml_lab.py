#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2017 Cisco and/or its affiliates.
#
# This file is part of Ansible
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

ANSIBLE_METADATA = {'metadata_version': '1.1', 'status': ['preview'], 'supported_by': 'community'}


DOCUMENTATION = r"""
---
module: cml_lab
short_description: Generate a CML lab file from devices in NSO
description:
  - Generate a CML lab file from devices in NSO
author:
  - Steven Mosher (@stmosher)
  - Jason King (@jasonkin)
requirements:
  - copy
version_added: '1.2.0'
options:
    devices:
        description: The devices used to build the topology
        required: true
        type: list
        elements: dict
    ext_conn:
        description: Whether to add external connectors to lab
        required: false
        type: bool
        default: true
    start_from:
        description: Which physical interface to start mapping to simulated interface
        required: false
        type: int
        default: 2
"""

EXAMPLES = r"""
- name: Build the topology
  hosts: localhost
  gather_facts: no
  tasks:
    - name: Build the topology
      ciscops.mdd.generate_topology:
        devices: "{{ devices }}"
      register: topology
"""

import copy
from ansible.module_utils.basic import AnsibleModule

interface_types_list = ["Fas", "Ten", "Gig"]
device_template = {
    "switch": {
        "node_definition": "iosvl2",
        "ram": 768,
        "tags": ["switch"],
        "y": 0,
        "type": "switch"
    },
    "router": {
        "node_definition": "csr1000v",
        "ram": 3072,
        "tags": ["router"],
        "y": 0,
        "type": "router"
    },
    "l3switch": {
        "node_definition": "Cat9000v",
        "image_definition": "Cat9k",
        "ram": 18432,
        "cpus": 4,
        "tags": ["l3switch"],
        "y": 0,
        "type": "l3switch"
    },
    "ext_conn": {
        "node_definition": "external_connector",
        "ram": 0,
        "tags": [],
        "y": 0
    },
}

default_mappings = {
    "Loopback(\\d+)": "Loopback\\1",
    "Vlan(\\d+)": "Vlan\\1"
}


def create_node(node_input):
    device = {
        "boot_disk_size": 0,
        "configuration": node_input["configuration"],
        "cpu_limit": 100,
        "cpus": node_input.get("cpus", 1),
        "data_volume": 0,
        "hide_links": False,
        "id": node_input["id"],
        "label": node_input["hostname"],
        "node_definition": node_input["node_definition"],
        "ram": node_input["ram"],
        "tags": node_input["tags"],
        "x": node_input["x_position"],
        "y": node_input.get("y_position", 0),
        "interfaces": [
            {
                "id": "i0",
                "label": "Loopback0",
                "type": "loopback"
            }
        ]
    }
    if node_input.get("image_definition"):
        device["image_definition"] = node_input.get("image_definition")
    return device


def switch_generate_interface(c, m, s):
    """
    Increments module and interface numbering for switches using modules of 4 interfaces, e.g.
        Gig0/0, Gig0/1, Gig0/2, Gig0/3, Gig1/0...
    :param c: int, interface number
    :param m: int, module number
    :param s: int, CML topo slot number
    :return: tuple, if-counter, module number, slot number
    """
    if c == 3:
        m += 1
        c = 0
    else:
        c += 1
    s += 1
    return c, m, s


def add_interfaces_to_topology(topo_node, device_info, physical_interfaces):
    """
    Adds interfaces to the devices in the CML topology
    """
    number_of_interfaces = len(physical_interfaces) + 3  # initial + 2 spares
    number_of_interfaces += 4 - (number_of_interfaces % 4)  # interfaces come in sets of 4
    if device_info["type"] == "l3switch":
        topo_node["interfaces"].append({
            "id": "i1",
            "label": "GigabitEthernet0/0",
            "slot": 0,
            "type": "physical"
        })
        counter = 1
        for i in range(24):
            topo_node["interfaces"].append({
                "id": "i{0}".format(counter + 1),
                "label": "GigabitEthernet1/0/{0}".format(counter),
                "slot": counter,
                "type": "physical"
            })
            counter += 1
    elif device_info["type"] == "switch":
        slot = 0
        mod = 0
        counter = 0
        if_id = 1
        for i in range(number_of_interfaces):
            topo_node["interfaces"].append({
                "id": "i{0}".format(if_id),
                "label": "GigabitEthernet{0}/{1}".format(mod, counter),
                "slot": slot,
                "type": "physical"
            })
            counter, mod, slot = switch_generate_interface(counter, mod, slot)
            if_id += 1
    elif device_info["type"] == "router":
        slot = 0
        counter = 1
        for i in range(number_of_interfaces):
            topo_node["interfaces"].append({
                "id": "i{0}".format(counter),
                "label": "GigabitEthernet{0}".format(counter),
                "slot": slot,
                "type": "physical"
            })
            slot += 1
            counter += 1


def map_physical_interfaces_to_logical_interfaces(topo_node, physical_interfaces, start_from):
    """
    Creates a dict of devices with dicts of interfaces with dicts of physical interface names containing dicts of
    virtual interfaces and ids. Device dict also contains node-id, e.g.
    {'Router-01': {'interfaces': {'Gig0': {'if-name': 'GigabitEthernet2', 'id': 'i2'},
    'Gig0/0/0': {'if-name': 'GigabitEthernet3', 'id': 'i3'},
    'Gig0/0/1': {'if-name': 'GigabitEthernet4', 'id': 'i4'}},
    'node_id': 'n0'}
    :param topo_node:
    :param physical_interfaces:
    :return: dict
    """
    mapping = {}

    # Find mgmt interface and make sure we map that as well
    for interface in topo_node["interfaces"]:
        if interface["id"] == "i1":
            mapping[interface["label"]] = {"if-name": interface["label"], "id": interface["id"]}
    for i in range(len(physical_interfaces)):
        mapping[physical_interfaces[i]] = {"if-name": topo_node["interfaces"][start_from + i]["label"],
                                           "id": topo_node["interfaces"][start_from + i]["id"]}
    return mapping


def cml_topology_create_initial(devices_with_interface_dict, remote_device_info_full, start_from):
    """
    Creates CML topology file and adds nodes
    :param devices_with_interface_dict:
    :param remote_device_info_full:
    :return:
    """
    mappings = {}
    topology = {
        "lab": {
            "description": "",
            "notes": "",
            "title": "generated_lab",
            "version": "0.1.0"
        },
        "links": [],
        "nodes": []
    }
    node_counter = 0
    x_position = 0
    for device in devices_with_interface_dict:
        configs = {
            "router": '''
hostname {0}
!
vrf definition Mgmt-intf
 address-family ipv4
 exit-address-family
!
ip domain name mdd.cisco.com
!
crypto key generate rsa modulus 2048
!
username admin privilege 15 secret 0 admin
!
interface GigabitEthernet1
 vrf forwarding Mgmt-intf
 ip address dhcp
 no shutdown
!
ip ssh time-out 60
ip ssh authentication-retries 2
!
line con 0
line aux 0
line vty 0 4
 login local
 transport input ssh
 exec-timeout 0 0
 exit
netconf ssh
end
'''.format(device),
            "switch": '''
"hostname {0}
!
vrf definition Mgmt-intf
 address-family ipv4
 exit-address-family
!
ip domain name mdd.cisco.com
!
crypto key generate rsa modulus 2048
!
username admin privilege 15 secret 0 admin
!
interface GigabitEthernet0/0
 no switchport
 vrf forwarding Mgmt-intf
 ip address dhcp
 no shutdown
!
interface GigabitEthernet0/1
 no switchport
!
interface GigabitEthernet0/2
 no switchport
!
interface GigabitEthernet0/3
 no switchport
!
interface GigabitEthernet1/0
 no switchport
!
interface GigabitEthernet1/1
 no switchport
!
interface GigabitEthernet1/2
 no switchport
!
interface GigabitEthernet1/3
 no switchport
!
no ip http server
no ip http secure-server
ip ssh time-out 60
ip ssh authentication-retries 2
!
line con 0
line aux 0
line vty 0 4
 login local
 transport input ssh
 exec-timeout 0 0
 exit
 netconf ssh
 end"
'''.format(device),
            "l3switch": '''
hostname {0}
!
vrf definition Mgmt-intf
!
 address-family ipv4
 exit-address-family
!
ip domain name mdd.cisco.com
!
crypto key generate rsa modulus 2048
!
enable secret 0 Xcisco1234
!
username admin privilege 15 secret 0 admin
!
interface GigabitEthernet0/0
 no switchport
 vrf forwarding Mgmt-intf
 ip address dhcp
 no shutdown
!
interface GigabitEthernet1/0/1-24
 no switchport
!
no ip http server
no ip http secure-server
ip ssh time-out 60
ip ssh authentication-retries 2
!
ip ssh version 2
!
ip ssh server algorithm mac hmac-sha1 hmac-sha2-256 hmac-sha2-512
ip ssh server algorithm kex diffie-hellman-group14-sha1
!
line con 0
line aux 0
line vty 0 4
 login local
 transport input ssh
 exec-timeout 0 0
 exit
netconf ssh
ip routing
license boot level network-advantage addon dna-advantage
license boot level network-advantage
end
'''.format(device)
        }
        device_type = remote_device_info_full.get(device, {}).get("type", "router")
        device_info = copy.deepcopy(device_template.get(device_type))
        device_info["hostname"] = device
        device_info["x_position"] = x_position
        device_info["id"] = "n{0}".format(node_counter)
        device_info["configuration"] = configs[device_type]
        node_counter += 1
        x_position += 150
        topo_node = create_node(device_info)
        add_interfaces_to_topology(topo_node, device_info, devices_with_interface_dict[device])
        physical_virtual_map = map_physical_interfaces_to_logical_interfaces(topo_node,
                                                                             devices_with_interface_dict[device],
                                                                             start_from)
        mappings.update({device: {"interfaces": physical_virtual_map,
                                  "node_id": device_info["id"]}})
        topology["nodes"].append(topo_node)

    return topology, mappings


def find_capabilities(device, cdp_line):
    """
    Find capabilites advertised from the remote device. Used to find the best CML image
    :param device:
    :param cdp_line:
    :return: dict of {remote_name, {"platform": hw_platform, "type": ("switch", "router", or "l3switch")}
    """
    rev = copy.deepcopy(cdp_line)
    rev.reverse()
    capabilities = []
    for r in rev[3:]:
        if r.isdigit():
            break
        else:
            if r == "R" or r == "S":
                capabilities.append(r)
    if "R" in capabilities and "S" in capabilities:
        # For now, set this to switch.  Once cat9kv is available, set to l3switch
        # device_type = "l3switch"
        device_type = "switch"
    elif "R" in capabilities:
        device_type = "router"
    elif "S" in capabilities:
        device_type = "switch"
    else:
        device_type = None
    platform = cdp_line[-3]
    return {device: {"platform": platform, "type": device_type}}


def parse_cdp_output(cdp_data, dev, devices):
    """
    Find local interface, remote name, remote interface, remote platform, remote capabilities

    return tuple
        [0] links, e.g.
            [{
            "router1": "Ten1/2,
            "router2": "Ten1/1",
            }]
        [1]ldict of devices, platform, and capabilities to be used
        [{"router10": {"platform": "c6509", "type": "l3switch"}}
    """
    device_links_list = []
    device_info = {}
    cdp_split = cdp_data.split('\r\n')  # split all csv data on carriage returns
    cdp_split.pop(0)  # RESTCONF results has an extra blank line
    # Find the first break list index
    for c, i in enumerate(cdp_split):
        if len(i.split()) == 0:
            index = cdp_split.index(i)
            break

    index = index + 2  # skip to first device name

    # new_list = [a for a in cdp_split[index:]]  # break single csv line into elements
    new_list = list(cdp_split[index:])  # break single csv line into elements

    for i in new_list:
        if len(i.split()) == 1 and "." in i.split()[0]:  # a line with only a name
            remote = i.split('.')[0]
        elif len(i.split()) == 1:
            remote = i.split()[0]
        elif len(i.split()) == 0:  # blank line is end of cdp neighbors
            break
        if i.split()[-1] == "eth0":  # not adding hosts
            pass
        elif len(i.split()) > 1 and i.split()[1] in interface_types_list:  # in case hostname is in line with data
            if "." in i.split()[0]:
                remote = i.split('.')[0]
            else:
                remote = i.split()[0]
            line_list = i.split()
            local_interface = line_list[1] + line_list[2]
            remote_interface = line_list[-2] + line_list[-1]
            # Only add devices that were included in devices list
            if any(d['hostname'] == remote for d in devices):
                device_links_list.append({dev['hostname']: local_interface, remote: remote_interface})
                device_info.update(find_capabilities(remote, line_list))
        elif len(i.split()) > 1:  # line with data below the device name line
            line_list = i.split()
            local_interface = line_list[0] + line_list[1]
            remote_interface = line_list[-2] + line_list[-1]
            # Only add devices that were included in devices list
            if any(d['hostname'] == remote for d in devices):
                device_links_list.append({dev['hostname']: local_interface, remote: remote_interface})
                device_info.update(find_capabilities(remote, line_list))
    return device_links_list, device_info


def check_for_and_remove_error_links(dls):
    """
    In case there is a case such as this:
    Router1   Ten 3/4           155              S I   C9300-24P Ten 1/1/4
    Router1   Ten 3/4           164              S I   C9300-24P Ten 1/1/3

    remove a Ten3/4 since it can't link to two other physical links
    :param dls: which is the device_links
    return: dict {"router1": ["Gig1", "Gig2"], "router2": ["Gig1", "Gig2"]]
    """
    devices_with_links = {}  # track each devices' interfaces
    redundant_links_to_remove = []  # redundant links to be removed from device_links
    for link_full in dls:
        for device_name in link_full:
            if device_name not in devices_with_links:
                devices_with_links[device_name] = []
            if link_full[device_name] not in devices_with_links[device_name]:
                devices_with_links[device_name].append(link_full[device_name])
            else:
                redundant_links_to_remove.append(link_full)
    for link_to_del in redundant_links_to_remove:
        if link_to_del in dls:
            dls.remove(link_to_del)
    return devices_with_links


def sort_device_interfaces(remote_device_i):
    for item in remote_device_i:
        remote_device_i[item].sort()


def cml_topology_add_links(topo, maps, d_links):
    """
    Add links to CML topology
    """
    counter = 0
    for d_link in d_links:
        if len(d_link) != 2:
            # print(
            #     f"Warning - Link {d_link} contains {len(d_link)} endpoints. Links must have 2 endpoints. This will not be added to the CML topology")
            continue
        link_temp = {"id": "l{0}".format(counter)}
        d_count = 0
        for k, v in d_link.items():
            if d_count == 0:
                link_temp.update({
                    "n1": maps[k]["node_id"],
                    "i1": maps[k]["interfaces"][v]["id"],
                    "label": "{0}<->".format(k)
                })
            elif d_count == 1:
                link_temp.update({
                    "n2": maps[k]["node_id"],
                    "i2": maps[k]["interfaces"][v]["id"],
                })
                link_temp["label"] = link_temp["label"] + k
            d_count += 1
        topo["links"].append(link_temp)
        counter += 1


def extend_naming(short_name):
    """
    If necessary, convert CDP short interface type naming to OS full interface type names
    """
    if "Gig" in short_name and "GigabitEthernet" not in short_name:
        short_name = short_name.replace("Gig", "GigabitEthernet")
    if "Ten" in short_name and "TenGigabitEthernet" not in short_name:
        short_name = short_name.replace("Ten", "TenGigabitEthernet")
    if "Fas" in short_name and "FastEthernet" not in short_name:
        short_name = short_name.replace("Fas", "FastEthernet")
    return short_name


def create_interface_mapping_dict(mappings):
    """
    Write interface physical to virtual mappings to YAML file
    Write interface virtual to physical mappings to YAML file
    """
    mapp_p_to_v = {}
    for k in mappings:
        temp_dict_p_to_v = {k: {"cml_intf_xlate": {}}}
        for key, value in mappings[k]["interfaces"].items():
            temp_dict_p_to_v[k]["cml_intf_xlate"].update({extend_naming(key): value["if-name"]})
        temp_dict_p_to_v[k]["cml_intf_xlate"].update(default_mappings)
        mapp_p_to_v.update(temp_dict_p_to_v)
    return mapp_p_to_v


def link_id_start(virtual_topology):
    links = []
    for i in virtual_topology["links"]:
        links.append(int(i["id"].lstrip("l")))
    links.sort()
    return links[-1] + 1


def node_id_start(virtual_topology):
    nodes = []
    for i in virtual_topology["nodes"]:
        nodes.append(int(i["id"].lstrip("n")))
    nodes.sort()
    return nodes[-1] + 1


def ext_conn_nodes_create(virtual_topology, draft_topo, node_start):
    y = -1000
    for n in draft_topo["nodes"]:
        device_info = copy.deepcopy(device_template.get("ext_conn"))
        device_info["label"] = "ext-conn-{0}".format(n['label'])
        device_info["cpus"] = 0
        device_info["x"] = 5500
        device_info["y"] = y
        device_info["id"] = "n{0}".format(node_start)
        device_info["configuration"] = "bridge0"
        device_info["hide_links"] = True
        device_info["interfaces"] = [{
            "id": "i0",
            "label": "port",
            "slot": 0,
            "type": "physical"
        }]
        virtual_topology["nodes"].append(device_info)
        y += 50
        node_start += 1


def ext_conn_links_create(virtual_topology, draft_topo, link_node_start, link_start):
    for n in draft_topo["nodes"]:
        link = {
            "id": "l{0}".format(link_start),
            "n1": n["id"],
            "i1": "i1",
            "n2": "n{0}".format(link_node_start),
            "i2": "i0",
            "label": "{0}<->ext-conn-{1}".format(n['label'], n['label'])
        }
        virtual_topology["links"].append(link)
        link_start += 1
        link_node_start += 1


def cml_topology_add_external_connectors_and_links(topo):
    """
    Add an external connected or link to each node management interface
    """
    link_start = link_id_start(topo)
    node_start = node_id_start(topo)
    link_node_start = node_start
    new_topo = copy.deepcopy(topo)

    ext_conn_nodes_create(topo, new_topo, node_start)
    ext_conn_links_create(topo, new_topo, link_node_start, link_start)


def main():
    arguments = dict(
        devices=dict(required=True, type='list', elements='dict'),
        ext_conn=dict(required=False, type='bool', default=True),
        start_from=dict(required=False, type='int', default=2)
    )

    module = AnsibleModule(argument_spec=arguments, supports_check_mode=False)

    device_links = []
    remote_device_info_full = {}

    devices = module.params['devices']
    start_from = module.params['start_from']

    for device in devices:
        temp_device_links, remote_device_info = parse_cdp_output(device['cdp'], device, devices)
        remote_device_info_full.update(remote_device_info)
        for link in temp_device_links:  # add any newly found links to device links
            if link not in device_links:
                device_links.append(link)  # now saved newly discovered links
    devices_with_interface_dict = check_for_and_remove_error_links(device_links)
    sort_device_interfaces(devices_with_interface_dict)
    topology_cml, mappings_cml = cml_topology_create_initial(devices_with_interface_dict, remote_device_info_full, start_from)
    cml_topology_add_links(topology_cml, mappings_cml, device_links)
    if module.params['ext_conn']:
        cml_topology_add_external_connectors_and_links(topology_cml)
    mappings = create_interface_mapping_dict(mappings_cml)

    module.exit_json(changed=True, topology=topology_cml, mappings=mappings)


if __name__ == '__main__':
    main()
