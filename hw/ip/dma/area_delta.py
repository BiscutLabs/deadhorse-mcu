"""Authenticate isolated DMA maps and apply their delta to the T35 chip budget."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT))
from tools.timing.usb_boundary import groups

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['before','after','budget','output']:p.add_argument('--'+name,required=True)
    a=p.parse_args();digest=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
    cfg=json.loads((ROOT/'phys/gf180-ws-1x1/block-timing.json').read_text())
    lib=ROOT/cfg['liberty']
    assert digest(lib)==cfg['sha256']
    areas={n:float(re.search(r'\barea\s*:\s*([\d.]+)',b)[1]) for n,b in groups(lib.read_text(),'cell')}
    rows=[];conditions=None
    for arg in [a.before,a.after]:
        directory=(ROOT/arg).resolve();directory.relative_to(ROOT/'build')
        result=json.loads((directory/'result.json').read_text());assert result['status']=='pass'
        for name,h in result['artifact_sha256'].items():
            # The timing runner stores artifact paths relative to its output.
            f=directory/name
            if not f.exists():f=ROOT/name
            assert digest(f)==h,str(f)
        m=result['measurement'];mapped=directory/'timing/mapped.json'
        keys=['top','operating_point','budget_ns','class_budgets_ns','class_failure_limits_ns',
              'mapping','assumptions','tools','flow_sha256']
        observed={k:m[k] for k in keys}
        if conditions is None:conditions=observed
        else:assert conditions==observed,'Before/after measurement conditions differ'
        assert m['top']=='Dma' and m['operating_point']=='main-9mhz'
        assert digest(mapped)==m['mapped_sha256']
        cells=json.loads(mapped.read_text())['modules']['Dma']['cells']
        assert abs(sum(areas[c['type']] for c in cells.values())-m['area_um2'])<1e-5
        counts={};scan=0
        for c in cells.values():
            t=c['type'];counts[t]=counts.get(t,0)+1
            if '__dff' in t:
                replacement=t.replace('__dff','__sdff');assert replacement in areas
                scan+=areas[replacement]-areas[t]
        rows.append(dict(area_um2_measured=m['area_um2'],flops_measured=sum(n for t,n in counts.items() if '__dff' in t),
            scan_uplift_um2_estimated=scan,classes=m['classes'],cell_counts=counts,
            receipt_sha256=digest(directory/'result.json'),receipt=str(directory.relative_to(ROOT)/'result.json')))
    delta=(rows[1]['area_um2_measured']-rows[0]['area_um2_measured'])/1e6
    scan_delta=(rows[1]['scan_uplift_um2_estimated']-rows[0]['scan_uplift_um2_estimated'])/1e6
    budget_path=(ROOT/a.budget).resolve();budget_path.relative_to(ROOT/'build')
    budget=json.loads(budget_path.read_text());assert budget['status']=='estimated_with_allowances'
    for f,h in budget['inputs'].items():assert digest(ROOT/f)==h,f
    total=budget['total_mm2_estimated']+(delta+scan_delta)/budget['utilization_assumed']
    result=dict(status='pass' if delta<=.010 and total<=12.92 else 'stop',rows=rows,
        dma_delta_mm2_measured=delta,scan_delta_mm2_estimated=scan_delta,cap_mm2=.010,
        baseline_total_mm2_estimated=budget['total_mm2_estimated'],total_mm2_estimated=total,
        headroom_mm2_estimated=12.92-total,utilization_assumed=budget['utilization_assumed'],
        basis='T35 baseline budget plus isolated mapped DMA delta and same-drive scan substitution delta / utilization; no whole-SoC remap or placement claimed.',
        conditions=conditions,
        inputs={a.budget:digest(budget_path),str(lib.relative_to(ROOT)):digest(lib),
            'phys/gf180-ws-1x1/block-timing.json':digest(ROOT/'phys/gf180-ws-1x1/block-timing.json'),
            'tools/timing/usb_boundary.py':digest(ROOT/'tools/timing/usb_boundary.py'),
            str(Path(__file__).relative_to(ROOT)):digest(Path(__file__))})
    out=(ROOT/a.output).resolve();out.relative_to(ROOT/'build');out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k not in ['rows','inputs','conditions']}))
    return 0 if result['status']=='pass' else 1
if __name__=='__main__':sys.exit(main())
