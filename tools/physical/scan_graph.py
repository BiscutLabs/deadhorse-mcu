"""Independent connectivity and normal-mode certificate for T37 insertion."""
from collections import defaultdict
from scan_cells import PREFIX


def chains(graph, manifest):
    eligible = {n for r in manifest['lanes'] for n in r['cells']}
    q = {}
    for name in eligible:
        cell = graph[name]
        if not cell['type'].startswith(PREFIX+'sdff'):
            raise ValueError('Unreplaced eligible FF: '+name)
        net = cell['pins']['Q']
        if net is None or net in q:
            raise ValueError('Ambiguous scanned state')
        q[net] = name
    seen, result = set(), []
    for lane in range(7):
        hook = 'i_chip_core.soc.scanHooks.lane_'+str(lane)
        net = graph[hook]['pins']['I']
        head = graph['_t37_scan_in_'+str(lane)]['pins']['Z']
        tail_first = []
        while net != head:
            if net not in q or q[net] in seen:
                raise ValueError('Broken, duplicate or crossed scan chain')
            name = q[net]
            if graph[name]['pins']['SE'] != graph['_t37_scan_enable']['pins']['Z']:
                raise ValueError('Wrong scan enable')
            seen.add(name); tail_first.append(name)
            net = graph[name]['pins']['SI']
        matches = [r for r in manifest['lanes'] if set(r['cells']) == set(tail_first)]
        if len(matches) != 1:
            raise ValueError('Mixed or partial original clock/edge group')
        result.append(dict(lane=lane, original_group=matches[0]['lane'],
            edge='falling' if matches[0]['clock_pin']=='CLKN' else 'rising',
            cells=list(reversed(tail_first))))
    if seen != eligible:
        raise ValueError('Unstitched state')
    return result


