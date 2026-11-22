"""Explicit non-inverting GF180 fanout trees; every original pin is verified.

ABC cannot buffer nets driving only sequential reset pins. T19's USB-domain
reset release exposes that case. This pass inserts real library buffers, with
their delay, area and electrical checks retained in the downstream STA.
It is enabled for USB, or explicitly selected internal reset sources in a
block screen; clock nets are never changed.
"""
import copy
import math

BUFFER = 'gf180mcu_fd_sc_mcu7t5v0__buf_4'

def internal_reset_sources(module, clock):
    """Select driven RN/SETN nets, never ideal primary inputs or clock nets."""
    primary={b for p in module['ports'].values() if p['direction']=='input' for b in p['bits']}
    clocks=set(module['ports'][clock]['bits'])
    drivers={}
    resets=set()
    for name,cell in module['cells'].items():
        clocks.update(cell['connections'].get('CLK',[]))
        for pin,direction in cell['port_directions'].items():
            for bit in cell['connections'][pin]:
                if not isinstance(bit,int):continue
                if direction=='output':drivers.setdefault(bit,[]).append((name,pin))
                elif pin in ('RN','SETN'):resets.add(bit)
    selected=resets-primary
    # This opt-in screen is pre-CTS and single-clock. Reject buffered/gated
    # clock trees rather than risk selecting a reset net in their ancestry.
    if clocks-set(module['ports'][clock]['bits']):
        raise ValueError('Internal clock tree is unsupported by reset selection')
    if selected & clocks:raise ValueError('Reset source also drives a clock')
    if any(len(drivers.get(bit,[]))!=1 for bit in selected):
        raise ValueError('Missing or ambiguous internal reset driver')
    return selected

def verify(original, transformed, inserted):
    if original['ports'] != transformed['ports']:
        raise ValueError('Buffer pass changed ports')
    if set(transformed['cells']) != set(original['cells']) | set(inserted):
        raise ValueError('Buffer pass changed original cell inventory')
    original_bits = {b for item in list(original['ports'].values())+list(original.get('netnames',{}).values())
                     for b in item['bits'] if isinstance(b,int)}
    original_bits.update(b for c in original['cells'].values() for bits in c['connections'].values()
                         for b in bits if isinstance(b,int))
    parents = {}
    for name in inserted:
        cell = transformed['cells'][name]
        if cell['type'] != BUFFER or cell['port_directions'] != {'I':'input','Z':'output'}:
            raise ValueError('Non-buffer inserted')
        pins = cell['connections']
        if set(pins) != {'I','Z'} or any(len(p)!=1 for p in pins.values()):
            raise ValueError('Invalid buffer pins')
        child, parent = pins['Z'][0], pins['I'][0]
        if child in original_bits:
            raise ValueError('Buffer output overlaps an original net')
        if child in parents:
            raise ValueError('Multiple buffer drivers')
        parents[child] = parent
    def resolve(bit):
        seen = set()
        while bit in parents:
            if bit in seen:
                raise ValueError('Buffer cycle')
            seen.add(bit); bit = parents[bit]
        return bit
    for name, old in original['cells'].items():
        new = copy.deepcopy(transformed['cells'][name])
        if 'CLK' in old['connections'] and new['connections']['CLK'] != old['connections']['CLK']:
            raise ValueError('Buffer pass changed clock pin')
        new['connections'] = {p:([resolve(b) for b in bits] if old['port_directions'][p]=='input' else bits)
                              for p,bits in new['connections'].items()}
        if new != old:
            raise ValueError('Buffer pass changed logic/pin: '+name)

def buffer_module(module, clock, limit=8, *, source_bits=None, prefix='usb_fanout_'):
    if limit < 2:
        raise ValueError('Fanout limit must permit a tree')
    if not prefix or any(not (c.isalnum() or c=='_') for c in prefix):
        raise ValueError('Invalid buffer instance prefix')
    result = copy.deepcopy(module)
    forbidden = set(module['ports'][clock]['bits'])
    for cell in module['cells'].values():
        if 'CLK' in cell['connections']:
            forbidden.update(cell['connections']['CLK'])
    if source_bits is not None:
        source_bits=set(source_bits)
        if not source_bits or any(not isinstance(b,int) for b in source_bits) or source_bits & forbidden:
            raise ValueError('Selected sources must be non-clock signal bits')
    all_bits = [b for cell in module['cells'].values() for bits in cell['connections'].values()
                for b in bits if isinstance(b,int)]
    all_bits += [b for item in list(module['ports'].values())+list(module.get('netnames',{}).values())
                 for b in item['bits'] if isinstance(b,int)]
    next_bit = max(all_bits+[1])+1
    sinks = {}
    for name,cell in module['cells'].items():
        for port,direction in cell['port_directions'].items():
            if direction == 'input':
                for index,bit in enumerate(cell['connections'][port]):
                    if isinstance(bit,int) and bit not in forbidden and (source_bits is None or bit in source_bits):
                        sinks.setdefault(bit,[]).append((name,port,index))
    inserted = []
    def subtree(source, targets):
        nonlocal next_bit
        if len(targets) <= limit:
            for name,port,index in targets:
                result['cells'][name]['connections'][port][index] = source
            return
        size = math.ceil(len(targets)/limit)
        for start in range(0,len(targets),size):
            name = prefix+str(len(inserted))
            if name in result['cells']:
                raise ValueError('Buffer instance collision')
            bit = next_bit; next_bit += 1
            result['cells'][name] = dict(hide_name=0,type=BUFFER,parameters={},attributes={},
                port_directions={'I':'input','Z':'output'},connections={'I':[source],'Z':[bit]})
            inserted.append(name)
            subtree(bit,targets[start:start+size])
    if source_bits is not None and set(sinks)!=source_bits:
        raise ValueError('Selected source has no mapped sinks')
    for source,targets in sinks.items():
        if len(targets)>limit:
            subtree(source,targets)
    verify(module,result,inserted)
    return result, inserted
