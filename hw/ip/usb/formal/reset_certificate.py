"""D51 reset-compatible groups, proved on exact source and mapped pins.

R: root-reset CE state; B: root/bus-reset CE state; H: unreset headers
with bus-reset write suppression; S: EP0 synchronous bus-reset overrides.
Only S -> R is incompatible. No functional non-observability is assumed.
"""
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess

from hw.ip.usb.formal.enable_certificate import aliases, bind_pins


SYNC = {'state':1, 'setupCount':0, 'cursor':0, 'committed':0,
        'addressQ':0, 'addressedQ':0, 'configuredQ':0, 'enabledQ':1,
        'pending':0, 'statusSent':0, 'zlpSent':0, 'flush':1,
        'inToggle':0, 'outToggle':0}
NORMAL = {'total','requested','response','pendingValue','writeCount'}
RX = {'se0_q','cnt_q','state_q','dp_pu_q',
      'rx_valid_qq','rx_err_qq','rx_eop_qq'}


def group(top, name):
    if top=='Usb':
        return group('UsbEngine',name[7:]) if name.startswith('engine.') else None
    if top!='UsbControl':
        if name.startswith('sie.u_phy_tx.') and name.count('.')==2 and name.endswith('_q'):return 'B'
        if name.startswith('sie.u_phy_rx.') and name[13:] in RX:return 'R'
        if name.startswith('sie.') and name.count('.')==1 and name.endswith('_q'):return 'B'
        if not name.startswith('control.'):return None
        name=name[8:]
    if re.fullmatch('header_[0-7]',name):return 'H'
    if name in SYNC:return 'S'
    if name in NORMAL or name=='descriptorLength' or re.fullmatch('decode(?:Valid|Reply|Length|Pending|Value)Q',name):return 'R'
    return None


class Cut:
    def __init__(self,module):
        self.m=copy.deepcopy(module)
        self.n=1+max(b for c in module['cells'].values() for bs in c['connections'].values() for b in bs if isinstance(b,int))
        self.n=max(self.n,1+max(b for v in list(module['ports'].values())+list(module['netnames'].values()) for b in v['bits'] if isinstance(b,int)))
        self.checks={k:[] for k in ('normal','sync','mask','constant','reset')}
    def gate(self,kind,pins,width=1):
        y=list(range(self.n,self.n+width));self.n+=width
        params={'WIDTH':format(width,'b')} if kind=='$mux' else {p+'_WIDTH':format(len(bs),'b') for p,bs in pins.items()}
        if kind!='$mux':params.update(Y_WIDTH=format(width,'b'),A_SIGNED='0');params.update({'B_SIGNED':'0'} if 'B' in pins else {})
        name='$d51_'+str(self.n)
        self.m['cells'][name]=dict(type=kind,parameters=params,attributes={},
            port_directions={**{p:'input' for p in pins},'Y':'output'},connections={**pins,'Y':y})
        return y
    def equal(self,kind,a,b):
        y=self.gate('$eq',{'A':a,'B':b})
        name='d51_'+kind+'_'+str(len(self.checks[kind]))
        self.m['ports'][name]=dict(direction='output',bits=y);self.checks[kind].append(name)
    def free(self,name,cell):
        self.m['ports']['d51_free_'+name]=dict(direction='input',bits=cell['connections']['Q'])
        del self.m['cells'][name]


