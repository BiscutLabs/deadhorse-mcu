"""Enumerate mapped data/reset origins. Inventory is not CDC/RDC qualification."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from hw.top.reference.measurements.plan04_screen import clock_manifest
from tools.timing.usb_boundary import groups


def reset_event_contract(module,clocks,liberty):
    """Check the polarity used for cohort normalization against actual Liberty."""
    types={module['cells'][name.rsplit('/',1)[0]]['type'] for name in clocks}
    library=dict(groups(liberty,'cell'));result={}
    for typ in sorted(types):
        if typ not in library:raise ValueError('Missing register cell '+typ)
        ffs=list(groups(library[typ],'ff'))
        if len(ffs)!=1:raise ValueError('Unsupported register state '+typ)
        controls={}
        for attribute,pin in (('clear','RN'),('preset','SETN')):
            expressions=re.findall(r'\b'+attribute+r'\s*:\s*"([^"]+)"\s*;',ffs[0][1])
            if expressions:
                if len(expressions)!=1 or re.sub(r'[\s()]','',expressions[0])!='!'+pin:
                    raise ValueError('Unsupported reset polarity '+typ+'/'+attribute)
                controls[pin]='active_low'
        for name in clocks:
            cell=module['cells'][name.rsplit('/',1)[0]]
            if cell['type']==typ and set(controls)!={p for p in ('RN','SETN') if p in cell['connections']}:
                raise ValueError('Reset pin inventory disagrees with Liberty '+typ)
        result[typ]=controls
    return result


def inventory(module,clocks):
    cells=module['cells'];drivers={};leaves=[];leaf_bits={};memo={}
    def leaf(bit,description):
        if bit not in leaf_bits:
            leaf_bits[bit]=1<<len(leaves);leaves.append(description)
    for name,c in cells.items():
        for pin,bits in c['connections'].items():
            if c['port_directions'][pin]=='output':
                for b in bits:
                    if isinstance(b,int):
                        if b in drivers:raise ValueError('Multiple drivers')
                        drivers[b]=(name,c,pin)
    registers={}
    for clock_pin,domain in clocks.items():
        name,pin=clock_pin.rsplit('/',1);c=cells[name]
        registers[name]=dict(domain=domain,clock_pin=pin)
        for output,bs in c['connections'].items():
            if c['port_directions'][output]=='output':
                for b in bs:leaf(b,dict(kind='register',name=name,pin=output,domain=domain))
    for name,p in module['ports'].items():
        if p['direction']=='input':
            for index,b in enumerate(p['bits']):
                if isinstance(b,int):leaf(b,dict(kind='port',name=name,pin=str(index),domain='external'))
    def origins(bit,active=None):
        if isinstance(bit,str):
            if bit not in ('0','1'):raise ValueError('Unknown constant in functional cone: '+bit)
            return 0
        if bit in leaf_bits:return leaf_bits[bit]
        if bit in memo:return memo[bit]
        active=set() if active is None else active
        if bit in active:raise ValueError('Combinational loop')
        if bit not in drivers:raise ValueError('Undriven functional bit '+str(bit))
        active=active|{bit};_,c,_=drivers[bit];mask=0
        for pin,bs in c['connections'].items():
            if c['port_directions'][pin]=='input':
                for b in bs:mask|=origins(b,active)
        memo[bit]=mask;return mask
    def reset_root(bit):
        seen=set()
        while isinstance(bit,int) and bit in drivers:
            if bit in seen:raise ValueError('Reset buffer cycle')
            seen.add(bit);_,c,_=drivers[bit]
            if not re.fullmatch(r'gf180mcu_fd_sc_mcu7t5v0__buf_[1248]',c['type']):break
            bits=c['connections']['I']
            if len(bits)!=1:raise ValueError('Wide reset buffer')
            bit=bits[0]
        return bit
    for name,row in registers.items():
        row['resets']=[(pin,reset_root(b)) for pin in ('RN','SETN') for b in cells[name]['connections'].get(pin,[])]
        if any(isinstance(b,str) and b not in ('0','1') for _,b in row['resets']):
            raise ValueError('Unknown reset constant')
        # In the pinned GF180 cells RN and SETN both assert low. They differ
        # in reset VALUE, not the event which defines a reset cohort. Retain
        # the raw pin inventory, without declaring different roots equivalent.
        row['reset_events']=sorted({b for _,b in row['resets']},key=str)
    def describe(mask):
        while mask:
            bit=mask&-mask;yield leaves[bit.bit_length()-1];mask^=bit
    rows=[];counts=dict(registers=len(registers),cdc_candidates=0,rdc_candidates=0,external_data=0,reset_origins=0)
    for name,destination in registers.items():
        for pin in ('D','RN','SETN'):
            for index,b in enumerate(cells[name]['connections'].get(pin,[])):
                for source in describe(origins(b)):
                    kind='reset' if pin!='D' else 'external' if source['kind']=='port' else \
                        'cdc' if source['domain']!=destination['domain'] else \
                        'rdc' if registers[source['name']]['reset_events']!=destination['reset_events'] else 'local'
                    if kind=='local':continue
                    key=dict(reset='reset_origins',external='external_data',cdc='cdc_candidates',rdc='rdc_candidates')[kind]
                    counts[key]+=1
                    rows.append(dict(kind=kind,source=source['name']+'/'+source['pin'],
                        source_domain=source['domain'],destination=name+'/'+pin,
                        destination_bit=index,destination_domain=destination['domain']))
    return counts,rows,registers


def main(base):
    base=(ROOT/base).resolve();base.relative_to(ROOT/'build')
    out=base/'crossing-inventory';out.mkdir(exist_ok=False)
    mapped=base/'map/canonical.json';receipt_path=base/'map/result.json'
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    receipt=json.loads(receipt_path.read_text())
    assert receipt['status']=='mapped' and digest(mapped)==receipt['mapped_sha256']
    module=json.loads(mapped.read_text())['modules']['DeadhorseSoc']
    clocks=clock_manifest(module)
    libraries=[ROOT/p for p,h in receipt['input_sha256'].items()
               if p.endswith('.lib') and h==receipt['liberty_sha256']]
    if len(libraries)!=1 or digest(libraries[0])!=receipt['liberty_sha256']:
        raise ValueError('Missing or stale mapped Liberty')
    reset_controls=reset_event_contract(module,clocks,libraries[0].read_text())
    counts,rows,registers=inventory(module,clocks)
    with (out/'paths.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['kind','source','source_domain','destination','destination_bit','destination_domain'])
        writer.writeheader();writer.writerows(rows)
    (out/'registers.json').write_text(json.dumps(registers,indent=2)+'\n')
    result=dict(status='inventoried_not_qualified',counts_measured=counts,reset_event_contract=reset_controls,
        scope='Structural data cones and reset origins; no synchronization, reconvergence, metastability or reset-epoch waiver. RDC candidates are same-clock/different-reset only; different-clock paths are CDC even when resets also differ. Raw distinct reset roots produce candidates even when logically equivalent.',
        input_sha256={p.relative_to(ROOT).as_posix():digest(p) for p in
            (mapped,receipt_path,libraries[0],Path(__file__),Path(__file__).with_name('plan04_screen.py'),ROOT/'tools/timing/usb_boundary.py')},
        artifact_sha256={p.name:digest(p) for p in out.iterdir() if p.is_file()})
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--base',required=True)
    main(parser.parse_args().base)
