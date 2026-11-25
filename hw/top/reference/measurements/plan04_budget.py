"""PLAN04 planning budget from measured digital cells and unchanged allowances."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from tools.timing.usb_boundary import groups

def main(base):
    base=(ROOT/base).resolve();base.relative_to(ROOT/'build')
    mapped=base/'map/canonical.json';mapping=json.loads((base/'map/result.json').read_text())
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    assert mapping['status']=='mapped' and digest(mapped)==mapping['mapped_sha256']
    cfg=json.loads((ROOT/'phys/gf180-ws-1x1/block-timing.json').read_text())
    lib=ROOT/cfg['liberty']
    assert digest(lib)==cfg['sha256']
    areas={n:float(re.search(r'\barea\s*:\s*([\d.]+)',b)[1]) for n,b in groups(lib.read_text(),'cell')}
    cells=json.loads(mapped.read_text())['modules']['DeadhorseSoc']['cells']
    assert all(c['type'] in areas for c in cells.values())
    measured=sum(areas[c['type']] for c in cells.values())/1e6
    uplift=0;negative=0;flops=0
    for c in cells.values():
        if '__dff' not in c['type']:continue
        replacement=c['type'].replace('__dff','__sdff');extra=0
        if replacement not in areas:
            assert c['type']=='gf180mcu_fd_sc_mcu7t5v0__dffnrnq_1'
            replacement='gf180mcu_fd_sc_mcu7t5v0__sdffrnq_1'
            extra=areas['gf180mcu_fd_sc_mcu7t5v0__inv_1'];negative+=1
        uplift+=areas[replacement]+extra-areas[c['type']];flops+=1
    uplift/=1e6
    blocks=json.loads((base/'new-digital-area/result.json').read_text())
    assert blocks['status']=='measured_area_only'
    for name,value in blocks['input_sha256'].items():assert digest(ROOT/name)==value
    spent=(blocks['digital_area_um2_measured']+blocks['scan_uplift_um2_estimated'])/1e6
    assert spent<=.10,'PLAN04 digital additions exceed clock/reset allowance'
    digital={'remaining_clock_reset_power_mm2_estimated':.10-spent,
        'rom_mm2_assumed':.50,'bist_mm2_assumed':.05,'scan_glue_mm2_assumed':.05,
        'scan_cell_substitution_mm2_estimated':uplift}
    lef=ROOT/'build/riscay-mcu/.tools/gf180-sram/gf180mcu_ocd_ip_sram__sram1024x8m8wm1.lef'
    assert digest(lef)=='35bcf13111ab5029860ca7a2ef473fbf21b4938d6c6244b53b4480bd35f2776a'
    width,height=map(float,re.search(r'\bSIZE\s+([\d.]+)\s+BY\s+([\d.]+)',lef.read_text()).groups())
    sram=20*width*height/1e6
    physical={'lf_rc_mm2_assumed':.10,'por_brownout_mm2_assumed':.15,
        'pad_keepout_mm2_assumed':.50,'sram_halo_glue_mm2_assumed':.40}
    placed=(measured+sum(digital.values()))/.55
    total=placed+sram+sum(physical.values())
    result=dict(status='estimated_with_allowances',mapped_logic_mm2_measured=measured,
        flops_measured=flops,negative_edge_scan_estimates=negative,
        scan_basis='Same-drive characterized scan cells; two negative-edge flops estimated as positive-edge scan plus inverter, unqualified until T37',
        clock_allowance_spent_mm2_estimated=spent,digital_allowances=digital,utilization_assumed=.55,
        placed_digital_mm2_estimated=placed,sram_mm2_estimated=sram,
        sram_basis='Pinned1024x8 macro footprint:16 performance macros plus4 retained macros, latter exposes3KiB of4KiB capacity',
        physical_allowances=physical,total_mm2_estimated=total,ceiling_mm2=12.92,headroom_mm2_estimated=12.92-total,
        boundary='Built controller logic and its scan substitution appear only in whole-top measured/estimated rows. Isolated block cost reduces original0.10 controller allowance; remainder is an estimate for unfinishedT33, not an exact integrated partition.',
        inputs={str(p.relative_to(ROOT)):digest(p) for p in (mapped,lib,lef,base/'new-digital-area/result.json',Path(__file__))})
    (base/'area-budget.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
    assert total<=12.92,'PLAN04 area stop condition'

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--base',required=True)
    main(parser.parse_args().base)
