"""FPU protocol/cancel/progress with unconstrained arithmetic and real faults."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[4]

def bind_production(prepared,directory):
    """Strip only monitors and prove exact named-state equivalence to production."""
    sys.path.insert(0,str(ROOT/'dv/core'))
    from equiv import compare, negatives
    design=json.loads(prepared.read_text())
    module=design['modules'].pop('FpuFormal')
    module['cells']={n:c for n,c in module['cells'].items()
                     if c['type'] not in ('$assert','$assume','$cover','$check')}
    design['modules']['Fpu']=module
    projected=directory/'projected.json';projected.write_text(json.dumps(design))
    paths=[]
    for role,read in [('projected',f'read_json {projected}'),
        ('production','read_slang --top Fpu '+' '.join(map(str,sorted((ROOT/'build/t12/emit').glob('*.sv')))))]:
        path=directory/(role+'-canonical.json');script=directory/(role+'.ys')
        script.write_text(read+'\nprep -top Fpu -flatten\nopt -full -nodffe -nosdff\ncheck -assert\n'+f'write_json {path}\n')
        with (directory/(role+'.log')).open('w') as log:
            subprocess.run(['yosys','-Q','-T','-s',str(script)],cwd=ROOT,
                           stdout=log,stderr=subprocess.STDOUT,check=True,timeout=30)
        paths.append(path)
    out=directory/'binding';out.mkdir(exist_ok=True)
    if compare('Fpu',*paths,out)!='proved': raise ValueError('Formal instrumentation changed production')
    faults=negatives('Fpu',*paths,out)
    (out/'negative-controls.json').write_text(json.dumps(faults,indent=2)+'\n')

def prepare(sources,directory):
    path=directory/'prepared.json'
    script=directory/'prepare.ys'
    script.write_text('read_slang --top FpuFormal '+' '.join(map(str,sources))+'\n'
        'prep -top FpuFormal -flatten\n'+f'write_json {path}\n')
    with (directory/'prepare.log').open('w') as log:
        subprocess.run(['yosys','-Q','-T','-s',str(script)],cwd=ROOT,stdout=log,
                       stderr=subprocess.STDOUT,check=True,timeout=30)
    design=json.loads(path.read_text())
    module=design['modules']['FpuFormal']
    fresh=1+max(b for n in module['netnames'].values() for b in n['bits'] if isinstance(b,int))
    module['cells']['initial_cycle']=dict(type='$initstate',parameters={},attributes={},
        port_directions={'Y':'output'},connections={'Y':[fresh]})
    module['cells']['initial_reset']=dict(type='$assume',parameters={},attributes={},
        port_directions={'A':'input','EN':'input'},
        connections={'A':module['ports']['reset']['bits'],'EN':[fresh]})
    path.write_text(json.dumps(design))
    kinds=[cell['type'] for cell in module['cells'].values()]
    if not any(k in ('$assert','$check','$cover') for k in kinds):
        raise ValueError('No formal properties in emitted production harness')
    # Cut combinational arithmetic only. Never replace a state-holding output:
    # several HardFloat result ports alias stored metadata or constant bits.
    sequential={b for cell in module['cells'].values()
                if any(x in cell['type'].lower() for x in ('dff','latch'))
                for port,bits in cell['connections'].items()
                if cell['port_directions'][port]=='output' for b in bits if isinstance(b,int)}
    names=['pre.io_mulAddA','pre.io_mulAddB','pre.io_mulAddC',
           'after.io_invalidExc','rounding.io_out','rounding.io_exceptionFlags',
           'toInt.io_out','toInt.io_intExceptionFlags','compare.io_eq',
           'compare.io_lt','compare.io_exceptionFlags','div.trialComputed']
    names += ['after.io_rawOut_'+f for f in ('isNaN','isInf','isZero','sign','sExp','sig')]
    names += [n for n in module['netnames'] if n.startswith('pre.io_toPostMul_')]
    cuts=[]; retained=[]
    for name in names:
        bits=module['netnames'][name]['bits']
        if any(b in sequential for b in bits if isinstance(b,int)) or not any(isinstance(b,int) for b in bits):
            retained.append(name)
        else: cuts.append(name)
    if not cuts or 'div.trialComputed' not in cuts: raise ValueError('Arithmetic abstraction missing')
    manifest=dict(cutpoints=cuts,retained_aliases=retained,
                  sources={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    (directory/'abstraction.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return path, '\n'.join('cutpoint w:'+name for name in cuts)

def check():
    out=ROOT/'build/t12/formal';out.mkdir(parents=True,exist_ok=True)
    with (out/'emit.log').open('w') as log:
        subprocess.run([sys.executable,'tools/sbt.py',
            f'set hw / Compile / unmanagedSources += file("{ROOT}/hw/ip/fpu/formal/FpuFormal.scala")',
            f'hw/runMain deadhorse.fpu.EmitFpuFormal {out}/emit'],cwd=ROOT,
            stdout=log,stderr=subprocess.STDOUT,check=True,timeout=180)
    results={}
    for role in ['normal','cover_operations','cover_protocol','cover_division','cancel_fault','hold_fault','progress_fault']:
        mode='cover' if role.startswith('cover') else 'prove' if role=='normal' else 'bmc'
        depth=64 if role=='cover_division' else 44 if role in ('normal','cover_operations','progress_fault') else 14 if role=='cover_protocol' else 8
        sources=sorted((out/'emit'/role).glob('*.sv'))
        directory=out/role;directory.mkdir(exist_ok=True)
        prepared,cuts=prepare(sources,directory)
        if role=='normal': bind_production(prepared,directory)
        config=directory/'check.sby'
        skip='skip 63\n' if role=='cover_division' else 'skip 43\n' if role in ('cover_operations','progress_fault') else ''
        stimulus=''
        if mode=='cover':
            stimulus='fminit -seq reset 1,0 -set io_req_bits_rm 0 -set io_req_bits_c 0 '
            if role=='cover_division':
                stimulus+='-seq io_req_valid 0,1,0 -set io_cancel 0 -set io_rsp_ready 0 -set io_req_bits_a 1065353216 -set io_req_bits_b 1073741824\n'
            elif role=='cover_operations':
                stimulus+='-seq io_req_valid 0,1,0 -set io_cancel 0 -set io_rsp_ready 0 -set io_req_bits_a 0 -set io_req_bits_b 0\n'
            else:
                stimulus+='-set io_req_bits_op 7 -set io_req_bits_a 0 -set io_req_bits_b 0\n'
        if role=='progress_fault':
            # Concrete counterexample search only; the normal PDR proof has no
            # restrictions on requests, operands, cancellation or backpressure.
            stimulus='fminit -seq reset 1,0 -seq io_req_valid 0,1,0 -set io_cancel 0 -set io_rsp_ready 0 -set io_req_bits_op 3 -set io_req_bits_rm 0 -set io_req_bits_a 1065353216 -set io_req_bits_b 1073741824 -set io_req_bits_c 0\n'
        config.write_text(f'[options]\nmode {mode}\ndepth {depth}\n{skip}timeout 120\n\n'
            '[engines]\n'+('abc pdr' if mode=='prove' else 'smtbmc z3')+'\n\n[script]\n'
            f'read_json {prepared}\n{cuts}\nopt_clean\n{stimulus}async2sync\ndffunmap\n')
        start=time.monotonic()
        with (directory/'run.log').open('w') as log:
            process=subprocess.run(['sby','-f','-d',str(directory/'proof'),str(config)],
                cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=135)
        status=(directory/'proof/status').read_text().strip().split()[0]
        expected='FAIL' if role.endswith('fault') else 'PASS'
        if status!=expected or (status=='PASS' and process.returncode):
            raise RuntimeError(f'FPU formal {role}: expected {expected}, got {status}')
        if role!='normal' and not list((directory/'proof/engine_0').glob('trace*.vcd')):
            raise RuntimeError('Missing fault/cover witness: '+role)
        results[role]=dict(status=status,kind='covered' if mode=='cover' else
                          'fault rejected' if role.endswith('fault') else 'proved; arithmetic abstracted',
                          depth=depth,seconds=time.monotonic()-start)
        if stimulus: results[role]['witness_stimulus']=stimulus.strip()
        print('PASS formal',role,results[role],flush=True)
    (out/'result.json').write_text(json.dumps(dict(status='pass',assumptions=['reset asserted in initial formal cycle; subsequent reset unconstrained'],
        arithmetic='unconstrained combinational cutpoints; original control and register enables',results=results),indent=2)+'\n')

if __name__=='__main__': check()
