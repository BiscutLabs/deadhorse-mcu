"""Bounded registered-core protocol checks, production binding and live covers."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'dv/core'))
from common import local, output_dir, run
from equiv import compare, negatives
TOP='CoreIntegrationFormal'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--emitted',required=True); parser.add_argument('--output',required=True)
    parser.add_argument('--variant',choices=['all','normal','fault','redirect-fault','cover'],default='all')
    args=parser.parse_args(); out=output_dir(args.output); candidate=local(args.emitted)
    receipt=dict(status='running',assumptions=['startup reset low; subsequent reset unrestricted'],
                 variant=args.variant,scope='integration control; arithmetic checked separately')
    try:
        if args.variant=='all':
            receipt['variants']={}
            for variant in ('normal','fault','redirect-fault','cover'):
                run([sys.executable,__file__,'--emitted',candidate,'--output',out/variant,'--variant',variant],
                    out,variant,timeout=1000)
                receipt['variants'][variant]=json.loads((out/variant/'result.json').read_text())
            receipt['status']='pass'
            print('PASS integration: bounded protocol, production binding, fault and covers; not unbounded proof')
            return
        run([sys.executable,'tools/env/check.py'],out,'environment')
        emitted=out/'emit'
        run([sys.executable,'tools/sbt.py',
             f'set hw / Compile / unmanagedSources += file("{ROOT}/hw/ip/perf_core/formal/CoreIntegrationFormal.scala")',
             f'hw/runMain deadhorse.perf_core.EmitCoreIntegrationFormal {emitted.relative_to(ROOT)} {args.variant}'],
            out,'emit',timeout=600)
        sources=sorted(emitted.glob('*.sv'))
        receipt['source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
        script=out/'prepare.ys'
        script.write_text(f'read_slang --top {TOP} '+' '.join(map(str,sources))+
                          f'\nprep -top {TOP} -flatten\nwrite_json {out}/prepared.json\n')
        run(['yosys','-Q','-T','-s',script],out,'prepare')
        design=json.loads((out/'prepared.json').read_text()); m=design['modules'][TOP]
        inventory={}
        for c in m['cells'].values():
            if c['type'] not in ('$check','$assert','$cover','$assume'): continue
            flavor=c['parameters']['FLAVOR'] if c['type']=='$check' else c['type'][1:]
            inventory[flavor]=inventory.get(flavor,0)+1
        receipt['properties']=inventory
        if inventory!=({'cover':14} if args.variant=='cover' else {'assert':21}):
            raise ValueError(f'Unexpected properties/assumptions: {inventory}')
        if args.variant in ('normal','fault','redirect-fault','cover'):
            projected=json.loads(json.dumps(design)); module=projected['modules'].pop(TOP)
            projected['modules']['ibex_core']=module
            module['ports'].pop('checking')
            module['cells']={n:c for n,c in module['cells'].items() if c['type'] not in ('$check','$assert','$cover','$assume')}
            (out/'projected.json').write_text(json.dumps(projected))
            production=[p for p in sorted(candidate.glob('*.sv')) if p.name not in ('ibex_top.sv','ClockGate.sv')]
            receipt['production_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in production}
            netlists=[]
            for name,read in [('projected',f'read_json {out}/projected.json'),
                ('production','read_slang --top ibex_core '+' '.join(map(str,production)))]:
                path=out/(name+'-canonical.json'); netlists.append(path)
                ys=out/(name+'.ys')
                ys.write_text(read+'\nprep -top ibex_core -flatten\nopt -full -nodffe -nosdff\ncheck -assert\n'+f'write_json {path}\n')
                run(['yosys','-Q','-T','-s',ys],out,name)
            binding=output_dir(out/'binding')
            if compare('ibex_core',*netlists,binding)!='proved': raise RuntimeError('Instrumentation/production binding failed')
            if args.variant=='normal': negatives('ibex_core',*netlists,binding)
        bits=m['ports'].pop('checking')['bits']; m['netnames']['checking']['attributes']['init']='0'
        m['cells']['__history']=dict(type='$dff',attributes={},parameters=dict(WIDTH='1',CLK_POLARITY='1'),
            port_directions=dict(CLK='input',D='input',Q='output'),
            connections=dict(CLK=m['ports']['clk_i']['bits'],D=['1'],Q=bits))
        if args.variant=='fault':
            # Real output-strobe mutation: the DUT publishes a register write
            # while its execution transaction is pending without a result.
            old=m['ports']['rf_we_wb_o']['bits']
            fresh=max(b for n in m['netnames'].values() for b in n['bits'] if isinstance(b,int))+1
            pending=m['netnames']['pending']['bits']; valid=m['netnames']['responseValid']['bits']
            if len(old)!=1 or len(pending)!=1 or len(valid)!=1: raise ValueError('Fault requires scalar signals')
            for c in m['cells'].values():
                for port,direction in c['port_directions'].items():
                    if direction=='input': c['connections'][port]=[fresh+2 if b==old[0] else b for b in c['connections'][port]]
            m['ports']['rf_we_wb_o']['bits']=[fresh+2]
            m['netnames']['rf_we_wb_o']['bits']=[fresh+2]
            for name,kind,a,b,y in [('not','$not',valid,None,fresh),('early','$and',pending,[fresh],fresh+1),
                                   ('write','$or',old,[fresh+1],fresh+2)]:
                parameters=dict(A_SIGNED='0',A_WIDTH='1',Y_WIDTH='1')
                directions=dict(A='input',Y='output'); connections=dict(A=a,Y=[y])
                if b is not None:
                    parameters.update(B_SIGNED='0',B_WIDTH='1'); directions['B']='input'; connections['B']=b
                m['cells']['__fault_'+name]=dict(type=kind,parameters=parameters,attributes={},
                    port_directions=directions,connections=connections)
        if args.variant=='redirect-fault':
            # Corrupt a real target-address bit after capture, including the
            # prefetch consumer. The expected-address monitor is unchanged.
            address=m['netnames']['redirectAddress']['bits']
            if len(address)!=32: raise ValueError('Redirect fault requires full address observation')
            old=address[2]
            if not isinstance(old,int): raise ValueError('Redirect target bit must be live')
            fresh=max(b for n in m['netnames'].values() for b in n['bits'] if isinstance(b,int))+1
            for c in m['cells'].values():
                for port,direction in c['port_directions'].items():
                    if direction=='input': c['connections'][port]=[fresh if b==old else b for b in c['connections'][port]]
            m['cells']['__redirect_fault']=dict(type='$not',attributes={},
                parameters=dict(A_SIGNED='0',A_WIDTH='1',Y_WIDTH='1'),
                port_directions=dict(A='input',Y='output'),connections=dict(A=[old],Y=[fresh]))
        prepared=out/'checked.json'; prepared.write_text(json.dumps(design))
        mode='cover' if args.variant=='cover' else 'bmc'
        is_fault=args.variant in ('fault','redirect-fault')
        depth=40 if is_fault else 160
        engine='btor btormc' if mode=='cover' else 'abc bmc3'
        config=out/'check.sby'
        config.write_text(f'[options]\nmode {mode}\ndepth {depth}\ntimeout 600\n[engines]\n{engine}\n[script]\n'+
            f'read_json {prepared}\nprep -top {TOP}\nfminit -seq rst_ni 0,\'z\nasync2sync\nchformal -lower\ndffunmap\n')
        result=run(['sby','-f','-d',out/'work',config],out,'check',allowed=(0,2,8,16),timeout=630)
        status=(out/'work/status').read_text().split()[0]
        expected='FAIL' if is_fault else 'PASS'
        if status!=expected or result.returncode!=(2 if expected=='FAIL' else 0):
            raise RuntimeError(f'Expected {expected}, got {status}/{result.returncode}')
        if args.variant!='normal' and not list((out/'work/engine_0').glob('trace*.vcd')):
            raise RuntimeError('Missing counterexample/cover witness')
        receipt.update(status='pass',result='fault rejected' if is_fault else 'covered' if mode=='cover' else 'bounded',depth=depth)
        print(f'PASS integration {args.variant}: {receipt["result"]}, depth {depth}')
    except Exception as exc:
        receipt.update(status='failed',error=str(exc)); raise
    finally:
        (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__': main()