def normal_mode(before, after, manifest, controls):
    """Compositional state equivalence; FF truth tables qualified separately.

    New primitive logic is reduced with mode=0. Every original cell/pin and
    supply must match. The seven SO hook changes are masked by their original
    mode muxes, checked directly against the actual pin graph below.
    """
    mode = before[manifest['mode'][0]]['pins'][manifest['mode'][1]]
    zero, one = controls['zero'], controls['one']
    added = set(after)-set(before)
    if added != set(controls['added']):
        raise ValueError('Unexpected new/deleted cell inventory')
    if not set(before) <= set(after):
        raise ValueError('Deleted original cell')
    # Macro outputs were split before a clamp; the raw output represents the
    # same unconstrained original macro value. No assumption about RAM data.
    aliases = {r['raw']: r['original'] for r in controls['output_clamps']}
    drivers = {}
    expected_power=before[next(iter(manifest['excluded']))]['power']
    for name in added:
        c = after[name]
        if c['power']!=expected_power:
            raise ValueError('Incorrect added-cell power/well connection')
        output = 'ZN' if c['type']==PREFIX+'clkinv_4' else 'Z'
        if output not in c['pins'] or c['pins'][output] in drivers:
            raise ValueError('Unknown or multiply driven added primitive')
        drivers[c['pins'][output]] = name
    def driving(graph):
        result=defaultdict(set)
        for name,c in graph.items():
            for p in controls['output_pins'][c['type']]:
                if c['pins'][p] is not None:result[c['pins'][p]].add((name,p))
        return result
    left,right=driving(before),driving(after)
    splits={r['original']:r for r in controls['output_clamps']}
    oldnets={v for c in before.values() for v in c['pins'].values() if v is not None}
    for n in oldnets:
        expected=left[n]
        if n in splits:
            row=splits[n]
            if expected!={(row['cell'],row['pin'])} or n not in drivers:
                raise ValueError('Invalid macro-output split')
            expected={(drivers[n],'Z')}
        if right[n]!=expected:
            raise ValueError('Changed driver of original net: '+n)
    for n in set(right)-oldnets:
        if len(right[n])!=1:raise ValueError('Multiple new net drivers')
    # Unscanned controller and its backward combinational cones are unchanged
    # in BOTH modes. Stop at other state/macro outputs; their interfaces are
    # independently audited. Raw POR must never be masked by testMode.
    todo=list(manifest['excluded']);protected=set()
    while todo:
        name=todo.pop()
        if name in protected:continue
        protected.add(name)
        if after[name]!=before[name]:raise ValueError('Changed access/reset cone: '+name)
        c=before[name];outs=controls['output_pins'][c['type']]
        for p,n in c['pins'].items():
            if p in outs:continue
            for driver,driver_pin in left[n]:
                if after[driver]['pins'][driver_pin]!=before[driver]['pins'][driver_pin] or right[n]!=left[n]:
                    raise ValueError('Changed raw controller-cone frontier')
                if driver in manifest['excluded'] or driver not in controls['state_or_macro']:
                    todo.append(driver)
    busy = set()
    cache = {mode: False, zero: False, one: True}

    def reduce(net):
        if net in cache:
            return cache[net]
        if net in aliases:
            return aliases[net]
        if net not in drivers:
            return net
        if net in busy:
            raise ValueError('New combinational cycle')
        busy.add(net)
        c = after[drivers[net]]; p = c['pins']; kind=c['type'].removeprefix(PREFIX)
        if kind=='mux2_1':
            s=reduce(p['S'])
            if not isinstance(s, bool):
                raise ValueError('Mux selection is not fixed by test mode')
            result=reduce(p['I1'] if s else p['I0'])
        elif kind=='and2_1':
            a,b=reduce(p['A1']),reduce(p['A2'])
            result=False if a is False or b is False else b if a is True else a if b is True else ('and',a,b)
        elif kind=='buf_1':
            result=reduce(p['I'])
        elif kind=='clkinv_4':
            a=reduce(p['I']); result=(not a) if isinstance(a,bool) else ('not',a)
        else:
            raise ValueError('Unqualified added logic: '+kind)
        busy.remove(net);cache[net]=result
        return result

    for n in drivers:reduce(n)  # Include otherwise unused added logic.
    for lane,pair in enumerate(manifest['inputs']):
        anchor=after['_t37_scan_in_'+str(lane)]
        if anchor['type']!=PREFIX+'buf_1' or anchor['pins']['I']!=before[pair[0]]['pins'][pair[1]]:
            raise ValueError('Wrong physical SI lane binding')

    eligible={n for r in manifest['lanes'] for n in r['cells']}
    hooks={'i_chip_core.soc.scanHooks.lane_'+str(i) for i in range(7)}
    clamp_pins={(r['cell'], r['pin']): r for r in controls['output_clamps']}
    observed=0
    for name, old in before.items():
        new=after[name]
        if new['power'] != old['power']:
            raise ValueError('Changed supply: '+name)
        if name not in eligible and new['type'] != old['type']:
            raise ValueError('Changed non-scan type: '+name)
        expected=set(old['pins'])
        if name in eligible:
            expected=(expected-{'CLKN'}) | ({'CLK'} if 'CLKN' in old['pins'] else set()) | {'SI','SE'}
        if set(new['pins']) != expected:
            raise ValueError('Changed pin inventory: '+name)
        for pin, net in old['pins'].items():
            if name in hooks and pin=='I':
                continue
            newpin='CLK' if pin=='CLKN' and name in eligible else pin
            actual=new['pins'][newpin]
            if (name,pin) in clamp_pins:
                row=clamp_pins[name,pin]
                if actual != row['raw'] or row['original'] != net or reduce(net) != net:
                    raise ValueError('Changed isolated macro output')
                continue
            reference= False if net==zero else True if net==one else net
            if pin=='CLKN' and name in eligible:
                reference=('not',reference)
            # The mode-Q pin itself must keep its original net, not be reduced
            # to its mode assumption. This also protects the raw reset cone.
            if actual==net and not (pin=='CLKN' and name in eligible):
                continue
            if reduce(actual) != reference:
                raise ValueError('Changed functional pin: '+name+'/'+pin)
            observed+=1
        if name in eligible and reduce(new['pins']['SE']) is not False:
            raise ValueError('Scan selected in functional mode')
    # Each SO hook feeds only the I1 of an existing mode-selected output mux.
    # This proves arbitrary chain-tail values cannot affect any original state
    # or output when mode=0; there is no unchecked observation exclusion.
    def mode_buffer(n):
        visited=set()
        while n!=mode:
            if n in visited or len(left[n])!=1:return False
            visited.add(n);driver,p=next(iter(left[n]));c=before[driver]
            if p!='Z' or c['type']!=PREFIX+'buf_1':return False
            n=c['pins']['I']
        return True
    for hook in hooks:
        z=before[hook]['pins']['Z']
        uses=[(n,p) for n,c in before.items() for p,v in c['pins'].items() if v==z and not(n==hook and p=='Z')]
        if not uses:
            raise ValueError('Unobserved scan output hook')
        for name,pin in uses:
            c=before[name]
            if c['type'] != PREFIX+'mux2_1' or pin!='I1' or not mode_buffer(c['pins']['S']):
                raise ValueError('Scan tail has a functional fanout')
    return dict(changed_pins_reduced=observed, state_bits=len(eligible)+len(manifest['excluded']),
        claim='State/output event equivalence in mode=0, composed with qualified FF and added primitive Liberty functions; excludes electrical timing')


