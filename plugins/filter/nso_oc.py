from __future__ import absolute_import, division, print_function
__metaclass__ = type

from ansible.module_utils.six import raise_from
from ansible.errors import AnsibleError
import copy

try:
    from package_nso_to_oc.xe import main_xe
except ImportError as imp_exc:
    NSO_OC_IMPORT_ERROR = imp_exc
else:
    NSO_OC_IMPORT_ERROR = None


def nso_oc(config_data):

    if NSO_OC_IMPORT_ERROR:
        raise_from(AnsibleError('nso-oc must be installed to use this plugin'), NSO_OC_IMPORT_ERROR)

    mdd_dict = {
        "mdd_data": {}
    }
    oc_dict = {
        "mdd:openconfig": {}
    }
    native_dict = copy.deepcopy(config_data)
    translation_notes = []
    main_xe.build_xe_to_oc(config_data, native_dict, oc_dict, translation_notes)

    mdd_dict['mdd_data'] = {
        "mdd:openconfig": oc_dict['mdd:openconfig'],
        "config": native_dict
    }
    return mdd_dict


class FilterModule(object):

    def filters(self):
        return {
            'nso_oc': nso_oc
        }
