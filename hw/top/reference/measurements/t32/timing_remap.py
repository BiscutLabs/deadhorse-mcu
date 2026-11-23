"""Third T32 timing trial: tighter ABC optimization goal, unchanged STA limits."""
import csv
import json
from pathlib import Path
import re
import subprocess
import time
from timing_iterations import ROOT, TOP, sha, write
from tools.timing.check import electrical_checks
from tools.timing.usb_boundary import groups


def main():
    base=ROOT/'build/t32/final-fast03/fast/faithful-floating-timing'
    out=ROOT/'build/t32/timing-iterations/loop3'
    out.mkdir(parents=True,exist_ok=False)
    lib=ROOT/'build/riscay-mcu/.tools/physical/pdk/gf180mcu_fd_sc_mcu7t5v0__ss_125C_3v00.lib'
    receipt=dict(status='running',commands=[],producer_sha256=sha(__file__),
        helper_sha256=sha(Path(__file__).with_name('timing_iterations.py')),
        liberty_sha256=sha(lib),revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        original_mapping_target_ps=62500,trial_mapping_target_ps=50000,
        budget_ns=.60*1000/9,qualification='Diagnostic only; no production-flow or physical acceptance. Mapping goal is not STA acceptance.')
    def run(command,label):
        start=time.monotonic()
        with (out/(label+'.log')).open('w') as f:
            code=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT).returncode
        receipt['commands'].append(dict(command=command,returncode=code,seconds=time.monotonic()-start))
        assert code==0,label
    try:
        receipt['inputs']={str(p):sha(p) for p in (base/'premapped.json',base/'mapping.abc',base/'mapping.constr',base/'timing.tcl')}
        original_script=(base/'mapping.abc').read_text()
        assert original_script.count('62500')==3
        (out/'mapping.abc').write_text(original_script.replace('62500','50000'))
        (out/'mapping.constr').write_bytes((base/'mapping.constr').read_bytes())
        (out/'synth.ys').write_text(f'read_json "{base}/premapped.json"\nhierarchy -check -top {TOP}\ncheck -assert\nabc -liberty "{lib}" -constr "{out}/mapping.constr" -script "{out}/mapping.abc"\nclean -purge\ncheck -assert\nstat -liberty "{lib}"\nwrite_json "{out}/candidate.json"\nwrite_verilog -noattr -noexpr "{out}/mapped.v"\n')
        run(['yosys','-Q','-T','-s',str(out/'synth.ys')],'synthesis')
        (out/'timing.tcl').write_text((base/'timing.tcl').read_text().replace(str(base),str(out)))
        run(['sta','-no_init','-exit',str(out/'timing.tcl')],'sta')
        log=(out/'sta.log').read_text()
        assert 'TIMING_COMPLETE' in log and not re.search(r'^Error:',log,re.M)
        rows=list(csv.DictReader((out/'paths.tsv').open(),delimiter='\t'))
        classes={k:max((r for r in rows if r['class']==k),key=lambda r:float(r['delay_ns'])) for k in {r['class'] for r in rows}}
        worst=max(rows,key=lambda r:float(r['delay_ns']))
        gates=list(csv.DictReader((out/'gate_checks.tsv').open(),delimiter='\t'));assert gates
        gate=min(float(g['slack_ns']) for g in gates)
        electrical=electrical_checks(log)
        library=dict(groups(lib.read_text(),'cell'))
        areas={n:float(re.search(r'\barea\s*:\s*([0-9.]+)',body)[1]) for n,body in library.items() if re.search(r'\barea\s*:',body)}
        original=json.loads((base/'mapped.json').read_text())['modules'][TOP]
        candidate=json.loads((out/'candidate.json').read_text())['modules'][TOP]
        assert set(candidate['ports'])==set(original['ports'])
        assert all((p['direction'],len(p['bits']))==(original['ports'][n]['direction'],len(original['ports'][n]['bits'])) for n,p in candidate['ports'].items())
        area=sum(areas[c['type']] for c in candidate['cells'].values())
        old_area=sum(areas[c['type']] for c in original['cells'].values())
        ok=float(worst['delay_ns'])<=receipt['budget_ns'] and electrical['max_capacitance_and_slew_violations']==0 and gate>=0
        receipt.update(status='timing-pass-unqualified' if ok else 'fail',worst=worst,classes=classes,
                       electrical=electrical,gate_min_slack_ns=gate,
                       mapped_area_um2=area,area_delta_um2=area-old_area,
                       equivalence_status='not yet run; required before retention')
    except Exception as error:
        receipt.update(status='error',error=repr(error));raise
    finally:
        receipt['artifacts']={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='result.json'}
        write(out/'result.json',receipt)
        print(json.dumps({k:receipt.get(k) for k in ('status','mapped_area_um2','area_delta_um2','error')}),flush=True)


if __name__=='__main__':main()
