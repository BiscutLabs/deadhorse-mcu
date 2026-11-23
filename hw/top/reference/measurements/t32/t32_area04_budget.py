"""Planning estimate from measured cells and pinned macro geometry; not physical fit."""
import hashlib,json,re,sys
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root))
from tools.timing.usb_boundary import groups
base=root/'build/t32/area04/mapped'
mapped=max(json.loads((base/f'map-{m}/area-partition.json').read_text())['area_um2']/1e6 for m in (8,))
lef=root/'build/riscay-mcu/.tools/gf180-sram/gf180mcu_ocd_ip_sram__sram1024x8m8wm1.lef'
assert hashlib.sha256(lef.read_bytes()).hexdigest()=='35bcf13111ab5029860ca7a2ef473fbf21b4938d6c6244b53b4480bd35f2776a'
width,height=map(float,re.search(r'\bSIZE\s+([\d.]+)\s+BY\s+([\d.]+)',lef.read_text()).groups())
macro=width*height/1e6
lib=root/'build/riscay-mcu/.tools/physical/pdk/gf180mcu_fd_sc_mcu7t5v0__ss_125C_3v00.lib'
areas={n:float(re.search(r'\barea\s*:\s*([\d.]+)',b)[1]) for n,b in groups(lib.read_text(),'cell')}
scan=[]
for mhz in (8,):
    cells=json.loads((base/f'map-{mhz}/canonical.json').read_text())['modules']['DeadhorseSoc']['cells']
    uplift=0;count=0;negative=[]
    for c in cells.values():
        if '__dff' not in c['type']:continue
        replacement=c['type'].replace('__dff','__sdff')
        extra=0
        if replacement not in areas:
            assert c['type']=='gf180mcu_fd_sc_mcu7t5v0__dffnrnq_1'
            replacement='gf180mcu_fd_sc_mcu7t5v0__sdffrnq_1'
            extra=areas['gf180mcu_fd_sc_mcu7t5v0__inv_1']
            negative.append(dict(original=c['type'],estimated_scan_cell=replacement,estimated_clock_inverter_um2=extra,
                basis='Negative-edge scan estimate: positive-edge scan flop plus clock inverter. T37 must implement and qualify it.'))
        uplift+=areas[replacement]+extra-areas[c['type']];count+=1
    scan.append(dict(main_mhz=mhz,flops=count,estimated_area_uplift_mm2=uplift/1e6,negative_edge_estimates=negative))
scan_uplift=max(r['estimated_area_uplift_mm2'] for r in scan)
allowances={'clock/reset/power controller logic':.10,'boot ROM realization':.50,'SRAM macro wrappers and memory BIST':.05,'scan/test control and insertion glue':.05,'scan-flop cell substitution estimate':scan_uplift}
utilization=.55
placed=(mapped+sum(allowances.values()))/utilization
sram=20*macro
physical={'analog oscillator/POR/supply-monitor macros':.50,'pad interface and in-core keepout allowance':.50,'SRAM halo/channel and unmodelled physical glue':.40}
total=placed+sram+sum(physical.values())
receipt=dict(status='estimated_with_allowances',mapped_logic_mm2_measured=mapped,
    scan_cell_substitution_estimate=scan,scan_basis='Two negative-edge reset flops use a labelled positive-edge scan plus clock-inverter estimate; all other mapped dff[q/rnq/snq] cells replaced by same-drive characterized sdff variants; a planning estimate, not scan insertion or ATPG. Separate control/glue allowance remains assumed.',
    digital_allowances_mm2_assumed_except_scan_estimate=allowances,utilization_assumed=utilization,placed_digital_mm2_estimated=placed,
    logic_routing_whitespace_mm2_estimated=placed-mapped-sum(allowances.values()),
    macro_geometry_um_measured=[width,height],macro_area_mm2_estimated=macro,
    performance_sram=dict(logical_kib=16,count=16,estimated_mm2=16*macro),
    retained_sram=dict(logical_kib=3,physical_kib=4,count=4,estimated_mm2=4*macro,
       basis='Four 1024x8 macros; 256 of 1024 words unused. Capacity/address map remains 3 KiB.'),
    physical_allowances_mm2_assumed=physical,total_mm2_estimated=total,core_budget_mm2=12.92,headroom_mm2_estimated=12.92-total,
    basis='Worst measured standard-cell mapping plus explicitly assumed unbuilt digital allowances, divided by the existing 0.55 utilization; add pinned SRAM bounding boxes and named physical allowances. SRAM whitespace charged separately, not divided by standard-cell utilization. Entire external pad-ring footprint is outside this core budget; T38 must reconcile die and core geometry.',
    limitations='Planning budget only. Boot-ROM contents/implementation, BIST/scan, macro wrappers, analog layout, pad cells, routing and CTS can change it. The ROM allowance is not proof that arbitrary 64 KiB ROM contents fit. T32-T38 must replace each allowance; no tape-out fit claim.',
    lef_sha256=hashlib.sha256(lef.read_bytes()).hexdigest(),producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(base/'area-budget02.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps({k:receipt[k] for k in ('mapped_logic_mm2_measured','scan_cell_substitution_estimate','total_mm2_estimated','headroom_mm2_estimated')}),flush=True)
assert total<=12.92,'T32 area stop condition'
