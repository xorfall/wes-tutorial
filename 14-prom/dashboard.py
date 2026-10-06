"""Layout-only export for results in the Prometheus tutorial workspace."""


def dashboard_definition(client):
    """Reference this session's results without exporting values or credentials."""
    names = ['board', 'resourcePanel', 'logs']
    members = [{'id': name, 'node': client.names[name],
                'generation': client.generation, 'label': '$' + name}
               for name in names]

    def leaf(name, weight=1):
        return {'kind': 'member', 'id': name + '-leaf', 'member': name,
                'width': 'fill', 'align': 'start', 'weight': weight}

    return {
        'version': 1, 'id': 'prom-showcase', 'name': 'orders',
        'title': 'Orders API · operations', 'revision': 0, 'members': members,
        'layout': {
            'kind': 'column', 'id': 'root', 'weight': 1, 'children': [
                {'kind': 'row', 'id': 'signals-and-resources', 'weight': 1,
                 'children': [leaf('board', 2), leaf('resourcePanel')]},
                leaf('logs'),
            ],
        },
    }