def extend(top,mapped,liberty,output,receipt,cadence):
    output=Path(output)
    cadence_hash=next(j['source_sha256']['UsbBitEnable.sv'] for j in cadence['cases']['cadence_reset']['jobs'] if j['variant']=='correct')
    for role in ('reset_aware','reset_aware_early'):
        case=cadence.get('cases',{}).get(role,{})
        if case.get('status')!='pass' or {r.get('result') for r in case.get('jobs',[])}!={'proved','covered','fault_rejected'}:
            raise ValueError('Missing D51 reset/restart lemma: '+role)
        if any(j['source_sha256'].get('UsbBitEnable.sv')!=cadence_hash for j in case['jobs'] if j['variant']!='corrupt'):
            raise ValueError('Reset lemma cadence differs from production cadence')
    source=json.loads((output/'source.json').read_text())['modules'][top]
    module=json.loads(Path(mapped).read_text())['modules'][top]
    prefix='engine.' if top=='Usb' else ''
    enable='bitEnable' if top=='UsbControl' else prefix+'cadence.enable'
    root='reset_n' if top=='UsbControl' else prefix+'cadence.reset_n'
    bus='busReset' if top=='UsbControl' else prefix+'sie.bus_reset_o'
    clk='usbClock' if top=='Usb' else 'clk'
    snames=aliases(source);mnames=aliases(module)
    metadata={};others=set();selected=[];bindings={};eliminated=[];source_tests=[];faults=[];not_applicable=[]

    def run(name,cut,mapped_view=False,negative=False):
        path=output/(name+'.json');path.write_text(json.dumps({'modules':{top:cut.m}}))
        preparation=([f'read_liberty -ignore_miss_func {liberty}'] if mapped_view else [])+[f'read_json {path}',f'hierarchy -check -top {top}',
            'flatten','proc','opt_clean','check -assert','techmap','opt']
        scripts=[]
        for kind,checks in cut.checks.items():
            if not checks:continue
            setting={'normal':'-set d51_enable 0','sync':'-set d51_enable 0 -set d51_bus 0',
                     'mask':'-set d51_bus 1','constant':'-set d51_bus 1','reset':''}[kind]
            scripts.append('sat -set-def-inputs '+setting+' '+' '.join('-prove '+p+' 1' for p in checks)+' -verify')
        script=output/(name+'.ys');script.write_text('\n'.join(preparation+scripts)+'\n')
        r=subprocess.run(['yosys','-Q','-T','-s',str(script)],capture_output=True,text=True,timeout=120)
        (output/(name+'.log')).write_text(r.stdout+r.stderr)
        okay=(r.returncode==1 and 'proof did fail' in r.stdout+r.stderr) if negative else (r.returncode==0 and r.stdout.count('SUCCESS!')==len(scripts))
        if not okay:raise ValueError('D51 proof/control failed: '+name)

    def controls(cut,mod):
        def identity(net):
            if mod is source:return source['netnames'][net]['bits']
            targets={alias_bits[label] for bit in source['netnames'][net]['bits']
                     for label in snames[bit] if label in alias_bits}
            if len(targets)!=1:raise ValueError('Missing/ambiguous mapped reset/cadence identity: '+net)
            return list(targets)
        e=identity(enable);r=identity(root);b=identity(bus)
        if any(len(x)!=1 for x in (e,r,b)):raise ValueError('Non-scalar reset/cadence boundary')
        cut.m['ports']['d51_enable']=dict(direction='output',bits=e)
        cut.m['ports']['d51_bus']=dict(direction='output',bits=b)
        return r,cut.gate('$and',{'A':r,'B':cut.gate('$not',{'A':b})})

    scut=Cut(source);r,rb=controls(scut,source)
    for name,c in source['cells'].items():
        if 'dff' not in c['type']:continue
        pins=c['connections'];labels=set().union(*(snames.get(q,set()) for q in pins['Q']))
        groups={group(top,n) for n,_ in labels}-{None}
        if not groups:others.update(labels);scut.free(name,c);continue
        if len(groups)!=1:raise ValueError('Mixed source reset groups')
        g=groups.pop()
        if c['type'] not in ('$adffe','$adff','$dffe','$dff') or int(c['parameters']['CLK_POLARITY'],2)!=1 or pins['CLK']!=source['ports'][clk]['bits']:
            raise ValueError('Unsupported source register semantics: '+str(labels))
        nxt=pins['D']
        if 'EN' in pins:
            en=pins['EN']
            if int(c['parameters']['EN_POLARITY'],2)!=1:en=scut.gate('$not',{'A':en})
            nxt=scut.gate('$mux',{'A':pins['Q'],'B':nxt,'S':en},len(nxt))
        scut.equal('sync' if g=='S' else 'normal',nxt,pins['Q'])
        if g=='H':scut.equal('mask',nxt,pins['Q'])
        if g=='S':
            local_values={SYNC[n.split('.')[-1]] for n,_ in labels if n.split('.')[-1] in SYNC}
            if len(local_values)!=1:raise ValueError('Ambiguous synchronous reset constant')
            val=local_values.pop();constant=list(reversed(format(val,f'0{len(nxt)}b')))
            scut.equal('constant',nxt,constant)
        else:constant=None
        source_tests.append((name,g,constant))
        reset_values=None
        if 'ARST' in pins:
            expected=scut.gate('$not',{'A':rb if g=='B' else r}) if int(c['parameters']['ARST_POLARITY'],2) else (rb if g=='B' else r)
            scut.equal('reset',pins['ARST'],expected)
            reset_values=list(reversed(c['parameters']['ARST_VALUE']))
        elif g!='H':raise ValueError('Missing source reset')
        for i,q in enumerate(pins['Q']):
            bit_labels=snames.get(q,set())
            meta=(g,None if reset_values is None else reset_values[i],None if constant is None else constant[i])
            for label in bit_labels:
                if label in metadata and metadata[label]!=meta:raise ValueError('Ambiguous source alias')
                metadata[label]=meta
            selected.append((bit_labels,meta))
        scut.free(name,c)
    if not selected or set(metadata)&others:raise ValueError('Missing/mixed source aliases')
    run('d51-source',scut)
    # Mutate the actual prepared register, then reconstruct its next-value
    # observation. These controls exercise binding/priority, not just the lemma.
    for fault,g,kind in [('wrong-sync-constant','S','constant'),('missing-header-mask','H','mask')]:
        target=next(((n,c) for n,sg,c in source_tests if sg==g),None)
        if target is None:not_applicable.append(fault);continue
        n,constant=target;bad=copy.deepcopy(source);c=bad['cells'][n];p=c['connections']
        if fault=='wrong-sync-constant':p['D']=['1' if b=='0' else '0' for b in constant]
        if 'EN' in p:p['EN']=source['netnames'][enable]['bits'] if g=='H' else ['1' if int(c['parameters']['EN_POLARITY'],2) else '0']
        else:raise ValueError('Unexpected fault-target source semantics')
        (output/(fault+'-source.json')).write_text(json.dumps({'modules':{top:bad}}))
        cut=copy.deepcopy(scut);cut.checks={k:[] for k in cut.checks}
        en=p['EN'] if int(c['parameters']['EN_POLARITY'],2) else cut.gate('$not',{'A':p['EN']})
        nxt=cut.gate('$mux',{'A':p['Q'],'B':p['D'],'S':en},len(p['Q']))
        cut.equal(kind,nxt,constant if g=='S' else p['Q'])
        run('d51-'+fault,cut,negative=True)
        faults.append(fault)
    alias_bits={(n,i+net.get('offset',0)):bit for n,net in module['netnames'].items()
                for i,bit in enumerate(net['bits'])}
    source_candidate_names={n for n,_ in metadata if group(top,n)}
    for labels in mnames.values():
        if any(n in source_candidate_names and (n,i) not in metadata for n,i in labels):
            raise ValueError('Recoded or ambiguous reset-qualified alias')
    connected={b for c in module['cells'].values() for bs in c['connections'].values() for b in bs}
    connected.update(b for p in module['ports'].values() for b in p['bits'])
    qcells={c['connections']['Q'][0]:n for n,c in module['cells'].items() if 'CLK' in c['connections']}
    for labels,meta in selected:
        targets={alias_bits[label] for label in labels if label in alias_bits}
        if len(targets)!=1:raise ValueError('Missing/ambiguous source-to-mapped identity: '+str(labels))
        bit=targets.pop()
        if isinstance(bit,str) or bit not in connected:eliminated.append(sorted(labels));continue
        name=qcells.get(bit)
        if not name or mnames.get(bit,set())&others:raise ValueError('Mixed/non-register mapped alias')
        if name in bindings and bindings[name]!=meta:raise ValueError('Merged incompatible reset groups')
        bindings[name]=meta
    mcut=Cut(module);r,rb=controls(mcut,module)
    for name,c in module['cells'].items():
        if 'CLK' not in c['connections']:continue
        if name in bindings:
            g,rv,sv=bindings[name];p=c['connections']
            bind_pins(module,{name:dict(launch=name+'/Q',capture=name+'/D')})
            if p['CLK']!=module['ports'][clk]['bits']:raise ValueError('Mapped clock mismatch')
            mcut.equal('sync' if g=='S' else 'normal',p['D'],p['Q'])
            if g=='H':mcut.equal('mask',p['D'],p['Q'])
            if g=='S':mcut.equal('constant',p['D'],[sv])
            reset_pins=[pin for pin in ('RN','SETN') if pin in p]
            if rv is None:
                if reset_pins:raise ValueError('Unexpected mapped header reset')
            else:
                if len(reset_pins)!=1 or rv!=('1' if reset_pins[0]=='SETN' else '0'):raise ValueError('Mapped reset value differs: '+str((name,c['type'],rv,reset_pins,mnames.get(p['Q'][0]))))
                mcut.equal('reset',p[reset_pins[0]],rb if g=='B' else r)
        mcut.free(name,c)
    # Only proved replica equalities may constrain the otherwise free-Q model.
    from tools.timing.usb_enable_fanout import identities,PREFIX
    copies=identities(module)
    for c in mcut.m['cells'].values():
        c['connections']={p:[copies.get(b,b) for b in bs] for p,bs in c['connections'].items()}
    for n in module['cells']:
        if n.startswith(PREFIX):del mcut.m['ports']['d51_free_'+n]
    run('d51-mapped',mcut,True)
    target=next(n for n,meta in bindings.items() if meta[1] is not None)
    bad=copy.deepcopy(module);pin='SETN' if bindings[target][1]=='1' else 'RN'
    bad['cells'][target]['connections'][pin]=['1']
    (output/'wrong-reset-aware-pin-mapped.json').write_text(json.dumps({'modules':{top:bad}}))
    cut=copy.deepcopy(mcut);cut.checks={k:[] for k in cut.checks}
    cut.equal('reset',bad['cells'][target]['connections'][pin],rb if bindings[target][0]=='B' else r)
    run('d51-wrong-reset-aware-pin',cut,True,negative=True)
    try:bind_pins(module,{target:dict(launch=target+'/Q',capture=target+'/CLK')})
    except ValueError:pass
    else:raise ValueError('Wrong newly classified register pin escaped')
    faults.extend(['wrong-reset-aware-pin','wrong-classified-pin'])
    groups={g:sorted(n for n,meta in bindings.items() if meta[0]==g) for g in ('R','B','H','S')}
    allowed=[(a,b) for a in groups for b in groups if not(a=='S' and b=='R')]
    receipt['d48_certified']=receipt['certified']
    receipt['certified']={n:dict(launch=n+'/Q',capture=n+'/D') for n in bindings}
    receipt['full_rate']=sorted(set(qcells.values())-set(bindings))
    receipt['reset_aware']=dict(decision='D51',groups=groups,allowed_pairs=allowed,
        incompatible_pairs=[('S','R')],source_register_bits=len(selected),eliminated_unused=eliminated,
        scope='Root assertion suppresses all normal captures; production cadence delays restart. Bus reset changes only on CE. Synchronous reset constants suppress affected data captures while busReset is high; the proved reset-aware lemma excludes early captures afterward. S-to-R remains single-cycle.',
        source_mapped_proof='Actual next value/hold, synchronous reset constants, header masks, clock/reset pins and polarity/value are proved; all unrelated state free',
        cadence_emitted_sha256=cadence_hash,
        temporal_receipt_sha256=hashlib.sha256(json.dumps(cadence,sort_keys=True).encode()).hexdigest(),
        temporal_assumptions=cadence['assumptions'],
        boundary_contract=('Standalone EP0: conditional on bitEnable production cadence and busReset producer changing only on that enable, reset by the same root; both producer guarantees are discharged by the integrated engine certificate' if top=='UsbControl' else 'Integrated cadence and bus-reset producer identities/phase/root are bound by the source/mapped certificate'),
        excluded_reset_launch='PHY bus_reset_q stays full-rate because it drives synchronous EP0 reset-as-data captures on the next sample',
        negative_controls=faults,not_applicable_controls=not_applicable,
        limitations='Sampled digital proof, not physical inter-edge reset skew or pad signoff')
    receipt['proof_source_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in
        (Path('hw/ip/usb/formal/enable_certificate.py'),Path(__file__).relative_to(Path.cwd()),Path('tools/timing/usb_enable_fanout.py'))}
    receipt['status']='pass'
    (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt
