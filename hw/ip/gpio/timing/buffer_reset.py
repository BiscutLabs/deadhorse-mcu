"""Verified reset-only GF180 fanout repair for the tied-clock GPIO screen."""
import copy
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from tools.timing.fanout import buffer_module,verify
from tools.timing.check import electrical_checks

def main():
    base=ROOT/'build/t21/timing-first/gpio/timing'
    out=ROOT/'build/t21/timing-gpio-buffered';out.mkdir(parents=True,exist_ok=False)
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    design=json.loads((base/'mapped.json').read_text());old=design['modules']['GpioTiming']
    root=old['netnames']['d.w._ar_released']['bits'];assert len(root)==1 and isinstance(root[0],int)
    new,inserted=buffer_module(old,'clk',source_bits=set(root),prefix='gpio_reset_');assert inserted
    verify(old,new,inserted)
    fault=copy.deepcopy(new);fault['cells'][inserted[0]]['connections']['I']=fault['cells'][inserted[0]]['connections']['Z'][:]
    try:verify(old,fault,inserted)
    except ValueError as error:assert 'cycle' in str(error)
    else:raise ValueError('Reset buffer cycle escaped')
    design['modules']['GpioTiming']=new;(out/'buffered.json').write_text(json.dumps(design))
    cfg=json.loads((ROOT/'phys/gf180-ws-1x1/block-timing.json').read_text())
    lib=ROOT/cfg['liberty']
    assert digest(lib)==cfg['sha256']
    ys=out/'export.ys';ys.write_text(f'read_json {out}/buffered.json\ncheck -assert\nstat -liberty {lib}\nwrite_json {out}/mapped.json\nwrite_verilog -noattr -noexpr {out}/mapped.v\n')
    with (out/'export.log').open('w') as log:subprocess.run(['yosys','-Q','-T','-s',str(ys)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
    tcl=(base/'timing.tcl').read_text().replace(str(base),str(out))
    tcl+='\n'+ '\n'.join([
        f'set safety [open {{{out}/short_reset.tsv}} w]',
        'puts $safety "check\\tstart\\tend\\tslack_ns"',
        'set resets [concat [get_pins -quiet */RN] [get_pins -quiet */SETN]]',
        'if {![llength $resets]} {error "Missing reset pins"}',
        'foreach {kind targets modes} [list hold [all_registers -data_pins] {min_rise min_fall} reset $resets {min_rise min_fall max_rise max_fall}] {',
        ' foreach mode $modes {',
        '  foreach path [find_timing_paths -to $targets -path_delay $mode -group_path_count [expr {2*[llength $targets]}] -endpoint_path_count 1] {',
        '   puts $safety "$kind/$mode\\t[get_full_name [get_property $path startpoint]]\\t[get_full_name [get_property $path endpoint]]\\t[get_property $path slack]"',
        '  }',' }','}','close $safety','puts T21_BUFFER_COMPLETE',''])
    script=out/'timing.tcl';script.write_text(tcl)
    p=subprocess.run(['sta','-no_init','-exit',str(script)],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (out/'sta.log').write_text(p.stdout)
    assert p.returncode==0 and 'T21_BUFFER_COMPLETE' in p.stdout and not re.search(r'(?m)^Error',p.stdout)
    def rows(name):
        with (out/name).open() as f:return list(csv.DictReader(f,delimiter='\t'))
    paths=rows('paths.tsv');safety=rows('short_reset.tsv');assert paths and safety
    for r in paths:r['delay_ns']=float(r['delay_ns'])
    for r in safety:r['slack_ns']=float(r['slack_ns'])
    classes={k:max((r for r in paths if r['class']==k),key=lambda r:r['delay_ns']) for k in {r['class'] for r in paths}}
    assert {'RR','IR','RO'}<=set(classes)
    electrical=electrical_checks(p.stdout);budget=.6*1000/9
    passed=max(r['delay_ns'] for r in paths)<=budget and electrical['max_capacitance_and_slew_violations']==0
    area=float(re.findall(r'Chip area for (?:top )?module[^\n]*:\s*([\d.]+)',(out/'export.log').read_text())[-1])
    receipt=dict(status='setup_electrical_pass' if passed else 'fail',classes=classes,budget_ns=budget,
        area_um2=area,electrical=electrical,buffers=len(inserted),root='d.w._ar_released',
        verification='Every original pin and clock preserved through non-inverting buffers; cycle fault rejected',
        physical_status='unqualified; ideal-clock pre-CTS hold/reset negatives remain physical-flow items',
        short_reset_worst={k:min((r for r in safety if r['check']==k),key=lambda r:r['slack_ns']) for k in {r['check'] for r in safety}},
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        source_sha256={p.relative_to(ROOT).as_posix():digest(p) for p in [Path(__file__),ROOT/'tools/timing/fanout.py',
            ROOT/'tools/timing/check.py',ROOT/'tools/timing/analyze.tcl',base/'mapped.json',base/'timing.tcl',lib]},
        artifact_sha256={p.relative_to(out).as_posix():digest(p) for p in out.rglob('*') if p.is_file()})
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');print(receipt['status'],electrical)
    return 0 if passed else 1

if __name__=='__main__':sys.exit(main())
