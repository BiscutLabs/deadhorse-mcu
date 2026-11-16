"""Focused F integration bounds, real production binding, covers and a fault."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'dv/core'))
from common import local,output_dir,run
from equiv import compare,negatives

TOP='FloatIntegrationFormal'


def prepare(emitted,out,production,bind,contract=None):
    sources=sorted(emitted.glob('*.sv')); script=out/'prepare.ys'
    script.write_text(f'read_slang --top {TOP} '+' '.join(map(str,sources))+
                      f'\nprep -top {TOP} -flatten\nwrite_json {out}/prepared.json\n')
    run(['yosys','-Q','-T','-s',script],out,'prepare')
    design=json.loads((out/'prepared.json').read_text()); module=design['modules'][TOP]
    kinds={}
    for cell in module['cells'].values():
        if cell['type']=='$check':
            kind=cell['parameters']['FLAVOR']; kinds[kind]=kinds.get(kind,0)+1
    if set(kinds) not in ({'assert'},{'cover'}): raise ValueError(f'Unexpected properties: {kinds}')
    if bind:
        projected=copy.deepcopy(design); m=projected['modules'].pop(TOP)
        projected['modules']['ibex_core']=m; m['ports'].pop('checking')
        m['cells']={n:c for n,c in m['cells'].items() if c['type'] not in ('$check','$assert','$assume','$cover')}
        (out/'projected.json').write_text(json.dumps(projected)); netlists=[]
        for role,read in [('projected',f'read_json {out}/projected.json'),
            ('production','read_slang --top ibex_core '+' '.join(map(str,sorted(production.glob('*.sv')))))]:
            path=out/(role+'-canonical.json'); netlists.append(path); ys=out/(role+'.ys')
            ys.write_text(read+'\nprep -top ibex_core -flatten\nopt -full -nodffe -nosdff\ncheck -assert\n'+f'write_json {path}\n')
            run(['yosys','-Q','-T','-s',ys],out,role)
        binding=output_dir(out/'binding')
        if compare('ibex_core',*netlists,binding)!='proved': raise ValueError('Production binding failed')
        negatives('ibex_core',*netlists,binding)
    if contract:
        contracted=[contract/'Fpu.sv' if p.name=='Fpu.sv' else p for p in sources]
        ys=out/'contract.ys'
        ys.write_text(f'read_slang --top {TOP} '+' '.join(map(str,contracted))+
            f'\nprep -top {TOP} -flatten\nwrite_json {out}/contract.json\n')
        run(['yosys','-Q','-T','-s',ys],out,'contract')
        design=json.loads((out/'contract.json').read_text()); module=design['modules'][TOP]
    bits=module['ports'].pop('checking')['bits']; module['netnames']['checking']['attributes']['init']='0'
    module['cells']['__history']=dict(type='$dff',attributes={},parameters=dict(WIDTH='1',CLK_POLARITY='1'),
        port_directions=dict(CLK='input',D='input',Q='output'),
        connections=dict(CLK=module['ports']['clk_i']['bits'],D=['1'],Q=bits))
    if contract:
        (out/'abstraction.json').write_text(json.dumps(dict(
            kind='T12 proved port protocol; arbitrary completion latency/result/flags',
            model_sha256=hashlib.sha256((contract/'Fpu.sv').read_bytes()).hexdigest(),
            environmental_assumptions_added=[]),indent=2)+'\n')
        return design,kinds,[]
    # Exactly the T12 combinational arithmetic cutpoints, in the integrated
    # hierarchy. Registers, valid, ready, destination and cancellation stay real.
    prefix='floatExecution.fpu.'
    names=['pre.io_mulAddA','pre.io_mulAddB','pre.io_mulAddC','after.io_invalidExc',
           'rounding.io_out','rounding.io_exceptionFlags','toInt.io_out','toInt.io_intExceptionFlags',
           'compare.io_eq','compare.io_lt','compare.io_exceptionFlags','div.trialComputed']
    names += ['after.io_rawOut_'+field for field in ('isNaN','isInf','isZero','sign','sExp','sig')]
    names=[prefix+n for n in names]+[n for n in module['netnames'] if n.startswith(prefix+'pre.io_toPostMul_')]
    sequential={b for c in module['cells'].values() if any(k in c['type'].lower() for k in ('dff','latch'))
                for p,bits in c['connections'].items() if c['port_directions'][p]=='output' for b in bits if isinstance(b,int)}
    cuts=[]; retained=[]
    for name in names:
        bits=module['netnames'][name]['bits']
        if any(b in sequential for b in bits) or not any(isinstance(b,int) for b in bits): retained.append(name)
        else: cuts.append(name)
    if prefix+'div.trialComputed' not in cuts: raise ValueError('Missing arithmetic cutpoint')
    (out/'abstraction.json').write_text(json.dumps(dict(cutpoints=cuts,retained_aliases=retained),indent=2)+'\n')
    return design,kinds,cuts


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--emitted',required=True); parser.add_argument('--output',required=True)
    parser.add_argument('--fpu-contract',action='store_true')
    parser.add_argument('--prove',action='store_true',help='Unbounded PDR instead of normal BMC; same assertions and timeout')
    args=parser.parse_args(); out=output_dir(args.output); production=local(args.emitted)
    receipt=dict(status='running',results={},assumptions=['reset asserted initially; later reset unrestricted'],
                 arithmetic='T12 combinational cutpoints unconstrained; original FPU control and enables retained')
    path=out/'result.json'; path.write_text(json.dumps(receipt)+'\n')
    try:
        contract=None
        if args.fpu_contract:
            proof=ROOT/'build/t12/formal/result.json'
            sys.path.insert(0,str(ROOT/'hw/ip/fpu/formal'))
            from receipt import authenticate
            receipt['t12_authentication']=authenticate(ROOT,proof.parent)
            contract=output_dir(out/'fpu-contract')
            run([sys.executable,'tools/sbt.py',
                 f'set hw / Compile / unmanagedSources += file("{ROOT}/hw/ip/perf_core/formal/FpuProtocolModel.scala")',
                 f'hw/runMain deadhorse.perf_core.EmitFpuProtocolModel {contract}'],out,'emit-contract',timeout=180)
            # Authenticate the integrated FPU against the exact T12 production
            # module. Only the unused busy observation port is projected away.
            netlists=[]
            for role,directory in [('t12',ROOT/'build/t12/emit'),('integrated',production)]:
                ys=contract/(role+'.ys'); path0=contract/(role+'.json')
                ys.write_text('read_slang --top Fpu '+' '.join(map(str,sorted(directory.glob('*.sv'))))+
                    f'\nprep -top Fpu -flatten\nwrite_json {path0}\n')
                run(['yosys','-Q','-T','-s',ys],contract,role)
                raw=json.loads(path0.read_text()); raw['modules']['Fpu']['ports'].pop('io_busy',None)
                path0.write_text(json.dumps(raw)); final=contract/(role+'-canonical.json'); netlists.append(final)
                ys.write_text(f'read_json {path0}\nopt -full -nodffe -nosdff\ncheck -assert\nwrite_json {final}\n')
                run(['yosys','-Q','-T','-s',ys],contract,role+'-canonical')
            binding=output_dir(contract/'binding')
            if compare('Fpu',*netlists,binding)!='proved': raise ValueError('Integrated FPU differs from T12')
            receipt['arithmetic']='T12 proved FPU port contract; arbitrary latency and arithmetic; no deadline claim'
            receipt['t12_proof_sha256']=hashlib.sha256(proof.read_bytes()).hexdigest()
        for role in ('normal','fault','cover'):
            directory=output_dir(out/role); emitted=directory/'emit'
            run([sys.executable,'tools/sbt.py',
                 f'set hw / Compile / unmanagedSources += file("{ROOT}/hw/ip/perf_core/formal/FloatIntegrationFormal.scala")',
                 f'hw/runMain deadhorse.perf_core.EmitFloatIntegrationFormal {emitted} {role}'],directory,'emit',timeout=180)
            design,properties,cuts=prepare(emitted,directory,production,role=='normal',contract)
            module=design['modules'][TOP]
            if role=='fault':
                # Force a real FP commit on squash. The original response,
                # scoreboard and architectural monitor remain unchanged.
                name='floatExecution.io_commitArithmetic'
                old=module['netnames'][name]['bits']; cancel=module['netnames']['floatExecution.io_cancel']['bits']
                fresh=1+max(b for n in module['netnames'].values() for b in n['bits'] if isinstance(b,int))
                for c in module['cells'].values():
                    for p,direction in c['port_directions'].items():
                        if direction=='input': c['connections'][p]=[fresh if b==old[0] else b for b in c['connections'][p]]
                module['netnames'][name]['bits']=[fresh]
                module['cells']['__fault_commit']=dict(type='$or',attributes={},
                    parameters=dict(A_SIGNED='0',B_SIGNED='0',A_WIDTH='1',B_WIDTH='1',Y_WIDTH='1'),
                    port_directions=dict(A='input',B='input',Y='output'),connections=dict(A=old,B=cancel,Y=[fresh]))
            prepared=directory/'checked.json'; prepared.write_text(json.dumps(design))
            mode='cover' if role=='cover' else 'prove' if role=='normal' and args.prove else 'bmc'
            depth=160 if role!='fault' else 48
            config=directory/'check.sby'
            config.write_text(f'[options]\nmode {mode}\ndepth {depth}\ntimeout 120\n[engines]\n'+
                ('abc pdr' if mode=='prove' else 'btor btormc')+'\n[script]\n'+
                f'read_json {prepared}\n'+'\n'.join('cutpoint w:'+n for n in cuts)+
                f'\nopt_clean\nfminit -seq rst_ni 0,\'z\nasync2sync\nchformal -lower\ndffunmap\n')
            result=run(['sby','-f','-d',directory/'work',config],directory,'check',allowed=(0,2,8,16),timeout=135)
            status=(directory/'work/status').read_text().split()[0]; expected='FAIL' if role=='fault' else 'PASS'
            if status!=expected or result.returncode!=(2 if role=='fault' else 0):
                raise RuntimeError(f'{role}: expected {expected}, got {status}/{result.returncode}')
            if role!='normal' and not list((directory/'work/engine_0').glob('trace*.vcd')):
                raise ValueError('Missing cover/counterexample witness')
            receipt['results'][role]=dict(status='pass',kind=('proved' if mode=='prove' else 'bounded') if role=='normal' else
                'fault rejected' if role=='fault' else 'covered',depth=depth,properties=properties)
            receipt['production_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                                          for p in sorted(production.glob('*.sv'))}
            path.write_text(json.dumps(receipt,indent=2)+'\n')
            extent='unbounded safety proof' if mode=='prove' else f'depth {depth}'
            print(f'PASS F integration {role}: {status}, {extent}',flush=True)
        receipt['status']='pass'
    except Exception as exc:
        receipt.update(status='failed',error=str(exc)); raise
    finally: path.write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__': main()
