"""Mapped reset-held mux against pinned GF180 functional models, port-only oracle."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import shutil
import sys
import time

ROOT=Path(__file__).resolve().parents[4]


def main(output):
    out=(ROOT/output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    sources=list((ROOT/'hw/ip/osc_ctrl/src/main/scala').rglob('*.scala'))
    sources+=list((ROOT/'hw/lib/src/main/scala').rglob('*.scala'))
    sources += [Path(__file__),Path(__file__).with_name('EmitResetCell.scala'),
        Path(__file__).with_name('reset_cell_vpi.cpp'),ROOT/'tools/env/lock.json',ROOT/'build.sbt',
        ROOT/'tools/sbt.py',ROOT/'phys/gf180-ws-1x1/block-timing.json']
    snapshot=lambda:{p.relative_to(ROOT).as_posix():sha(p) for p in sources}
    receipt=dict(status='running',source_sha256=snapshot(),commands=[],
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        scope='Mapped functional cell simulation; no extracted delay, metastability or analog claim',
        assumptions=['Static POR_BYPASS per powered run (D84)',
            'AON selection stable during reset and sampling; later perturbation checks frozen selection',
            'Independent finite clock schedules; no liveness claim for a stopped selected source'])
    def run(command,label,cwd=ROOT):
        start=time.monotonic()
        result=subprocess.run(list(map(str,command)),cwd=cwd,text=True,capture_output=True)
        (out/(label+'.log')).write_text(result.stdout+result.stderr)
        receipt['commands'].append(dict(command=list(map(str,command)),cwd=str(cwd),
            returncode=result.returncode,seconds=time.monotonic()-start))
        if result.returncode:raise RuntimeError(label+' failed')
        return result.stdout+result.stderr
    try:
        receipt['tools_sha256']={name:sha(Path(shutil.which(name)))
            for name in ('yosys','iverilog','iverilog-vpi','vvp')}
        cfg=json.loads((ROOT/'phys/gf180-ws-1x1/block-timing.json').read_text())
        pdk=ROOT/'build/riscay-mcu/.tools/physical/pdk'
        lib=pdk/(cfg['library']+'__'+cfg['corner']+'.lib')
        models=[pdk/'gf180mcu_fd_sc_mcu7t5v0.v',pdk/'primitives.v']
        expected=[cfg['sha256'],'9a21c5f98200acfe77d8ba52067164e0802284dc1c1e117f0e64fb6ac42eb64b',
            'ccc0f447f71ce35c635e08d49eb0ed77aa2ec91cf31d8e3e45a246114d3cae92']
        for path,digest in zip([lib,*models],expected):
            if sha(path)!=digest:raise ValueError('Pinned library/model mismatch: '+str(path))
        receipt['libraries_sha256']={p.name:sha(p) for p in [lib,*models]}
        run([sys.executable,'tools/sbt.py',
            'set hw / Compile / unmanagedSourceDirectories += file("/work/hw/ip/osc_ctrl/formal")',
            f'hw/runMain deadhorse.osc_ctrl.EmitResetCell {out}/emit'],'emit')
        run(['iverilog-vpi',Path(__file__).with_name('reset_cell_vpi.cpp')],'vpi-build',out)
        receipt['cases']=[]
        for variant in ('correct','fault'):
            files=sorted((out/'emit'/variant).glob('*.sv'))
            if not files:raise ValueError('No emitted sources')
            ys=out/(variant+'.ys');net=out/(variant+'.v')
            ys.write_text('\n'.join([f'read_liberty -lib {lib}',
                'read_slang --top ResetBootstrap '+' '.join(map(str,files)),
                'synth -top ResetBootstrap -flatten -noabc',f'dfflibmap -liberty {lib}',
                f'abc -liberty {lib}','clean','check -assert',f'write_verilog -noattr {net}',
                f'write_json {out}/{variant}.json','']))
            run(['yosys','-Q','-T','-s',ys],variant+'-map')
            design=json.loads((out/(variant+'.json')).read_text())['modules']['ResetBootstrap']
            if not design['cells'] or any(not c['type'].startswith(cfg['library']+'__') for c in design['cells'].values()):
                raise ValueError('Unmapped/unknown cell remains')
            run(['iverilog','-g2012','-DFUNCTIONAL','-s','ResetBootstrap','-o',out/(variant+'.vvp'),net,*models],variant+'-compile')
            for external in (False,True):
                for bypass in (False,True):
                    label=f'{variant}-{int(external)}-{int(bypass)}'
                    command=['vvp','-M'+str(out),'-mreset_cell_vpi',out/(variant+'.vvp')]
                    if external:command.append('+external')
                    if bypass:command.append('+bypass')
                    log=run(command,label)
                    if variant=='correct':
                        expected=f'PASS RESET_CELL_CONTRACT source={int(external)} bypass={int(bypass)} samples=700'
                        if expected not in log or 'FAIL' in log:raise ValueError(label+' failed oracle')
                    elif 'FAIL RESET_CELL_CONTRACT step=220 reason=clock selection' not in log:
                        raise ValueError(label+' must reject actual unfrozen selector at the directed perturbation')
                    receipt['cases'].append(dict(name=label,status='pass' if variant=='correct' else 'fault_rejected'))
        if snapshot()!=receipt['source_sha256']:raise ValueError('Sources changed during check')
        receipt['status']='pass'
    except Exception as error:receipt.update(status='failed',error=str(error))
    receipt['artifact_sha256']={p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file() and p.name!='result.json'}
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(receipt['status'].upper(),receipt.get('error','RESET_CELL_CONTRACT'))
    return int(receipt['status']!='pass')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    sys.exit(main(parser.parse_args().output))
