"""Mapped-graph checks for physical-only insertion and raw reset containment."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import itertools

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def drivers(module):
    result={}
    for name,port in module['ports'].items():
        if port['direction']=='input':
            for i,b in enumerate(port['bits']):result[b]=('port',name,i)
    for name,cell in module['cells'].items():
        for pin,bits in cell['connections'].items():
            if cell['port_directions'][pin]=='output':
                for i,b in enumerate(bits):
                    if b in result:raise ValueError('Multiple drivers')
                    result[b]=('cell',name,pin,i)
    return result

def equivalent(before,after):
    """Exact original connectivity after collapsing only inserted buffers/ties."""
    original=set(before['cells']);extra=set(after['cells'])-original
    if original-set(after['cells']):raise ValueError('Original cell removed')
    if set(before['ports'])!=set(after['ports']):raise ValueError('Ports changed')
    for name in extra:
        if not re.fullmatch(r'gf180mcu_fd_sc_mcu7t5v0__(?:clkbuf_\d+|buf_\d+|clkinv_\d+|inv_\d+|tieh|tiel)',after['cells'][name]['type']):
            raise ValueError('Unexpected physical cell: '+name)
    def resolver(module,inserted):
        driven=drivers(module)
        def bit(b,seen=()):
            if b in ('0','1'):return b
            if b in seen:raise ValueError('Combinational physical loop')
            d=driven.get(b)
            if d is None:raise ValueError('Undriven net')
            if d[0]=='port' or d[1] not in inserted:return d
            cell=module['cells'][d[1]];kind=cell['type'].split('__')[1];c=cell['connections']
            if kind in ('tieh','tiel'):return '1' if kind=='tieh' else '0'
            if len(c.get('I',[]))!=1:raise ValueError('Malformed physical buffer')
            value=bit(c['I'][0],(*seen,b))
            if 'inv_' in kind:
                if value in ('0','1'):return str(1-int(value))
                return value[1] if value[0]=='not' else ('not',value)
            return value
        return bit
    left,right=resolver(before,set()),resolver(after,extra)
    for name,cell in before['cells'].items():
        new=after['cells'][name]
        if (cell['type']!=new['type'] or cell['port_directions']!=new['port_directions'] or
            cell.get('parameters',{})!=new.get('parameters',{}) or
            any(d not in ('input','output') for d in cell['port_directions'].values())):raise ValueError('Original cell changed: '+name)
        for pin,direction in cell['port_directions'].items():
            if direction=='input' and [left(b) for b in cell['connections'][pin]]!=[right(b) for b in new['connections'][pin]]:
                raise ValueError('Original pin changed: '+name+'/'+pin)
    for name,port in before['ports'].items():
        new=after['ports'][name]
        if (port['direction'],len(port['bits']))!=(new['direction'],len(new['bits'])):raise ValueError('Port shape changed')
        if port['direction']=='output' and [left(b) for b in port['bits']]!=[right(b) for b in new['bits']]:raise ValueError('Output changed')
    return dict(status='pass',original_cells=len(original),inserted_cells=len(extra),
                qualification='Exact logical original pins/outputs preserved; inserted buffers/inverters/ties only')

def reset_chains(module):
    """Qualify raw reset topology, never analog metastability or reset timing."""
    roots={'appReset_n','usbReset_n','aonReset_n'};driven=drivers(module)
    rootbits={module['ports'][p]['bits'][0]:p for p in roots}
    def value(b,assignment,seen=()):
        if b in rootbits:return assignment[rootbits[b]]
        if b in ('0','1'):return b=='1'
        if b in seen:raise ValueError('Reset cone loop')
        d=driven.get(b)
        if not d or d[0]!='cell':raise ValueError('Unqualified reset-cone input')
        c=module['cells'][d[1]];kind=c['type'].split('__')[-1]
        pins={p:[value(x,assignment,(*seen,b)) for x in bs] for p,bs in c['connections'].items() if c['port_directions'][p]=='input'}
        if re.fullmatch(r'buf_\d+',kind):return pins['I'][0]
        if re.fullmatch(r'inv_\d+',kind):return not pins['I'][0]
        if re.fullmatch(r'and2_\d+',kind):return pins['A1'][0] and pins['A2'][0]
        if re.fullmatch(r'nand2_\d+',kind):return not (pins['A1'][0] and pins['A2'][0])
        raise ValueError('Unqualified raw reset function: '+kind)
    def dependencies(b,seen=()):
        if b in rootbits:return {rootbits[b]}
        if b in ('0','1'):return set()
        if b in seen:raise ValueError('Reset cone loop')
        d=driven.get(b)
        if not d or d[0]=='port':return set()
        c=module['cells'][d[1]]
        if 'CLK' in c['connections']:return set()
        return set().union(*(dependencies(x,(*seen,b)) for p,bs in c['connections'].items() if c['port_directions'][p]=='input' for x in bs))
    consumers={}
    for name,c in module['cells'].items():
        for pin,bits in c['connections'].items():
            if c['port_directions'][pin]=='input':
                for b in bits:consumers.setdefault(b,[]).append((name,pin))
    groups={}
    for name,c in module['cells'].items():
        if 'CLK' not in c['connections']:continue
        for pin,bits in c['connections'].items():
            if c['port_directions'][pin]!='input':continue
            dep=set().union(*(dependencies(b) for b in bits))
            if dep:
                if pin!='RN' or not re.fullmatch(r'gf180mcu_fd_sc_mcu7t5v0__dffrnq_\d+',c['type']):raise ValueError('Raw reset bypasses release chain: '+name+'/'+pin)
                key=(tuple(bits),tuple(c['connections']['CLK']));groups.setdefault(key,[]).append(name)
    rows=[];domains=set()
    for (rn,clock),names in groups.items():
        if len(names)!=2:raise ValueError('Raw reset group is not exactly a two-flop chain')
        first=[n for n in names if module['cells'][n]['connections']['D']==['1']]
        if len(first)!=1:raise ValueError('Release chain constant/stage mismatch')
        first=first[0];second=next(n for n in names if n!=first)
        a,b=(module['cells'][n]['connections'] for n in (first,second))
        if b['D']!=a['Q'] or consumers.get(a['Q'][0])!=[(second,'D')]:raise ValueError('Reset first stage leaks or second stage bypassed')
        if any(a['Q'][0] in p['bits'] for p in module['ports'].values() if p['direction']!='input'):raise ValueError('Reset first stage exposed at output')
        domain=[n for n,p in module['ports'].items() if tuple(p['bits'])==clock and n in ('appClock','usbClock','aonClock')]
        if len(domain)!=1:raise ValueError('Wrong reset clock')
        domain=domain[0];domains.add(domain)
        expected={'aonReset_n'} if domain=='aonClock' else {'appReset_n','usbReset_n'}
        if dependencies(rn[0])!=expected:raise ValueError('Wrong reset source containment')
        for values in itertools.product((False,True),repeat=3):
            assignment=dict(zip(sorted(roots),values))
            if value(rn[0],assignment)!=all(assignment[p] for p in expected):raise ValueError('Wrong asynchronous reset assertion function')
        rows.append(dict(first=first,second=second,clock=domain,raw_resets=sorted(expected),
                         structural_status='two local stages; asynchronous RN; first Q isolated'))
    if domains!={'appClock','usbClock','aonClock'}:raise ValueError('Incomplete raw reset-domain inventory')
    return dict(status='structurally-qualified',chains=rows,
                remaining='Physical interstage timing, recovery/removal, minimum reset pulse and metastability characterization; no false paths granted')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--before',type=Path,required=True);p.add_argument('--after',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();before=json.loads(a.before.read_text())['modules']['Usb'];after=json.loads(a.after.read_text())['modules']['Usb']
    result=dict(before_sha256=sha(a.before),after_sha256=sha(a.after),connectivity=equivalent(before,after),rdc=reset_chains(before))
    # Preservation of every original pin (including CLK and RN) carries the
    # checked chain onto the physical graph through the inserted buffer trees.
    a.output.write_text(json.dumps(result,indent=2)+'\n');print('PASS physical connectivity; reset topology structurally qualified only')
