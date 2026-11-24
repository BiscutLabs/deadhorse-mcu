"""Audit elaborated production macro sockets; no source-text behavioral tests."""
import copy

PORTS = {
    'LfRcMacro': {'vdd': ('inout', 1), 'vss': ('inout', 1), 'enable': ('input', 1),
                  'trim': ('input', 6), 'test': ('input', 1), 'clock': ('output', 1), 'ready': ('output', 1)},
    'PorBrownoutMacro': {'vdd': ('inout', 1), 'vss': ('inout', 1), 'threshold': ('input', 2),
                         'test': ('input', 1), 'supplyReset_n': ('output', 1),
                         'powerOn_n': ('output', 1), 'brownout': ('output', 1)}}


def interfaces():
    """Pin-only Yosys blackboxes, never an analog implementation."""
    result = {'modules': {}}
    for name, ports in PORTS.items():
        module = dict(attributes={'blackbox': '1'}, ports={}, cells={}, netnames={})
        bit = 2
        for pin, (direction, width) in ports.items():
            bits = list(range(bit, bit + width)); bit += width
            module['ports'][pin] = dict(direction=direction, bits=bits)
            module['netnames'][pin] = dict(hide_name=0, bits=bits, attributes={})
        result['modules'][name] = module
    return result


def audit(design):
    top = design['modules']['DeadhorseSoc']; cells = top['cells']; ports = top['ports']
    def require(ok, message):
        if not ok: raise ValueError(message)
    expected = {'lf': 'LfRcMacro', 'por': 'PorBrownoutMacro'}
    require({n: c['type'] for n, c in cells.items() if c['type'] in PORTS} == expected,
            'Missing, duplicate or renamed analog socket')
    ignored = {'lf': 'ready', 'por': 'powerOn_n'}
    rows = []
    for name, kind in expected.items():
        c = cells[name]['connections']
        definition = design['modules'][kind]['ports']
        require({p: (v['direction'], len(v['bits'])) for p, v in definition.items()} == PORTS[kind],
                'Wrong macro port declaration')
        require(set(c) == set(PORTS[kind]) - {ignored[name]}, 'Unexpected or missing bound macro pin')
        require(all(len(bits) == PORTS[kind][pin][1] for pin, bits in c.items()), 'Wrong pin width')
        for p in ('vdd', 'vss'):
            require(c[p] == ports[p]['bits'], 'Wrong analog supply binding')
        require(c['test'] == ['0'], 'Test bypass must be tied low')
        for p in PORTS[kind]:
            rows.append(dict(instance=name, pin=p, bits=c.get(p, []),
                             disposition='intentionally_unused_diagnostic' if p == ignored[name] else 'bound'))
    lf, por = cells['lf']['connections'], cells['por']['connections']
    clock = cells['clocks']['connections']; cause = cells['causes']['connections']
    digital = cells['digital']['connections']
    live = [ports[p]['bits'][0] for p in ('vdd', 'vss')]
    live += [lf['clock'][0], por['supplyReset_n'][0], por['brownout'][0]]
    require(all(type(b) is int for b in live) and len(set(live)) == len(live),
            'Constant or aliased supply/analog output')
    require(lf['enable'] == ['1'] and lf['trim'] == ['0'] * 6, 'Unsafe LF startup ties')
    require(lf['clock'] == clock['rcClock'], 'LF clock misses counted bootstrap')
    require(por['supplyReset_n'] == clock['supplyReset_n'], 'POR misses reset combination')
    require(por['brownout'] == cause['brownout'], 'Brownout cause disconnected')
    require(por['threshold'] == digital['i1_clockControl_threshold'], 'Threshold not driven by production selector')
    require(clock['porBypass'] == ports['porBypass']['bits'] == cause['bypass'], 'Static bypass misbound')
    require(clock['externalReset_n'] == ports['externalReset_n']['bits'], 'External reset misbound')
    return rows


def fault_controls(design):
    faults = {
        'test_bypass': ('lf', 'test', ['1']),
        'wrong_trim': ('lf', 'trim', ['1'] * 6),
        'reset_disconnected': ('por', 'supplyReset_n', ['1']),
        'clock_disconnected': ('lf', 'clock', ['0']),
        'threshold_disconnected': ('por', 'threshold', ['0', '0']),
        'brownout_disconnected': ('por', 'brownout', ['0'])}
    caught = []
    for label, (cell, pin, value) in faults.items():
        broken = copy.deepcopy(design)
        broken['modules']['DeadhorseSoc']['cells'][cell]['connections'][pin] = value
        try: audit(broken)
        except ValueError: caught.append(label)
        else: raise ValueError('Binding fault escaped: ' + label)
    for label in ('paired_reset_constant', 'shorted_supplies', 'wrong_width'):
        broken = copy.deepcopy(design); top = broken['modules']['DeadhorseSoc']; cells = top['cells']
        if label == 'paired_reset_constant':
            cells['por']['connections']['supplyReset_n'] = ['1']
            cells['clocks']['connections']['supplyReset_n'] = ['1']
        elif label == 'shorted_supplies':
            top['ports']['vss']['bits'] = top['ports']['vdd']['bits']
            for name in ('lf', 'por'):
                cells[name]['connections']['vss'] = top['ports']['vdd']['bits']
        else: cells['lf']['connections']['clock'] *= 2
        try: audit(broken)
        except ValueError: caught.append(label)
        else: raise ValueError('Binding fault escaped: ' + label)
    return caught
