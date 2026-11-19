"""D58 relational induction on every engine/wrapper state and output.

Only packet flags may differ off CE. All other Q values are coupled arbitrary
inputs; their complete next-state/control functions must agree in every phase.
The actual flag and cadence machines remain sequential. This over-approximation
requires neither producer stability nor assumptions about consumer sampling.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

BASELINE = '099c27f8d9ab719eb54dceaecab0cfc95ee97aa1'
BASELINE_EMISSION = {'engine': {'banks_8x8.sv': '94ab1701d0c08634c1a29be639017d2a688392debd33fd3e738467f8a2e32d78', 'phy_rx.v': '7e5b81845160514dc9869bf86a05f36cc80ed0b97267e6f8ddc16c2a1f939c0c', 'phy_tx.v': '82c3ba96c5c8aca8ec6846b4bb75332102bfba4b5f154f6502f0752858eef775', 'ResetRelease.sv': '3cf3bb9ebd8c7babc806c12d1702ab1f57084680b880d2146baefb50fc6116b0', 'sie.v': '4e2dd686707d7daf6e56862173aaf0d90772bafa5176073b66a7bb74bd101fe1', 'UsbBitEnable.sv': 'e7af93dcd7592b9535aa268a2fa3e53247ff972d8829df8527965b2925f8df8e', 'UsbControl.sv': '7771f666c00ba8df933648d5c8f508c52c9a28259e3e796044fa64caaade2a0d', 'UsbEngine.sv': 'cf0a56a7c74d448852a5f7d09447b93f3ab5d1903a883748a04c899ad8729a00', 'UsbInBuffer.sv': '7801fc5eaa86d9ec56ef029844029214e8df41a2b0e79747eb536517a8086d79', 'UsbOutBuffer.sv': '50633323f04b8749af4764326f8d77a0cdd736619cf33e2256db3460f36ce26b', 'UsbPacketMemory.sv': 'b955d7420836a4b59d5cf2b49343c72187ed09e81bc524197027b327fa3f4981', 'UsbPadSafety.sv': '90d2c7471ebfa3380b5e69862a7f437138a5777ffd0d1bea3b864476ba91ebf7'}, 'usb': {'banks_8x8.sv': '94ab1701d0c08634c1a29be639017d2a688392debd33fd3e738467f8a2e32d78', 'BusRegAdapter.sv': 'ba91f14348b63a6f104e278704ee3749d06953385e27244ca40e91d2bd5419b5', 'CdcFifo.sv': '5d236ed84ead587f7168992317e0cff3e5cc55dfb1cea8411839be8166d987d7', 'CdcFifo_2.sv': '72e4be679bbe868fc2a2f1d3c71a820b80bbdf72e56390c74617255386fa50af', 'CdcRead.sv': '279960f4dab8f63fa86be760f72a9f8bb50b1be905e234e57d6f69448b20cd1e', 'CdcRead_2.sv': 'd8b5c02ce85944d54bbd859b821f27651861f211a4b14652a7e94952afb0bb09', 'CdcSync.sv': 'dc64c320311667ee0be50c79c6b4097607f320335a1c90a845244ca451bef214', 'CdcSync_2.sv': '3eef53814698f441b53b1d2b18c31f10d1352f214ea512c9c2f3c011d2cb2900', 'CdcWrite.sv': 'bbd1342f5c804c43fd38fc889c6c04d9bf624fdf8a650433ee5228b6348f0fde', 'CdcWrite_2.sv': '94833737f736fa0a24e212f0b896b0f0e0731ac9c2b5056463e5cfcc4470ddfd', 'phy_rx.v': '7e5b81845160514dc9869bf86a05f36cc80ed0b97267e6f8ddc16c2a1f939c0c', 'phy_tx.v': '82c3ba96c5c8aca8ec6846b4bb75332102bfba4b5f154f6502f0752858eef775', 'RegBlock.sv': '1fa1e6b5f9bc817db391158fc7cfd12dd6a5932909e19a148a8429a0f649eee6', 'ResetRelease.sv': '3cf3bb9ebd8c7babc806c12d1702ab1f57084680b880d2146baefb50fc6116b0', 'sie.v': '4e2dd686707d7daf6e56862173aaf0d90772bafa5176073b66a7bb74bd101fe1', 'Usb.sv': '5b5315adf224e02d8c3f702d5bbbe70a06963dbfe0de9df4fc77738711529894', 'UsbBitEnable.sv': 'e7af93dcd7592b9535aa268a2fa3e53247ff972d8829df8527965b2925f8df8e', 'UsbControl.sv': '7771f666c00ba8df933648d5c8f508c52c9a28259e3e796044fa64caaade2a0d', 'UsbEngine.sv': 'e812af5f2e5c40cc6b6fc69bbdb23a01ca0c3796737362ebaf51faa6bc53a764', 'UsbInBuffer.sv': 'baf7ba900be211433774e1d97d9c7e7b14a269f3e08a63b37467bcce8c3eb231', 'UsbOutBuffer.sv': 'eed1de7559a9d55255831eaac027d78eef26a172db765d9944116a0e547f4e91', 'UsbPacketMemory.sv': 'b955d7420836a4b59d5cf2b49343c72187ed09e81bc524197027b327fa3f4981', 'UsbPadSafety.sv': '90d2c7471ebfa3380b5e69862a7f437138a5777ffd0d1bea3b864476ba91ebf7', 'UsbRegisters.sv': '90f8ae7c1a3c4bc618ba5a00f7ef3dede5b61ab659498e2ec14c04959bf7fb05', 'UsbResume.sv': 'd2b5a3ded5f4868c58538ee8b7f14320ed0fd3e5b421733a57327ebd10afc2f7'}}
COMBINATIONAL = set("add and bmux bwmux demux eq ge gt le logic_and logic_not logic_or lt mux ne not or pmux reduce_and reduce_or reduce_bool reduce_xor shl shr sshl sshr sub xor xnor pos neg concat slice".split())
FLAGS = ('control.inRequest', 'control.inReady', 'control.inAck', 'control.setup',
         'control.outReady', 'control.outValid', 'control.outError', 'in.request',
         'in.consume', 'in.acknowledge', 'out.receiveValid', 'out.receiveReady',
         'out.receiveError')


def run(before, after, output, regmap):
    root=Path(__file__).resolve().parents[4]
    before=before.resolve() if before else None
    after=after.resolve();output=output.resolve();regmap=regmap.resolve()
    for directory in (after,output,regmap,*([before] if before else [])):directory.relative_to(root/'build')
    output.mkdir(parents=True, exist_ok=False)
    # Compile this snapshot; caller-supplied candidate must match the fresh emission.
    paths=[p for p in root.glob('hw/**/*.scala') if 'build' not in p.parts]
    paths += [root/'build.sbt',root/'hw/ip/usb/usb.regmap.yaml',Path(__file__),regmap,root/'tools/sbt.py',root/'tools/env/lock.json']
    paths += [p for p in (root/'hw/vendor/usb').rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    source_hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    receipt = dict(status='running', baseline=BASELINE, blocks={}, production_source_sha256=source_hashes,
        method='Relational induction: all unchanged Q coupled as arbitrary common inputs; real cadence/flags retained; all other next-state, clock/reset functions and top outputs equal each cycle',
        initial_relation='Common initial unreset state; retained flags and cadence start at their production reset values. Root/transport resets and all other inputs subsequently arbitrary.',
        limitations='Digital transition equivalence, not metastability or analog timing')
    def save():
        (output/'result.json').write_text(json.dumps(receipt, indent=2)+'\n')
    def yosys(name, commands, negative=False):
        script=output/(name+'.ys');script.write_text('\n'.join(commands)+'\n')
        started=time.monotonic()
        try:
            with (output/(name+'.log')).open('w') as log_file:
                result=subprocess.run(['yosys','-Q','-T','-s',str(script)],stdout=log_file,stderr=subprocess.STDOUT,timeout=120)
        except subprocess.TimeoutExpired:
            receipt['timeout_job']=name
            raise
        log=(output/(name+'.log')).read_text()
        receipt.setdefault('elapsed_seconds',{})[name]=time.monotonic()-started
        ok=(result.returncode==1 and 'proof did fail' in log) if negative else result.returncode==0
        if not ok:raise ValueError('Equivalence job failed: '+name)
        return log
    def port(m,n,bits,direction='output'):
        m['ports'][n]=dict(direction=direction,bits=bits)
    def regs(m):
        r={}
        for n,c in m['cells'].items():
            if c['type'].startswith('$') and c['type'][1:] in COMBINATIONAL:continue
            if c['type'] not in ('$aldff','$adff','$dff'):raise ValueError('Unsupported state '+c['type'])
            aliases={a for a,v in m['netnames'].items() if v['bits']==c['connections']['Q']}
            if not aliases:raise ValueError('Unnamed state '+n)
            r[n]=(c,aliases)
        return r
    def newcell(m,name,typ,connections,parameters):
        m['cells'][name]=dict(hide_name=0,type=typ,parameters=parameters,attributes={},
            port_directions={p:('output' if p=='Y' else 'input') for p in connections},connections=connections)
    def bit(m):
        used=[b for c in m['cells'].values() for bits in c['connections'].values() for b in bits]
        used += [b for v in m['netnames'].values() for b in v['bits']]
        used += [b for v in m['ports'].values() for b in v['bits']]
        value=1+max(b for b in used if isinstance(b,int))
        # Reserve it even if a state cell is subsequently removed.
        m['netnames']['$proof_alloc_'+str(value)]=dict(hide_name=1,bits=[value],attributes={})
        return value
    try:
        with (output/'candidate-emit.log').open('w') as log:
            subprocess.run([sys.executable,'tools/sbt.py',f'runMain deadhorse.usb.EmitUsb {output}/candidate {regmap}'],stdout=log,stderr=subprocess.STDOUT,timeout=600,check=True)
        for role in ('engine','usb'):
            expected={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (after/role).iterdir() if p.suffix in ('.sv','.v')}
            actual={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (output/'candidate'/role).iterdir() if p.suffix in ('.sv','.v')}
            if expected!=actual:raise ValueError('Candidate differs from fresh production emission '+role)
        after=output/'candidate'

        if before is None:
            reference=output/'reference-src';reference.mkdir()
            reference_paths={n:'hw/ip/usb/src/main/scala/deadhorse/usb/'+n for n in ('UsbEngine.scala','UsbBitEnable.scala')}
            reference_paths['UsbFormal.scala']='hw/ip/usb/formal/UsbFormal.scala'
            reference_paths['UsbSieTiming.scala']='hw/ip/usb/formal/UsbSieTiming.scala'
            for name,path in reference_paths.items():
                (reference/name).write_bytes(subprocess.check_output(['git','show',BASELINE+':'+path]))
            setting=('set hw / Compile / unmanagedSources := (hw / Compile / unmanagedSources).value'
                     '.filterNot(s => Set('+', '.join('"'+n+'"' for n in reference_paths)+').contains(s.getName)) ++ Seq('
                     +', '.join('file("'+str(reference/n)+'")' for n in reference_paths)+')')
            before=output/'reference'
            with (output/'reference-emit.log').open('w') as log:
                subprocess.run([sys.executable,'tools/sbt.py',setting,f'runMain deadhorse.usb.EmitUsb {before} {regmap}'],stdout=log,stderr=subprocess.STDOUT,timeout=600,check=True)
        for role,top in [('engine','UsbEngine'),('usb','Usb')]:
            prefix='' if role=='engine' else 'engine.'
            modules={};registers={};hashes={}
            for label,directory in [('before',before),('after',after)]:
                files=sorted((directory/role).glob('*.sv'))+sorted((directory/role).glob('*.v'))
                hashes[label]={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
                if label=='before' and hashes[label]!=BASELINE_EMISSION[role]:raise ValueError('Unauthenticated baseline '+role)
                yosys(role+'-'+label,['read_slang --top '+top+' -DSYNTHESIS '+' '.join(map(str,files)),
                    'hierarchy -check -top '+top,'proc','flatten','memory_map','opt_clean',
                    f'write_json {output}/{role}-{label}.json'])
                modules[label]=json.loads((output/(role+'-'+label+'.json')).read_text())['modules'][top]
                registers[label]=regs(modules[label])
            pairs=[];remaining=set(registers['after']);found_flags=set()
            for name,(cell,aliases) in registers['before'].items():
                matches=[n for n in remaining if aliases & registers['after'][n][1]]
                if len(matches)!=1:raise ValueError('Missing/ambiguous state '+name+': '+str(matches))
                other=matches[0];remaining.remove(other);new,otheraliases=registers['after'][other]
                if cell['type']!=new['type'] or cell['parameters']!=new['parameters']:
                    raise ValueError('State shape changed '+name)
                common=aliases&otheraliases
                flag=common & {prefix+f for f in FLAGS}
                if len(flag)>1:raise ValueError('Merged flag identity')
                found_flags |= flag
                cadence=prefix+'cadence.count' in common or prefix+'cadence.enable' in common
                pairs.append(dict(before=name,after=other,aliases=sorted(common),flag=bool(flag),cadence=cadence))
            if found_flags!={prefix+f for f in FLAGS}:raise ValueError('Incomplete flag inventory')
            if len(remaining)!=1:raise ValueError('Unexpected unmatched state '+str(remaining))
            pre=remaining.pop();precell,prealiases=registers['after'][pre]
            if prefix+'cadence.preEnable' not in prealiases:raise ValueError('Wrong new state')
            for label,m in modules.items():
                enable=next(registers[label][p[label]][0] for p in pairs if prefix+'cadence.enable' in p['aliases'])
                retained=[registers[label][p[label]][0] for p in pairs if p['flag'] or p['cadence']]
                if label=='after':retained.append(precell)
                for c in retained:
                    if c['type']!='$aldff' or int(c['parameters']['CLK_POLARITY'],2)!=1 or int(c['parameters']['ALOAD_POLARITY'],2)!=1:
                        raise ValueError('Unsupported retained clock/reset kind')
                    if c['connections']['AD']!=['0']*len(c['connections']['Q']):raise ValueError('Nonzero retained reset')
                    if c['connections']['CLK']!=m['ports']['clk' if role=='engine' else 'usbClock']['bits']:
                        raise ValueError('Retained state is not on USB sample clock')
                    # Slang may duplicate the same one-bit inverter per instance.
                    drivers=[x for x in m['cells'].values() if x['connections'].get('Y')==c['connections']['ALOAD']]
                    if len(drivers)!=1 or drivers[0]['type']!='$not' or drivers[0]['connections']['A']!=m['netnames'][prefix+'cadence.reset_n']['bits'] or len(c['connections']['ALOAD'])!=1:
                        raise ValueError('Different retained reset cone')
                if label=='after' and len(precell['connections']['Q'])!=1:raise ValueError('Wrong preEnable width')
            block=dict(status='running',emission_sha256=hashes,state_bindings=pairs,new_state=pre,
                unchanged_bits=sum(len(registers['before'][p['before']][0]['connections']['Q']) for p in pairs if not p['flag']),
                excluded_flags=sorted(found_flags),jobs={})
            receipt['blocks'][role]=block;save()
            def extract(original,label):
                m=copy.deepcopy(original)
                for i,pair in enumerate(pairs):
                    c=m['cells'][pair[label]]
                    if pair['flag']:
                        # Explicitly prove sampling equality, in addition to every consumer.
                        y=bit(m);ce=m['netnames'][prefix+'cadence.enable']['bits']
                        newcell(m,'$sample_'+str(i),'$and',dict(A=c['connections']['Q'],B=ce,Y=[y]),
                            dict(A_WIDTH=1,B_WIDTH=1,Y_WIDTH=1,A_SIGNED=0,B_SIGNED=0))
                        port(m,'sample_'+str(i),[y])
                    elif pair['cadence']:
                        port(m,'state_'+str(i),c['connections']['Q'])
                    else:
                        m['cells'].pop(pair[label]);port(m,'state_'+str(i),c['connections']['Q'],'input')
                    for pin,bits in c['connections'].items():
                        if pin=='Q' or (pair['flag'] and pin=='D'):continue
                        port(m,'next_'+str(i)+'_'+pin,bits)
                return m
            for variant in ('correct','early','late','off_enable_consumer'):
                sides=copy.deepcopy(modules)
                if variant in ('early','late'):
                    m=sides['after'];c=m['cells'][pre];y=bit(m)
                    n=1 if variant=='early' else 3
                    newcell(m,'fault_predecode','$eq',dict(A=m['netnames'][prefix+'cadence.count']['bits'],
                        B=[str(n&1),str((n>>1)&1)],Y=[y]),dict(A_WIDTH=2,B_WIDTH=2,Y_WIDTH=1,A_SIGNED=0,B_SIGNED=0))
                    c['connections']['D']=[y]
                if variant=='off_enable_consumer':
                    # Same newly faulty consumer in both designs; old/new flags now
                    # alter non-exempt state off CE. This must invalidate refinement.
                    for label,m in sides.items():
                        matches=[p for p in pairs if prefix+'attached_REG' in p['aliases']]
                        if len(matches)!=1:raise ValueError('Missing consumer fault identity')
                        m['cells'][matches[0][label]]['connections']['D']=m['netnames'][prefix+'in.consume']['bits']
                for label,m in sides.items():
                    (output/f'{role}-{variant}-{label}.json').write_text(json.dumps({'modules':{label:extract(m,label)}}))
                commands=[f'read_json {output}/{role}-{variant}-before.json',f'read_json {output}/{role}-{variant}-after.json',
                    'miter -equiv -flatten before after Equivalence','hierarchy -check -top Equivalence',
                    'check -assert','async2sync','techmap','opt -full','stat',
                    f'sat -set-def-inputs -set-init-zero -seq 8 '+(' -tempinduct -maxsteps 16 ' if variant=='correct' else '')+
                    f'-prove trigger 0 -verify -dump_json {output}/{role}-{variant}-trace.json']
                log=yosys(role+'-'+variant,commands,negative=variant!='correct')
                if variant=='correct' and 'SUCCESS!' not in log:raise ValueError('Missing induction success')
                block['jobs'][variant]='proved' if variant=='correct' else 'fault_rejected';save()
            block['status']='pass';save()
        with (output/'real-consumer.log').open('w') as log:
            result=subprocess.run([sys.executable,'tools/sbt.py','testOnly deadhorse.usb.UsbPreEnableSpec'],stdout=log,stderr=subprocess.STDOUT,timeout=1800)
        if result.returncode or 'OFF_ENABLE_CONSUMER rejected on real EP1 traffic' not in (output/'real-consumer.log').read_text():
            raise ValueError('Real off-enable consumer control failed')
        receipt['real_consumer_control']='fault_rejected'
        if source_hashes!={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}:raise ValueError('Production sources changed during proof')
        for role in ('engine','usb'):
            for label,directory in [('before',before),('after',after)]:
                actual={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (directory/role).iterdir() if p.suffix in ('.sv','.v')}
                if actual!=receipt['blocks'][role]['emission_sha256'][label]:raise ValueError('HDL changed during proof')
        receipt['negative_scope']='Phase and consumer faults rejected in relational model; real wire consumer control passed; exact production-cadence phase faults are separately required by the timing certificate'
        receipt['status']='pass';save();print('PASS D58 engine/wrapper relational equivalence and phase/consumer faults',flush=True)
    except Exception as e:
        receipt['status']='unresolved' if isinstance(e,subprocess.TimeoutExpired) else 'failed';receipt['error']=str(e)
        for block in receipt['blocks'].values():
            if block['status']=='running':block['status']=receipt['status']
        save();raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--before',type=Path)
    for name in ('after','output','regmap'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();run(a.before,a.after,a.output,a.regmap)
