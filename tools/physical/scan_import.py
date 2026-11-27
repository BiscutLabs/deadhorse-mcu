"""Fresh unplaced OpenDB import using the qualified T38 physical views.

OpenROAD Python entrypoint; T37_IMPORT_CONFIG names an explicit build config.
This does not run placement, CTS, routing or DRC.
"""
import hashlib
import json
import os
from pathlib import Path
import time

ROOT=Path(__file__).resolve().parents[2]


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    import openroad
    start=time.monotonic()
    path=Path(os.environ['T37_IMPORT_CONFIG']).resolve();path.relative_to(ROOT/'build')
    cfg=json.loads(path.read_text())
    if sha(cfg['openroad'])!='a58debef32b592a7f2622a42a65434c313f2d332b84dc15af4798b33db24e0b4':
        raise ValueError('Wrong OpenROAD')
    out=(ROOT/cfg['output']).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    chip=ROOT/cfg['chip'];v=chip/'chip_top.v';receipt=json.loads((chip/'result.json').read_text())
    if receipt['status']!='pass' or sha(v)!=receipt['artifact_sha256']['chip_top.v']:
        raise ValueError('Unqualified chip assembly')
    physical=ROOT/cfg['physical_config'];r=json.loads(physical.read_text())
    tech=openroad.Tech()
    lefs=[r['TECH_LEFS']['nom_*'],*r['CELL_LEFS'],*r['PAD_LEFS']]
    libs=[str(ROOT/'build/t43/pdk-candidate/gf180mcuD/libs.ref/gf180mcu_fd_sc_mcu7t5v0/lib/gf180mcu_fd_sc_mcu7t5v0__tt_025C_3v30.lib'),
        str(ROOT/'build/t43/pdk-candidate/gf180mcuD/libs.ref/gf180mcu_fd_io/lib/gf180mcu_fd_io__tt_025C_3v30.lib')]
    for macro in r['MACROS'].values():
        lefs+=macro['lef']
        for key,values in macro.get('lib',{}).items():
            if key=='*' or 'tt_025C_3v30' in key:libs+=values
    for p in dict.fromkeys(lefs):tech.readLef(p)
    for p in dict.fromkeys(libs):tech.readLiberty(p)
    d=openroad.Design(tech);commands=[]
    def tcl(command):
        commands.append(command)
        if d.evalTclString('catch {'+command+'} _import_result')!='0':
            raise ValueError(d.evalTclString('set _import_result'))
    d.readVerilog(str(v));tcl('link_design chip_top')
    tcl('add_global_connection -net VDD -inst_pattern .* -pin_pattern {^(VDD|VNW|vdd)$} -power')
    tcl('add_global_connection -net VSS -inst_pattern .* -pin_pattern {^(VSS|VPW|vss)$} -ground')
    tcl('global_connect');d.writeDb(str(out/'imported.odb'))
    result=dict(status='imported_unplaced',seconds=time.monotonic()-start,
        instances=len(d.getBlock().getInsts()),commands=commands,
        script_sha256={str(Path(__file__).relative_to(ROOT)):sha(__file__)},
        inputs={str(p):sha(p) for p in [path,physical,v,chip/'result.json',*lefs,*libs]},
        output_sha256=sha(out/'imported.odb'))
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS fresh unplaced import:',result['instances'],'instances')


if __name__=='__main__':main()
