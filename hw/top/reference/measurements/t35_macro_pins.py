"""Worst paths over complete T35 SRAM pin sets on production constraints."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[4]

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main(base,output):
    base=(ROOT/base).resolve();base.relative_to(ROOT/'build')
    out=(ROOT/output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    mapped=base/'map/canonical.json';mapping=json.loads((base/'map/result.json').read_text())
    assert mapping['status']=='mapped' and digest(mapped)==mapping['mapped_sha256']
    lock=ROOT/'hw/vendor/gf180_sram/gf180_sram.lock.json';macro=json.loads(lock.read_text())['macro']
    cells=json.loads(mapped.read_text())['modules']['DeadhorseSoc']['cells']
    names=[n for n,c in cells.items() if c['type']==macro];assert len(names)==20
    def pinlist(direction):
        return ' '.join(n+'/'+p+(f'[{i}]' if len(bits)>1 else '') for n in names
            for p,bits in cells[n]['connections'].items() if p!='CLK' and cells[n]['port_directions'][p]==direction
            for i in range(len(bits)))
    tool=Path(shutil.which('sta'));inputs={p.relative_to(ROOT).as_posix():digest(p) for p in (mapped,base/'map/result.json',lock,Path(__file__))}
    def seal(path):
        key=path.relative_to(ROOT).as_posix();value=digest(path)
        assert key not in inputs or inputs[key]==value,(key,'changed during measurement')
        inputs[key]=value
    def constraints(path):
        return '\n'.join(l.strip() for l in path.read_text().splitlines() if l.strip() and not l.lstrip().startswith('#'))
    receipt=dict(status='running',sources=inputs,tool_sha256=digest(tool),runs=[],
        scope='Worst paths over all 560 SRAM data/control input pins and 160 Q pins; five paired corners, both AON straps. Queried sets are complete; per-pin path coverage is explicitly reported. Same ideal pre-CTS clocks, loads and exceptions as production screens. Pulse/clock/reset and physical signoff remain separate.')
    try:
        for corner in ('ss125','ssn40','tt25','ff125','ffn40'):
            parent_path=base/corner/'result.json';parent=json.loads(parent_path.read_text())
            seal(parent_path)
            assert parent['status']=='measured_screen' and parent['mapped_sha256']==digest(mapped)
            for path,value in parent['input_sha256'].items():
                assert digest(ROOT/path)==value,(path,'stale screen');seal(ROOT/path)
            for mode in ('rc','external'):
                src=base/corner/mode;dest=out/corner/mode;dest.mkdir(parents=True)
                source=src/'timing.tcl'
                assert digest(source)==parent['constraint_sha256'][mode+'/timing.tcl']
                seal(source);seal(src/'applied.sdc')
                assert digest(src/'applied.sdc')==parent['constraint_sha256'][mode+'/applied.sdc']
                # Preserve the exact authenticated setup/constraint prefix. Do
                # not rerun or overwrite the original screen's large reports.
                text=source.read_text();marker='\nset threshold_metrics '
                assert text.count(marker)==1
                code=text.split(marker)[0]+'\n'
                code+='set inputs [get_pins {'+pinlist('input')+'}]\nset outputs [get_pins {'+pinlist('output')+'}]\n'
                code+='if {[llength $inputs] != 560 || [llength $outputs] != 160} {error "Missing SRAM pin"}\n'
                code+=f'write_sdc {dest}/applied.sdc\nset f [open {dest}/paths.tsv w]\nputs $f "direction\\tpolarity\\tstart\\tend\\tarrival_ns\\tslack_ns"\n'
                code+='''foreach dir {into outof} {
 foreach pol {max_rise max_fall min_rise min_fall} {
  if {$dir eq "into"} {set paths [find_timing_paths -to $inputs -path_delay $pol -group_path_count 1120 -endpoint_path_count 1]} else {set paths [find_timing_paths -from $outputs -path_delay $pol -group_path_count 1120 -endpoint_path_count 1]}
  if {[llength $paths] == 0} {error "No SRAM timing path"}
  foreach p $paths {puts $f "$dir\\t$pol\\t[get_full_name [get_property $p startpoint]]\\t[get_full_name [get_property $p endpoint]]\\t[get_property [lindex [get_property $p points] end] arrival]\\t[get_property $p slack]"}
 }
}
close $f
puts T35_MACRO_PATHS_COMPLETE
'''
                script=dest/'timing.tcl';script.write_text(code);command=['sta','-no_init','-exit',str(script)]
                seal(script)
                r=subprocess.run(command,cwd=ROOT,capture_output=True,text=True);(dest/'sta.log').write_text(r.stdout)
                assert r.returncode==0 and 'T35_MACRO_PATHS_COMPLETE' in r.stdout and not any(l.startswith('Error') for l in r.stdout.splitlines()),r.stdout[-2000:]
                assert constraints(dest/'applied.sdc')==constraints(src/'applied.sdc'),'Constraint prefix changed'
                rows=list(csv.DictReader((dest/'paths.tsv').open(),delimiter='\t'));summary={}
                assert rows and all(math.isfinite(float(r[k])) for r in rows for k in ('arrival_ns','slack_ns'))
                for direction in ('into','outof'):
                    for typ in ('max','min'):
                        matching=[r for r in rows if r['direction']==direction and r['polarity'].startswith(typ)]
                        summary[direction+'_'+typ]=min(matching,key=lambda r:float(r['slack_ns']))
                row=dict(corner=corner,mode=mode,command=command,worst_slack=summary,
                    constraints_sha256=hashlib.sha256(constraints(dest/'applied.sdc').encode()).hexdigest(),
                    queried_input_pins=560,queried_output_pins=160,
                    unreported_inputs=sorted(set(pinlist('input').split())-{r['end'] for r in rows if r['direction']=='into'}),
                    unreported_outputs=sorted(set(pinlist('output').split())-{r['start'] for r in rows if r['direction']=='outof'}),
                    source_sha256={p.relative_to(ROOT).as_posix():digest(p) for p in (source,parent_path,script)})
                receipt['runs'].append(row);print(corner,mode,{k:v['slack_ns'] for k,v in summary.items()},flush=True)
        assert inputs=={p:digest(ROOT/p) for p in inputs} and digest(tool)==receipt['tool_sha256']
        receipt['status']='measured_macro_interfaces'
    except Exception as error:receipt.update(status='failed',error=str(error));raise
    finally:
        receipt['artifact_sha256']={p.relative_to(out).as_posix():digest(p) for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
        (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();main(a.base,a.output)
