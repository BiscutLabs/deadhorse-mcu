"""Enumerate production mapped asynchronous pins and their source-state roles.

This inventory grants no timing exception or permission to remove a reset.
Physical FFs are counted once; all merged source identities remain visible.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import runpy
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.physical.scan_cells import groups, model
sys.path.insert(0,str(ROOT/'hw/top/reference/measurements'))
from plan04_screen import clock_manifest

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--map',required=True)
p.add_argument('--context',required=True,help='Reviewed fresh production USB-context receipt')
p.add_argument('--output',required=True)
a=p.parse_args()
started=time.monotonic()
base=(ROOT/a.map).resolve();base.relative_to(ROOT/'build')
out=(ROOT/a.output).resolve();out.relative_to(ROOT/'build')
out.mkdir(parents=True,exist_ok=False)
receipt=json.loads((base/'result.json').read_text())
context_path=(ROOT/a.context).resolve();context_path.relative_to(ROOT/'build')
context=json.loads(context_path.read_text())
assert context['status']=='pass'
input_hashes={str(context_path):sha(context_path),**context['input_sha256']}
for name,h in input_hashes.items():assert sha(name)==h, ('Changed context dependency',name)
for module in list(sys.modules.values()):
    file=getattr(module,'__file__',None)
    if file:
        path=Path(file).resolve()
        if path.suffix=='.py' and path.is_relative_to(ROOT):input_hashes[str(path)]=sha(path)
input_hashes[str(Path(__file__).resolve())]=sha(__file__)
mapped=base/'canonical.json'
assert sha(mapped)==receipt['mapped_sha256'], 'Mapping receipt does not bind canonical graph'
assert context['input_sha256'][str(mapped)]==sha(mapped), 'Context belongs to another production map'
for field in ('input_sha256','emitted_sha256'):
    for name,h in receipt[field].items():
        assert sha(ROOT/name.removeprefix('/work/'))==h, ('Changed production input',name)
cfg=json.loads((ROOT/'phys/gf180-ws-1x1/block-timing.json').read_text())
lib=ROOT/cfg['liberty']
assert sha(lib)==cfg['sha256']==receipt['liberty_sha256']
library=dict(groups(lib.read_text(),'cell'))
top=json.loads(mapped.read_text())['modules']['DeadhorseSoc']
cells=top['cells']
domains=clock_manifest(top)
aliases=defaultdict(set)
for name,net in top['netnames'].items():
    if not net.get('hide_name'):
        for index,bit in enumerate(net['bits']):
            aliases[bit].add(name+(f'[{index}]' if len(net['bits'])>1 else ''))
drivers=defaultdict(list)
loads=defaultdict(list)
for name,cell in cells.items():
    for pin,direction in cell['port_directions'].items():
        for index,bit in enumerate(cell['connections'][pin]):
            (drivers if direction=='output' else loads)[bit].append((name,pin,index))
for bit,ds in drivers.items():
    if isinstance(bit,int) and len(ds)!=1: raise ValueError(('Multiple drivers',bit,ds))

state={}
other_state=[]
for typ in sorted({c['type'] for c in cells.values()}):
    if typ not in library:
        assert typ in ('gf180mcu_ocd_ip_sram__sram1024x8m8wm1','gf180mcu_ocd_ip_sram__sram512x8m8wm1'), ('Unknown mapped macro',typ)
        continue  # SRAM internal state is outside standard-cell FF counts.
    body=library[typ]
    if list(groups(body,'ff')):
        state[typ]=model(body)
    elif any(list(groups(body,k)) for k in ('latch','ff_bank','latch_bank','statetable')):
        other_state.append(typ)

def net(bit):
    return dict(bit=bit,aliases=sorted(aliases[bit]),drivers=drivers[bit],fanout=len(loads[bit]))

def literal(expr):
    normalized=re.sub(r'[()\s]','',expr)
    if not re.fullmatch(r'!?[A-Za-z_][A-Za-z_0-9]*',normalized):
        raise ValueError(('Unsupported state control expression',expr))
    return normalized.lstrip('!'),not normalized.startswith('!')

def origin(bit):
    path=[];seen=set()
    while isinstance(bit,int) and drivers[bit]:
        if bit in seen: raise ValueError(('Reset buffer cycle',bit))
        seen.add(bit)
        name,pin,index=drivers[bit][0]
        cell=cells[name]
        # Do not silently collapse general combinational functions.
        if not cell['type'].startswith('gf180mcu_fd_sc_mcu7t5v0__buf_'): break
        assert pin=='Z' and index==0 and set(cell['connections'])=={'I','Z'}
        path.append(name);bit=cell['connections']['I'][0]
    return dict(net=net(bit),buffers=path)

clock_roots={top['ports']['oscIn']['bits'][0]:'OSC_IN',
    top['ports']['pins_inactive_jtagTck']['bits'][0]:'TCK',
    top['netnames']['_clocks_ungatedClock']['bits'][0]:'main divide-by-six output',
    top['netnames']['digital.subsystem.usb.aonClock']['bits'][0]:'static AON source selection'}
def clock_ancestry(bit):
    path=[];seen=set()
    while bit not in clock_roots:
        assert bit not in seen and len(drivers[bit])==1, 'Unknown/cyclic clock ancestry'
        seen.add(bit);name,pin,index=drivers[bit][0];cell=cells[name]
        if cell['type']=='gf180mcu_fd_sc_mcu7t5v0__icgtp_1':parent='CLK'
        elif re.fullmatch(r'gf180mcu_fd_sc_mcu7t5v0__buf_[1248]',cell['type']):parent='I'
        else:raise ValueError(('Unapproved clock-producing cell',name,cell['type']))
        path.append(dict(cell=name,type=cell['type'],output=pin,connections=cell['connections']))
        bit=cell['connections'][parent][0]
    return dict(root=clock_roots[bit],root_net=net(bit),gates_and_buffers=path)

rows=[];totals=Counter();origins=Counter()
for name,cell in cells.items():
    if cell['type'] not in state: continue
    ff,pins=state[cell['type']]
    clock,positive=literal(ff['clocked_on'])
    assert clock in cell['connections'] and len(cell['connections'][clock])==1
    assert len(cell['connections']['Q'])==1
    q=cell['connections']['Q'][0]
    row=dict(cell=name,type=cell['type'],q=net(q),clock_pin=clock,
        clock_polarity='rising' if positive else 'falling',
        clock=net(cell['connections'][clock][0]),async_controls=[],
        clock_domain=domains[name+'/'+clock],mapped_source=cell.get('attributes',{}),
        clock_ancestry=clock_ancestry(cell['connections'][clock][0]),
        role='unreviewed',cohort='unclassified',release_class='unclassified')
    for kind in ('clear','preset'):
        if kind not in ff:continue
        expr=ff[kind];pin,positive=literal(expr)
        assert pin in cell['connections'] and len(cell['connections'][pin])==1, (cell['type'],kind,expr)
        bit=cell['connections'][pin][0]
        src=origin(bit)
        origins[(src['net']['bit'],pin)]+=1
        row['async_controls'].append(dict(kind=kind,pin=pin,
            active_level=int(positive),
            net=net(bit),buffer_collapsed_origin=src))
    totals['flops']+=1
    totals['async_reset_or_set_flops' if row['async_controls'] else 'no_async_control_flops']+=1
    rows.append(row)

# Reconstruct source ownership from the authenticated production hierarchy.
# The USB island uses the explicitly proved older release-wire spellings.
hierarchy=context_path.parent/'hierarchy/hier.json'
binding_path=context_path.parent/'usb-source-binding/result.json'
binding=json.loads(binding_path.read_text())
assert context['input_sha256'][str(binding_path)]==sha(binding_path)
assert context['input_sha256'][str(hierarchy)]==sha(hierarchy)
assert sha(hierarchy)==binding['hierarchy_sha256']
previous_argv=sys.argv
sys.argv=['reset_inventory.py','--hier',str(hierarchy),'--output',str(out/'source-hierarchy')]
try:
    source=runpy.run_path(str(ROOT/'hw/top/reference/measurements/reset_inventory.py'))
finally:
    sys.argv=previous_argv
owners={}
def own(typ,path):
    owners[path]=typ
    for name,c in source['mods'][typ].get('cells',{}).items():
        if c['type'] in source['mods'] and not int(source['mods'][c['type']].get('attributes',{}).get('blackbox','0'),2):
            own(c['type'],path+'.'+name)
own('DeadhorseSoc','DeadhorseSoc')
owner_paths=sorted(owners,key=len,reverse=True)
byalias=defaultdict(list)
for c in source['seq']:
    owner=next(n for n in owner_paths if c['instance'].startswith(n+'.'))
    for index,q in enumerate(c['connections']['Q']):
        source_aliases=source['aliases'].get(source['find'](q),())
        item=dict(instance=c['instance'],bit=index,module=owners[owner],src=c['src'],
                  q_aliases=sorted(source_aliases))
        for alias in source_aliases:
            byalias[alias.removeprefix('DeadhorseSoc.')].append(item)

def state_alias(alias):
    prefix='digital.subsystem.usb.'
    proven=binding['release_aliases']
    assert len(proven)==7
    if alias.startswith(prefix):
        return prefix+proven.get(alias[len(prefix):],alias[len(prefix):])
    return alias

# These descriptive roles are NOT removal eligibility. In particular payload
# can have a public reset value or a protected architectural contract.
PAYLOAD={
 'CdcRead':r'head', 'BusRegAdapter':r'result', 'BridgeSource':r'result',
 'BridgeTarget':r'reply', 'BusFabric':r'result', 'DmaEngine':r'data_[0-9]+',
 'RegBlock':r'response|readFields_value(?:_[0-9]+)?',
 'LiteCore':r'registers_[0-9]+|instruction|storeData|requestBits_data|csr_scratch',
 'LiteBusAdapter':r'payload_.*|result_data', 'MailboxEndpoint':r'staging',
 'SocDebugRoute':r'data|packet_.*', 'DebugMemory':r'result|packet_.*',
 'DebugSba':r'readData|packet_.*', 'SocResetSlot':r'data',
 'SocRetainedMemory':r'result', 'SramDmi':r'value',
 'AonSpi':r'rxShift|txShift', 'SpiHost':r'rxShift|txShift|timestamp',
 'I2cHost':r'rxData|rxShift|txShift', 'QspiEngine':r'rx|tx',
 'QspiScheduler':r'cmdResult|result', 'GeneralTimers':r'captured_[0-9]+',
 'GpioWake':r'packet', 'Fpu':r'response_result',
 'UsbEngine':r'packetData', 'UsbInBuffer':r'stagingData', 'UsbOutBuffer':r'value',
 'UsbControl':r'inData_REG|deviceByte.*|configurationByte.*',
 'phy_rx':r'shift_register_q|rx_data_q', 'phy_tx':r'data_q',
 'sie':r'data_q|in_byte_q|crc16_q', 'fifo_v3':r'mem_q.*',
 'dm_mem':r'rdata_q', 'dm_csrs':r'data_q.*|progbuf_q.*|sbdata_q',
 'dmi_jtag':r'data_q|dr_q', 'ibex_register_file_ff':r'.*rf_reg_q',
 'ibex_id_stage':r'imd_val_q.*', 'ibex_load_store_unit':r'.*rdata.*',
 'ibex_multdiv_fast':r'op_numerator_q|op_quotient_q',
}
def role(item):
    typ=re.sub(r'_[0-9]+$','',item['module'].split('$')[0])
    bank=item['instance'].split('$driver$')[-1]
    pattern=PAYLOAD.get(typ)
    return 'payload' if pattern and re.fullmatch(pattern,bank) else 'control-or-architectural-state'

joins=Counter()
for row in rows:
    matched={}
    for alias in row['q']['aliases']:
        for item in byalias.get(state_alias(alias),[]):
            matched[(item['instance'],item['bit'])]=item
    row['source_state_matches']=list(matched.values())
    joins['multiple' if len(matched)>1 else 'unique' if matched else 'unmatched']+=1
    if matched:
        roles=sorted({role(item) for item in matched.values()})
        row['role']='mixed' if len(roles)>1 else roles[0]
        row['source_roles']=[dict(item,role=role(item)) for item in matched.values()]
    # Missing aliases stay explicit. Source locations are descriptive evidence,
    # never guessed state correspondence or a reset-removal authorization.
    row['reset_removal_authorized']=False
    row['protected']=any(item['instance'].startswith('DeadhorseSoc.digital.core.') for item in matched.values())

# Resolve an optimized double inversion by its real first-stage connection,
# not by treating a surviving consumer alias as a new state element.
for row in rows:
    if row['source_state_matches'] or not row['async_controls']:continue
    if 'clocks.executor.commands.reader.clear' in row['q']['aliases']:
        cell=cells[row['cell']]
        ds=cell['connections']['D'];assert len(ds)==1
        assert 'clocks.executor.dividedClear_s.metastable' in aliases[ds[0]]
        candidates=byalias['clocks.executor.dividedClear_s.stable']
        assert len(candidates)==1 and candidates[0]['module'].split('$')[0]=='CdcSync'
        row['source_state_matches']=candidates
        row['source_roles']=[dict(candidates[0],role='control-or-architectural-state')]
        row['role']='control-or-architectural-state'
        row['identity_note']='CdcSync stable; double inversion leaves FIFO clear alias; actual D is metastable Q'
    elif row['q']['aliases'] and all(a.startswith('digital.core.') for a in row['q']['aliases']):
        file=row['mapped_source']['src'].split(':')[0].split('/')[-1]
        assert file in ('ibex_controller.sv','ibex_cs_registers.sv'), 'Unreviewed optimized core state'
        row['role']='control-or-architectural-state'
        row['identity_note']='Protected controller debug-cause / packed mstatus export; exact bit correspondence not used for mutation'
        row['retained_unresolved_bit_identity']=True
        row['protected']=True

# Existing cadence certificate names the retained island state. Verify actual
# physical-copy controls before using its role; no new cadence claim is made.
reference=ROOT/'build/t33/pre-fast03/fast/usb/timing/usb'
certificate=json.loads((reference/'certificate/result.json').read_text())
preservation=json.loads((base/'island-preservation.json').read_text())
assert preservation['status']=='pass' and preservation['certificate_sha256']==sha(reference/'certificate/result.json')
assert preservation['reference_sha256']==sha(reference/'mapped.json')==certificate['mapped_sha256']
assert certificate['cadence_binding']['status']=='pass'
premap_path=base/'mapped.json'
precanonical=json.loads(premap_path.read_text())['modules']['DeadhorseSoc']
renames=receipt['replica_renames']
assert {renames.get(n,n) for n in precanonical['cells']}==set(cells)
bit_mapping={};inverse_bits={}
for name,cell in precanonical['cells'].items():
    candidate=cells[renames.get(name,name)]
    assert cell['type']==candidate['type'] and cell['parameters']==candidate['parameters']
    assert cell['connections'].keys()==candidate['connections'].keys()
    for pin,bits in cell['connections'].items():
        targets=candidate['connections'][pin];assert len(bits)==len(targets)
        for old,new in zip(bits,targets):
            if isinstance(old,str) or isinstance(new,str):assert old==new;continue
            assert bit_mapping.setdefault(old,new)==new
            assert inverse_bits.setdefault(new,old)==old
reference_module=json.loads((reference/'mapped.json').read_text())['modules']['Usb']
for name in certificate['cadence_binding']['mapped_registers']:
    original=reference_module['cells'][name];candidate=cells[preservation['cells'][name]]
    assert original['type']==candidate['type'] and original['parameters']==candidate['parameters']
    for pin,bits in original['connections'].items():
        expected=[bit_mapping[preservation['bits'][str(b)]] if isinstance(b,int) else b for b in bits]
        assert candidate['connections'][pin]==expected, ('Cadence connection changed',name,pin)
cadence_names={preservation['cells'][name] for name in certificate['cadence_binding']['mapped_registers']}
for row in rows:
    original=row['mapped_source'].get('usb_enable_original')
    if row['cell'] in cadence_names or original:
        if original:
            assert original in cadence_names
            master=cells[original];replica=cells[row['cell']]
            assert replica['type']==master['type']
            assert all(origin(replica['connections'][pin][0])['net']['bit']==
                       origin(master['connections'][pin][0])['net']['bit'] for pin in ('D','CLK','RN'))
        row['role']='control-or-architectural-state'
        row['cadence_certificate']=str(reference/'certificate/result.json')
        row['identity_note']='Retained mapped cadence certificate' + ('; identical D/CLK/RN physical enable copy' if original else '')

bycell={row['cell']:row for row in rows}
ports=defaultdict(list)
for name,port in top['ports'].items():
    for index,bit in enumerate(port['bits']):ports[bit].append(dict(port=name,bit=index,direction=port['direction']))
def cone(bit,seen=()):
    if bit in seen:raise ValueError(('Reset combinational cycle',bit))
    value=dict(net=net(bit))
    if not isinstance(bit,int):value['constant']=bit;return value
    ds=drivers[bit]
    if not ds:value['ports']=ports[bit];return value
    assert len(ds)==1
    name,pin,index=ds[0];cell=cells[name]
    value.update(cell=name,pin=pin,type=cell['type'])
    if name in bycell:
        state=bycell[name]
        value.update(launch_clock=state['clock'],launch_domain=state['clock_domain'],
                     launch_polarity=state['clock_polarity'],source_state_matches=state['source_state_matches'])
    elif not cell['type'].startswith('gf180mcu_fd_sc_mcu7t5v0__'):
        value['macro_boundary']=True
    else:
        value['inputs']={p:[cone(b,(*seen,bit)) for b in bits] for p,bits in cell['connections'].items()
                         if cell['port_directions'][p]=='input'}
    return value
controls=[]
for bit in sorted({key[0] for key in origins},key=str):
    sinks=[dict(cell=r['cell'],pin=c['pin'],clock_domain=r['clock_domain'],role=r['role'])
           for r in rows for c in r['async_controls'] if c['buffer_collapsed_origin']['net']['bit']==bit]
    controls.append(dict(origin=bit,sinks=sinks,cone=cone(bit)))

def launches(value):
    if 'inputs' not in value:return [value]
    return [leaf for values in value['inputs'].values() for item in values for leaf in launches(item)]
control_index={r['origin']:r for r in controls}
for row in rows:
    if not row['async_controls']:continue
    contributing=[]
    for control in row['async_controls']:
        root=control_index[control['buffer_collapsed_origin']['net']['bit']]
        leaves=launches(root['cone'])
        contributing.extend(leaves)
        control['launches']=[dict(cell=l.get('cell'),domain=l.get('launch_domain'),
            clock=l.get('launch_clock'),polarity=l.get('launch_polarity'),
            aliases=l['net']['aliases'],ports=l.get('ports',[])) for l in leaves]
    names={n for leaf in contributing for n in leaf['net']['aliases']}
    # Retain only reset-interface aliases as extra cohort evidence. Ordinary
    # consumers (e.g. watchdogs also driven by coldAon) do not redefine a root.
    names.update(n.removeprefix('DeadhorseSoc.') for leaf in contributing
                 for item in leaf.get('source_state_matches',[]) for n in item['q_aliases']
                 if '.resetDomains.released_' in n)
    owners=[item['instance'] for item in row['source_state_matches']]
    if any('.usb.' in n or '_usbAppUp_' in n for n in names):
        row['cohort']='USB transport (including chip-reset contributions)'
    elif any('released_warm' in n or '_debugger_ndmReset' in n or re.search(r'\.channels_[01]\.channel\.hold\[',n) for n in names):
        row['cohort']='warm (including cold assertion)'
    elif any('released_cold' in n or n in ('porBypass','analog_por_supplyReset_n','externalReset_n') for n in names):
        row['cohort']='debug (cold source; D106 cancellation separately listed)' if any('.debugger.' in n for n in owners) else 'cold'
    else:
        row['cohort']='unresolved'
    if any('CdcPulseCapture'==item['module'].split('$')[0] and item['instance'].endswith('$driver$captured') for item in row['source_state_matches']):
        row['functional_event_contribution']='D113 approved separate listing; all checks retained'

# A release pipeline inherits its source cohort. This is descriptive ownership,
# not a class-B qualification or an exemption for its downstream loads.
for _ in range(len(rows)):
    changed=False
    for row in rows:
        if row['cohort']!='unresolved':continue
        contributors=[entry for control in row['async_controls'] for entry in control['launches']]
        if not contributors or any(c['cell'] not in bycell for c in contributors):continue
        parents=[bycell[c['cell']] for c in contributors]
        if any(not p['source_state_matches'] or any(re.sub(r'_[0-9]+$','',s['module'].split('$')[0])!='ResetRelease'
                 for s in p['source_state_matches']) for p in parents):continue
        cohorts={p['cohort'] for p in parents}
        if len(cohorts)==1 and 'unresolved' not in cohorts:
            row['cohort']=cohorts.pop();changed=True
    if not changed:break
(out/'control-cones.json').write_text(json.dumps(controls,indent=2)+'\n')
blocks=defaultdict(Counter)
for row in rows:
    types={m['module'].split('$')[0] for m in row['source_state_matches']}
    label=' + '.join(sorted(types)) if types else 'unmatched-mapped-state'
    blocks[label]['reset_flops' if row['async_controls'] else 'nonreset_flops']+=1
    blocks[label][row['role']]+=1
(out/'block-summary.json').write_text(json.dumps(dict(blocks),indent=2)+'\n')
def block(row):
    values=set()
    for item in row['source_state_matches']:
        path=item['instance'].removeprefix('DeadhorseSoc.')
        if path.startswith('digital.subsystem.'):
            component=path.split('.')[2]
            values.add('digital.subsystem.'+('glue' if component.startswith('$') else component))
        elif path.startswith('digital.'):
            values.add('.'.join(path.split('.')[:2]))
        else:values.add(path.split('.')[0])
    if not values and row.get('protected'):values.add('digital.core')
    if not values and 'cadence_certificate' in row:values.add('digital.subsystem.usb')
    if not values and not row['async_controls']:
        for alias in row['q']['aliases']:
            if alias.startswith('digital.memory.'):values.add('digital.memory')
            elif alias.startswith('digital.subsystem.usb.'):values.add('digital.subsystem.usb')
        if not values and row['mapped_source'].get('src','').split(':')[0].endswith('/SocResetSlot.sv'):
            assert row['q']['aliases'] and all(n.startswith('usb_boundary_') for n in row['q']['aliases'])
            values.add('digital.subsystem.slot')
    return ' + '.join(sorted(values)) if values else 'unmatched-nonreset-state'
functional=defaultdict(lambda:dict(counts=Counter(),reset_nets=Counter()))
for row in rows:
    group=functional[block(row)]
    group['counts']['reset_flops' if row['async_controls'] else 'nonreset_flops']+=1
    for control in row['async_controls']:
        group['reset_nets'][control['buffer_collapsed_origin']['net']['bit']]+=1
(out/'functional-blocks.json').write_text(json.dumps({name:dict(counts=dict(value['counts']),
    largest_reset_nets=[dict(origin=net(bit),loads=count) for bit,count in value['reset_nets'].most_common(5)])
    for name,value in functional.items()},indent=2)+'\n')
inputs={str(q.resolve()):sha(q)
        for q in (mapped,base/'result.json',lib,hierarchy,base/'island-preservation.json',
                  reference/'certificate/result.json',reference/'mapped.json',premap_path,Path(__file__),
                  ROOT/'hw/top/reference/measurements/reset_inventory.py')}
for name,h in input_hashes.items():assert sha(name)==h, ('Input changed during inventory',name)
inputs.update(input_hashes)
joins=Counter('multiple' if len(r['source_state_matches'])>1 else 'unique' if r['source_state_matches'] else 'unmatched' for r in rows)
result=dict(status='inventory_unclassified',scope='No timing classification, reset removal or exception acceptance',
    mapping_commit=receipt['commit'],input_sha256=inputs,summary=dict(totals),
    source_join_counts=dict(joins),
    unresolved_async_roles=[r['cell'] for r in rows if r['async_controls'] and r['role']=='unreviewed'],
    unresolved_cohorts=[r['cell'] for r in rows if r['async_controls'] and r['cohort']=='unresolved'],
    protected_async_flops=sum(bool(r['async_controls']) and r.get('protected',False) for r in rows),
    retained_unresolved_bit_identity=[r['cell'] for r in rows if r.get('retained_unresolved_bit_identity')],
    other_standard_cell_state_types=other_state,
    largest_buffer_collapsed_controls=[dict(origin=net(bit),sink_pin=pin,loads=n)
        for (bit,pin),n in origins.most_common(20)],flops=rows,
    seconds=time.monotonic()-started)
(out/'inventory.json').write_text(json.dumps(result,indent=2)+'\n')
(out/'receipt.json').write_text(json.dumps(dict(status='descriptive-inventory',
    qualification='No timing exception or reset-removal acceptance',
    input_sha256=inputs,artifact_sha256={str(path.resolve()):sha(path)
        for path in out.rglob('*') if path.is_file() and path.name!='receipt.json'}),indent=2)+'\n')
print(json.dumps({k:result[k] for k in ('status','mapping_commit','summary','seconds')},indent=2))
