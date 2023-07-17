#!/usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (c) 2023 Cisco and/or its affiliates.
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
# along with Ansible.  If not, see http://www.gnu.org/licenses/.

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

ANSIBLE_METADATA = {'metadata_version': '1.1', 'status': ['preview'], 'supported_by': 'community'}

DOCUMENTATION = r"""
---
module: send_validation_report
short_description: Sends the validation report to a data visualization software
description:
  -
author:
  - Kris Stickney (@kstickne)
  - Paul Pajerski (@ppajersk)
options:
    send:
        description:
        - Flag to denote whether to send or not
        required: true
        type: bool
    report:
        description:
        - The json report from validate
        required: true
        type: dict
        elements: str
"""

EXAMPLES = r"""
- name: Send validation report
    send_validation_report:
        send: true
        report: validation_report
    run_once: true
"""

from ansible.module_utils.basic import AnsibleModule
from influxdb import InfluxDBClient
from datetime import datetime, timezone, timedelta
import json


debug = []

def send_data(report, host_ip):
    try:
        client = InfluxDBClient(host=host_ip, port=8086, database='',username=None, password=None,
                                headers={"Authorization": ''})

        failure_list = report['consolidated_report']['failures']

        for failure in failure_list:
            current_host_list = []
            current_schemas_failed = []
            current_reasons_failed = []

            for host_item in json.loads((failure['hosts'].replace("'",'"'))):
                current_host_list.append(host_item)

            for schema_item in json.loads((failure['schemas'].replace("'",'"'))):
                current_schemas_failed.append(schema_item)

            for reason_item in json.loads((failure['reasons'].replace("'",'"'))):
                current_reasons_failed.append(reason_item)

            for write_host in current_host_list:
                current_time = datetime.now(timezone(timedelta(hours=-5), 'EST'))

                schemas_string = ', '.join(current_schemas_failed)
                reasons_string = ', '.join(current_reasons_failed)

                json_body = [ # regular
                    {
                        "measurement": "gitlab_pipeline_report",
                        # "tags": {
                        #     "person": [""],
                        #     "status": status
                        # },
                        "time": current_time,
                        "fields": {
                            "Host": write_host,
                            "Schemas": schemas_string,
                            "Reasons": reasons_string
                        }
                    }
                ]

                client.write_points(json_body)

        # debug.append(text)
        return (False, "Successful", debug)
    except Exception as e:
        return (True, e, debug)

def main():
    arguments = dict(
        send=dict(required=True, type='bool'),
        report=dict(required=True, type='dict'),
        host_ip=dict(required=True, type='str')
    )

    module = AnsibleModule(argument_spec=arguments, supports_check_mode=False)

    if module.params['send']:
        failed, error, debug = send_data(module.params['report'], module.params['host_ip'])
        module.exit_json(changed=True, failed=failed, result=error, debug=debug)
    else:
        module.exit_json(changed=False, failed=False)

if __name__ == '__main__':
    main()