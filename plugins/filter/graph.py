from __future__ import absolute_import, division, print_function
__metaclass__ = type

from ansible.module_utils.six import raise_from
from ansible.errors import AnsibleError
try:
    import networkx as nx
except ImportError as imp_exc:
    NETWORKX_IMPORT_ERROR = imp_exc
else:
    NETWORKX_IMPORT_ERROR = None

# display = Display()


def graph(topology_data, layout='kamada_kawai', scale=500):
    if NETWORKX_IMPORT_ERROR:
        raise_from(AnsibleError('networkx must be installed to use this plugin'), NETWORKX_IMPORT_ERROR)

    pos = {}
    g = nx.Graph()

    for link in topology_data['links']:
        g.add_edge(link['n1'], link['n2'])

    if layout == 'spring':
        pos = nx.layout.spring_layout(g, scale=scale)
    elif layout == 'planar':
        pos = nx.layout.planar_layout(g, scale=scale)
    elif layout == 'spectral':
        pos = nx.layout.spectral_layout(g, scale=scale)
    elif layout == 'kamada_kawai':
        pos = nx.layout.kamada_kawai_layout(g, scale=scale)

    # display.vvvvv(f"{pos}")

    for key, value in pos.items():
        for node in topology_data['nodes']:
            if node['id'] == key:
                node['x'] = int(value[0])
                node['y'] = int(value[1])

    return topology_data


class FilterModule(object):

    def filters(self):
        return {
            'graph': graph,
        }
