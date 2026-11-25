"""PLAN05 RVFI-only cone removal, followed by exact retained-state equivalence."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'dv/core'))
import equiv
from common import run as core_run
from state_equiv import STATE

def capped(*args,**kwargs):
    kwargs['timeout']=120
    return core_run(*args,**kwargs)
equiv.run=capped

def main(output):
    out=(ROOT/output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    paths=[p for root in ('hw/ip/perf_core/src/main','hw/ip/lite_core/src/main','hw/lib/src/main',
                         'hw/top/reference/formal','dv/core') for p in (ROOT/root).rglob('*')
           if p.is_file() and p.suffix in ('.scala','.py','.json')]
    paths += [ROOT/p for p in ('build.sbt','tools/sbt.py','tools/env/lock.json')]
    hashes=lambda:{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    receipt=dict(status='running',sources=hashes(),commands=[],cases={},assumptions=[],
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        scope='Remove only RVFI output ports and their dead logic; compare every retained state, clock/reset function and other output. No live state excluded.')
    def command(argv,label):
        start=time.monotonic()
        with (out/(label+'.log')).open('w') as log:
            try:code=subprocess.run(list(map(str,argv)),cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=120).returncode
            except subprocess.TimeoutExpired:code=124
        receipt['commands'].append(dict(command=list(map(str,argv)),returncode=code,seconds=time.monotonic()-start))
        if code:raise RuntimeError(label+(' timed out; deferred without retry' if code==124 else ' failed'))
    def yosys(lines,label):
        script=out/(label+'.ys');script.write_text('\n'.join(lines)+'\n')
        command(['yosys','-Q','-T','-s',script],label)
    try:
        # Select this emitter only: other top formal fixtures are separately built.
        command([sys.executable,'tools/sbt.py',
            'set hw / Compile / unmanagedSources += file("/work/hw/top/reference/formal/EmitRvfiVariants.scala")',
            f'hw/runMain deadhorse.top.EmitRvfiVariants {out}/emit'],'emit')
        for case,top in (('lite','LiteHart'),('performance','ibex_top')):
            directory=out/case;directory.mkdir();entry=dict(models={});receipt['cases'][case]=entry
            for side in ('verification','production'):
                sources=sorted((out/'emit'/case/side).glob('*.sv'))
                if case=='performance':sources.append(ROOT/'hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv')
                raw=directory/(side+'-raw.json')
                yosys(['read_slang --top '+top+' '+' '.join(map(str,sources)),
                       f'prep -top {top} -flatten',f'write_json {raw}'],case+'-'+side+'-raw')
                design=json.loads(raw.read_text());module=design['modules'][top]
                observations=[n for n in module['ports'] if n.startswith('rvfi_')]
                if (side=='verification') != bool(observations):raise ValueError('Unexpected RVFI interface: '+case+' '+side)
                for name in observations:
                    if module['ports'][name]['direction']!='output':raise ValueError('RVFI input cannot be excluded')
                    del module['ports'][name]
                trimmed=directory/(side+'-ports.json');trimmed.write_text(json.dumps(design))
                model=directory/(side+'.json')
                yosys([f'read_json {trimmed}','opt_clean -purge','memory_map','opt_clean -purge',
                       'check -assert',f'write_json {model}','stat'],case+'-'+side+'-cone')
                # Removing an output can change the surviving net alias (e.g.
                # rvfi_ext_fcsr -> fp_fcsr_o). Preserve the exact frontend
                # driver-cell identity as an additional Q alias on BOTH sides.
                # This only supplies the induction correspondence: every D,
                # clock/reset function, type, initial value and output must
                # still prove equal, and every live state must be paired.
                canonical=json.loads(model.read_text());m=canonical['modules'][top]
                aliases={}
                for name,cell in m['cells'].items():
                    if cell['type'] in STATE:
                        alias='plan05_state_'+hashlib.sha256(name.encode()).hexdigest()
                        if alias in m['netnames']:raise ValueError('Ambiguous state alias')
                        m['netnames'][alias]=dict(hide_name=0,bits=cell['connections']['Q'],attributes={})
                        aliases[alias]=name
                model.write_text(json.dumps(canonical))
                metadata=dict(netlist_sha256=hashlib.sha256(model.read_bytes()).hexdigest(),
                    driver_state_aliases=aliases,
                    excluded_output_ports=observations,source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
                model.with_suffix('.elaboration.json').write_text(json.dumps(metadata))
                entry['models'][side]=metadata
            positive=directory/'positive';positive.mkdir()
            status=equiv.compare(top,directory/'verification.json',directory/'production.json',positive)
            entry['positive']=json.loads((positive/'result.json').read_text())
            if status!='proved':raise RuntimeError(case+' equivalence '+status)
            negative=directory/'negative';negative.mkdir()
            entry['negative']=equiv.negatives(top,directory/'verification.json',directory/'production.json',negative)
        if hashes()!=receipt['sources']:raise ValueError('Proof sources changed')
        receipt['status']='pass'
    except Exception as error:receipt.update(status='unresolved' if any(s in str(error).lower() for s in ('timed out','timeout')) else 'failed',error=str(error))
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper(),receipt.get('error',''),flush=True)
    return 0 if receipt['status']=='pass' else 1

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();sys.exit(main(a.output))
