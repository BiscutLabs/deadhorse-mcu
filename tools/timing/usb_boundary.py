"""Estimated USB integration contract, not pad/board or fast-corner signoff."""
import hashlib
import math
from pathlib import Path
import re


def groups(text, kind):
    """Read balanced Liberty groups from the pinned library, never RTL."""
    for match in re.finditer(r'\b'+kind+r'\s*\(([^)]*)\)\s*\{', text):
        depth=1; end=match.end()
        while depth and end<len(text):
            depth+=(text[end]=='{')-(text[end]=='}');end+=1
        if depth:raise ValueError('Truncated Liberty group')
        yield match.group(1).strip().strip('"'),text[match.end():end-1]


def table_range(body, x_range=(0.02,0.5), y_range=(0.001,0.05)):
    def values(kind):
        m=re.search(r'\b'+kind+r'\s*\((.*?)\)\s*;',body,re.S)
        if not m:raise ValueError('Missing Liberty '+kind)
        return [float(v) for v in re.findall(r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?',m.group(1))]
    xs,ys,z=values('index_1'),values('index_2'),values('values')
    if len(z)!=len(xs)*len(ys) or any(not math.isfinite(v) for v in xs+ys+z):raise ValueError('Malformed Liberty table')
    if any(a>=b for axis in (xs,ys) for a,b in zip(axis,axis[1:])):raise ValueError('Invalid Liberty axes')
    if not (xs[0]<=x_range[0]<=x_range[1]<=xs[-1] and ys[0]<=y_range[0]<=y_range[1]<=ys[-1]):raise ValueError('Contract outside characterized table')
    def at(x,y):
        i=next(i for i in range(len(xs)-1) if xs[i]<=x<=xs[i+1])
        j=next(j for j in range(len(ys)-1) if ys[j]<=y<=ys[j+1])
        a=(x-xs[i])/(xs[i+1]-xs[i]);b=(y-ys[j])/(ys[j+1]-ys[j])
        return sum(z[(i+di)*len(ys)+j+dj]*wx*wy for di,wx in ((0,1-a),(1,a)) for dj,wy in ((0,1-b),(1,b)))
    # Bilinear extrema occur at corners of each intersecting grid rectangle.
    samples=[at(x,y) for x in sorted(set(x_range)|{v for v in xs if x_range[0]<v<x_range[1]})
                     for y in sorted(set(y_range)|{v for v in ys if y_range[0]<v<y_range[1]})]
    return min(samples),max(samples)


def characterize(liberty):
    raw=Path(liberty).read_bytes();text=raw.decode()
    cell='gf180mcu_fd_sc_mcu7t5v0__dffrnq_1'
    cells=[b for n,b in groups(text,'cell') if n==cell]
    if len(cells)!=1:raise ValueError('Missing reset source cell')
    pins=[b for n,b in groups(cells[0],'pin') if n=='Q']
    if len(pins)!=1:raise ValueError('Missing reset source Q')
    arcs=[b for _,b in groups(pins[0],'timing') if re.search(r'related_pin\s*:\s*"CLK"',b) and re.search(r'timing_type\s*:\s*rising_edge',b)]
    cq=[table_range(b) for a in arcs for _,b in groups(a,'cell_rise')]
    slew=[table_range(b) for a in arcs for _,b in groups(a,'rise_transition')]
    if not cq or not slew:raise ValueError('Missing reset CLK-to-Q tables')
    return dict(cell=cell,library_sha256=hashlib.sha256(raw).hexdigest(),
        assumed_clock_slew_ns=[0.02,0.5],assumed_q_load_pf=[0.001,0.05],
        cq_min_ns=min(v[0] for v in cq),cq_max_ns=max(v[1] for v in cq),
        rise_transition_max_ns=max(v[1] for v in slew),
        method='Bilinear extrema over every grid rectangle intersecting the assumed slew/load envelope; pinned SS corner only')


def contract(top, characterization=None):
    if top not in ('UsbEngine', 'Usb'):
        return None
    clock = 'usbClock' if top == 'Usb' else 'block_clock'
    inputs = {p: dict(clock=clock, minimum=0.0, maximum=2.0, edge='both')
              for p in ('dpRx', 'dnRx', 'vbus')}
    resets = ({'appReset_n': 'appClock', 'usbReset_n': 'usbClock', 'aonReset_n': 'aonClock'}
              if top == 'Usb' else {'reset_n': clock})
    for port, source_clock in resets.items():
        inputs[port] = dict(clock=source_clock, minimum=2.420, maximum=3.882108633, edge='rise', transition=2.4)
        if characterization:
            inputs[port].update(minimum=characterization['cq_min_ns'],maximum=characterization['cq_max_ns'],
                transition=math.ceil(characterization['rise_transition_max_ns']*10)/10)
    outputs = {p: dict(clock=clock, minimum=0.0, maximum=2.0)
               for p in ('dpTx', 'dnTx', 'txEnable', 'pullupEnable' if top == 'Usb' else 'pullup_0')}
    return dict(top=top,inputs=inputs, outputs=outputs, provenance='estimated',characterization=characterization,
        pad_basis='0..2 ns = assumed 0..1 ns pad plus 0..1 ns package/board. RX/VBUS asynchronous: min=0 preserves first-sampler diagnostics, no source-synchronous phase guarantee.',
        reset_basis='Upstream dffrnq_1 synchronized deassertion, rising CLK-to-Q at pinned SS/125C/3V. Assumed clock slew 0.02..0.5 ns and Q load 0.001..0.05 pF: table minimum 2.420 ns, interpolated maximum 3.882108633 ns. Estimated output transition 2.4 ns rounds the approximately 2.363 ns characterized rising transition upward. Assertion remains asynchronous; peer-domain reset phase is not guaranteed. No delay is added to internal synchronizer outputs.',
        limitations='Pre-layout integration requirements; upstream implementation, pads, board, fast-corner hold, CTS and analog reset qualification remain open.')


def validate(value, module, clocks):
    expected=contract(value['top'])
    for kind, direction in (('inputs','input'),('outputs','output')):
        if set(value[kind])!=set(expected[kind]):raise ValueError('Incomplete USB boundary inventory')
        for name,row in value[kind].items():
            if module['ports'].get(name,{}).get('direction')!=direction or len(module['ports'][name]['bits'])!=1:
                raise ValueError('Missing/non-scalar USB contracted '+direction+': '+name)
            if (row['clock'] not in clocks or row['clock']!=expected[kind][name]['clock'] or
                row.get('edge','both')!=expected[kind][name].get('edge','both') or
                any(type(row[k]) not in (int,float) or not math.isfinite(row[k]) for k in ('minimum','maximum')) or
                not 0<=row['minimum']<=row['maximum']):
                raise ValueError('Invalid USB contract clock/delay')
            if direction=='input' and name in ('dpRx','dnRx','vbus') and row['minimum']!=0:
                raise ValueError('Asynchronous pad phase cannot have a positive minimum')


def reset_sinks(value, module):
    """Conservative combinational cone inventory, stopping at every FF Q."""
    clocks={tuple(p['bits']):('block_clock' if value['top']=='UsbEngine' else n)
            for n,p in module['ports'].items() if n in ('clk','appClock','usbClock','aonClock')}
    rows=[]
    for port,entry in value['inputs'].items():
        if entry['edge']!='rise':continue
        reached=set(module['ports'][port]['bits'])
        while True:
            before=set(reached)
            for c in module['cells'].values():
                if 'CLK' in c['connections']:continue
                if any(reached.intersection(bits) for p,bits in c['connections'].items() if c['port_directions'][p]=='input'):
                    reached.update(b for p,bits in c['connections'].items() if c['port_directions'][p]=='output' for b in bits if isinstance(b,int))
            if before==reached:break
        found=[]
        for name,c in module['cells'].items():
            if 'CLK' not in c['connections']:continue
            domain=clocks.get(tuple(c['connections']['CLK']))
            if not domain:raise ValueError('Unknown reset sink clock')
            for pin in ('RN','SETN'):
                if reached.intersection(c['connections'].get(pin,[])):
                    found.append(dict(port=port,pin=name+'/'+pin,source_clock=entry['clock'],capture_clock=domain,
                        qualification='conditional owner-domain release' if domain==entry['clock'] else 'peer-domain RDC unqualified'))
        if not found:raise ValueError('Reset input has no mapped asynchronous reset sink')
        rows.extend(found)
    return rows


def tcl_rows(rows):
    return ' '.join('{'+ ' '.join(map(str, (port, row['clock'], row['minimum'], row['maximum'], row.get('edge', 'both'),row.get('transition',0.5))))+'}'
                    for port, row in rows.items())


def output_pass(rows):
    import math
    return bool(rows) and all(math.isfinite(float(r['slack_ns'])) and float(r['slack_ns'])>=0 for r in rows)


def read_output_checks(path, outputs):
    import csv
    with Path(path).open() as stream:rows=list(csv.DictReader(stream,delimiter='\t'))
    expected={(p,m) for p in outputs for m in ('max_rise','max_fall','min_rise','min_fall')}
    if {(r['end'],r['check']) for r in rows}!=expected:raise ValueError('Incomplete output setup/hold coverage')
    for row in rows:
        row['slack_ns']=float(row['slack_ns'])
        if not row['start'] or not math.isfinite(row['slack_ns']):raise ValueError('Invalid USB output slack')
    return rows


def audit_runs(output, tcl, run, value):
    """Same netlist: complete output checks, physical faults and raw comparison."""
    import csv
    positive=read_output_checks(output/'output_checks.tsv',value['outputs'])
    original=tcl.read_text()
    def analyze(label,text):
        directory=output/label;directory.mkdir()
        for filename in ('paths.tsv','gate_checks.tsv'):
            text=text.replace(str(output/filename),str(directory/filename))
        script=directory/'timing.tcl';script.write_text(text)
        log=run(['sta','-no_init','-exit',str(script)],output,label)
        if 'TIMING_COMPLETE' not in log or re.search(r'(?im)^Error:|not a valid (?:start|end) point',log):
            raise ValueError('Incomplete boundary audit '+label)
        return directory
    old_outputs='set usb_output_contract {'+tcl_rows(value['outputs'])+'}'
    excessive={p:dict(row,maximum=row['maximum']+1000.0) for p,row in value['outputs'].items()}
    directory=analyze('output-delay-fault',original.replace(old_outputs,'set usb_output_contract {'+tcl_rows(excessive)+'}'))
    fault=read_output_checks(directory/'output_checks.tsv',value['outputs'])
    if output_pass(fault):raise ValueError('Excessive output-delay fault escaped')
    old_inputs='set usb_input_contract {'+tcl_rows(value['inputs'])+'}'
    directory=analyze('zero-delay-reference',original.replace(old_inputs,'').replace(old_outputs,''))
    def safety(directory):
        with (directory/'short_reset_checks.tsv').open() as stream:rows=list(csv.DictReader(stream,delimiter='\t'))
        if not rows:raise ValueError('Missing boundary hold/reset audit')
        for row in rows:
            row['slack_ns']=float(row['slack_ns'])
            if not math.isfinite(row['slack_ns']):raise ValueError('Invalid boundary audit slack')
        return rows
    raw=safety(directory)
    result=dict(output_checks=positive,output_checks_pass=output_pass(positive),
        output_delay_fault=dict(status='fault_rejected',extra_delay_ns=1000.0,worst_slack_ns=min(r['slack_ns'] for r in fault)),
        zero_delay_reference=dict(hold_reset_checks=raw,violations=[r for r in raw if r['slack_ns']<0],
            interpretation='Original all-domain zero-arrival diagnostic; includes asynchronous/peer-domain reset-phase checks, not signoff'))
    if value['top']=='Usb':
        wrong={p:dict(row,minimum=0.0) if row['edge']=='rise' else row for p,row in value['inputs'].items()}
        directory=analyze('zero-release-fault',original.replace(old_inputs,'set usb_input_contract {'+tcl_rows(wrong)+'}'))
        violations=[r for r in safety(directory) if r['check'].startswith('reset/min') and r['start']=='aonReset_n' and r['slack_ns']<0]
        if not violations:raise ValueError('Zero-clock-to-Q reset-release fault escaped')
        result['zero_release_fault']=dict(status='fault_rejected',violations=violations)
    return result
