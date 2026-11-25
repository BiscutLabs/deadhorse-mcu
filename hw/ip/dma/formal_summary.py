"""Read-only step-0 evidence from scoped T40 jobs; never reruns a solver."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',required=True);a=p.parse_args()
    base=(ROOT/a.base).resolve();base.relative_to(ROOT/'build')
    receipt=json.loads((base/'result.json').read_text());rows=[]
    for job in receipt['jobs']:
        folder=base/job['name'];model=folder/'model/design.il'
        if not model.exists():
            rows.append(dict(job=job['name'],result=job.get('result',job['solver_status']),model='not prepared'))
            continue
        dest=folder/'step0.json'
        with (folder/'step0.log').open('w') as log:
            subprocess.run(['yosys','-Q','-T','-p',f'read_rtlil {model}; stat; write_json {dest}'],
                cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
        modules=json.loads(dest.read_text())['modules'];cells=[c for m in modules.values() for c in m['cells'].values()]
        log=(folder/'logfile.txt').read_text()
        bounds=[int(v) for v in re.findall(r'bad state property \d+(?: reachable)? at bound k = (\d+)',log)]
        covers=re.findall(r'bad state property (\d+) reachable at bound k = (\d+) SATISFIABLE',log) if job['mode']=='cover' else []
        rows.append(dict(job=job['name'],result=job['result'],depth=job['depth'],seconds_measured=job['seconds'],
            cells_measured=len(cells),sequential_bits_measured=sum(len(c['connections']['Q']) for c in cells if 'dff' in c['type'] or c['type']=='$ff'),
            memories_measured=sum(c['type'].startswith('$mem') for c in cells),
            last_attempted_bmc_bound_measured=max(bounds) if bounds else None,cover_steps_measured=covers,
            prepared_model_sha256=hashlib.sha256(model.read_bytes()).hexdigest()))
    result=dict(jobs=rows,receipt_sha256=hashlib.sha256((base/'result.json').read_bytes()).hexdigest(),
        notes='Finite jobs: full-width four-channel engine. Ring jobs: actual MMIO wrapper plus checker. Neither has packet RAM. Range/count arithmetic and other channels share cones. No proof assumption added. Last attempted bound is not a fully discharged depth.')
    (base/'step0-summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(rows))
if __name__=='__main__':main()
