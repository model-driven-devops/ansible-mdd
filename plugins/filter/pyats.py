from __future__ import absolute_import, division, print_function
__metaclass__ = type

from ansible.module_utils.six import PY3, raise_from
from ansible.errors import AnsibleError, AnsibleFilterError


try:
    from genie.conf.base import Device
    from genie.libs.parser.utils import get_parser
except ImportError as imp_exc:
    GENIE_IMPORT_ERROR = imp_exc
else:
    GENIE_IMPORT_ERROR = None

try:
    from pyats.datastructures import AttrDict
except ImportError as imp_exc:
    PYATS_IMPORT_ERROR = imp_exc
else:
    PYATS_IMPORT_ERROR = None

ansible_os_map = {
    "ios": "iosxe"
}


def pyats_parser(cli_output, command, os):
    if not PY3:
        raise AnsibleFilterError("Genie requires Python 3")

    if GENIE_IMPORT_ERROR:
        raise_from(
            AnsibleError('genie must be installed to use this plugin'),
            GENIE_IMPORT_ERROR)

    if PYATS_IMPORT_ERROR:
        raise_from(
            AnsibleError('pyats must be installed to use this plugin'),
            PYATS_IMPORT_ERROR)

    # Translate from ansible_network_os values to pyATS
    if os in ansible_os_map.keys():
        os = ansible_os_map[os]

    device = Device("uut", os=os)

    device.custom.setdefault("abstraction", {})["order"] = ["os"]
    device.cli = AttrDict({"execute": None})

    try:
        get_parser(command, device)
    except Exception as e:
        raise AnsibleFilterError("Unable to find parser for command '{0}' ({1})".format(command, e))

    try:
        parsed_output = device.parse(command, output=cli_output)
    except Exception as e:
        raise AnsibleFilterError("Unable to parse output for command '{0}' ({1})".format(command, e))

    if parsed_output:
        return parsed_output
    else:
        return None


class FilterModule(object):
    def filters(self):
        return {
            'pyats_parser': pyats_parser
        }