def test_mode(graph, manifest, controls):
    """Trace actual test controls, never the transform's intended rewires."""
    mode,zero,one=controls['mode'],controls['zero'],controls['one']
    added=set(controls['added']);drivers={}
    for name in added|set(manifest['clock_gates']):
        c=graph[name]
        p='Q' if name in manifest['clock_gates'] else 'ZN' if c['type']==PREFIX+'clkinv_4' else 'Z'
        if c['pins'][p] in drivers:raise ValueError('Multiple test-control drivers')
        drivers[c['pins'][p]]=name
    cache={mode:True,zero:False,one:True};busy=set()
    def value(n):
        if n in cache:return cache[n]
        if n not in drivers:return n
        if n in busy:raise ValueError('Test clock/control cycle')
        busy.add(n);c=graph[drivers[n]];p=c['pins'];kind=c['type'].removeprefix(PREFIX)
        if kind=='mux2_1':
            s=value(p['S'])
            if not isinstance(s,bool):raise ValueError('Unknown test mux selection')
            v=value(p['I1'] if s else p['I0'])
        elif kind=='and2_1':
            a,z=value(p['A1']),value(p['A2'])
            v=False if a is False or z is False else z if a is True else a if z is True else ('and',a,z)
        elif kind=='buf_1':v=value(p['I'])
        elif kind=='clkinv_4':
            a=value(p['I']);v=(not a) if isinstance(a,bool) else ('not',a)
        elif kind.startswith('icgtp_'):
            if value(p['TE']) is not True:raise ValueError('ICG not forced open in test')
            v=value(p['CLK'])
        else:raise ValueError('Unqualified test primitive')
        busy.remove(n);cache[n]=v;return v
    for row in manifest['lanes']:
        clock=('not',controls['osc']) if row['clock_pin']=='CLKN' else controls['osc']
        for name in row['cells']:
            p=graph[name]['pins']
            if value(p['CLK'])!=clock:raise ValueError('Wrong test clock: '+name)
            if value(p['SE'])!=controls['enable']:raise ValueError('Wrong test enable')
            for pin in ('RN','SN'):
                if pin in p and value(p[pin])!=controls['reset_n']:raise ValueError('Wrong test reset: '+name)
    count=defaultdict(int)
    for name,c in graph.items():
        if c['type'].startswith('gf180mcu_ocd_ip_sram__'):
            for pin,n in c['pins'].items():
                if pin in ('CEN','GWEN') or pin.startswith('WEN['):
                    if value(n) is not True:raise ValueError('Unisolated memory write/enable')
                    count['write_controls']+=1
    for r in controls['output_clamps']:
        if value(r['original']) is not False:raise ValueError('Unisolated macro output')
        count['clamped_outputs']+=1
    for pin,n in graph['i_chip_core.soc.por']['pins'].items():
        if pin.startswith('threshold[') and value(n) is not False:raise ValueError('Unsafe threshold')
    if count!={'write_controls':200,'clamped_outputs':161}:raise ValueError('Wrong isolation inventory')
    return dict(count)
