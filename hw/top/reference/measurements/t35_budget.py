"""T35 whole-chip planning budget: real SRAM instances, LEF footprints and BIST."""
import argparse
import collections
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
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    mapped=base/'map/canonical.json';mapping=json.loads((base/'map/result.json').read_text())
    assert mapping['status']=='mapped' and mapping.get('sram_liberty')
    assert digest(mapped)==mapping['mapped_sha256']
    cfg=json.loads((ROOT/'phys/gf180-ws-1x1/block-timing.json').read_text())
    lib=ROOT/f'build/riscay-mcu/.tools/physical/pdk/{cfg["library"]}__{cfg["corner"]}.lib'
    assert digest(lib)==cfg['sha256']
    areas={n:float(re.search(r'\barea\s*:\s*([\d.]+)',b)[1]) for n,b in groups(lib.read_text(),'cell')}
    lock_path=ROOT/'hw/vendor/gf180_sram/gf180_sram.lock.json';lock=json.loads(lock_path.read_text());macro=lock['macro']
    cells=json.loads(mapped.read_text())['modules']['DeadhorseSoc']['cells']
    macro_types={macro,lock['retained_macro']}
    macros={n:c for n,c in cells.items() if c['type'] in macro_types}
    assert len(macros)==20 and sum(n.startswith('digital.memory.') for n in macros)==16
    assert sum(n.startswith('digital.subsystem.retained.') for n in macros)==4
    assert all(c['type']==macro for n,c in macros.items() if n.startswith('digital.memory.'))
    assert all(c['type']==lock['retained_macro'] for n,c in macros.items() if n.startswith('digital.subsystem.retained.'))
    views=[];footprints={}
    for cell in sorted(macro_types):
        relative=f'cells/{cell}/{cell}.lef';lef=ROOT/'build/vendor/gf180_sram'/relative
        assert digest(lef)==lock['files'][relative]
        width,height=map(float,re.search(r'\bSIZE\s+([\d.]+)\s+BY\s+([\d.]+)',lef.read_text()).groups())
        count=sum(c['type']==cell for c in macros.values())
        footprints[cell]=dict(width_um_measured=width,height_um_measured=height,
            instances_measured=count,area_mm2_estimated=count*width*height/1e6)
        views.append(lef)
    digital={n:c for n,c in cells.items() if c['type'] not in macro_types}
    assert all(c['type'] in areas for c in digital.values())
    # ABC renames combinational cells. Attribute actual endpoint cones using
    # retained net aliases, with uniquely-owned source files as state fallback.
    # Shared logic is counted once rather than charged to multiple blocks.
    prefixes={'digital.subsystem.bist':'bist',
        'digital.subsystem.debugger.custom':'custom_dmi',
        'digital.memory':'local_memory_control',
        'digital.subsystem.retained':'retained_memory_control'}
    def label(path):
        return next((v for p,v in prefixes.items() if path==p or path.startswith(p+'.')), 'other_production_logic')
    module=json.loads(mapped.read_text())['modules']['DeadhorseSoc']
    aliases=collections.defaultdict(set)
    for name,net in module['netnames'].items():
        if net.get('hide_name'):continue
        for bit in net['bits']:
            if isinstance(bit,int):aliases[bit].add(label(name))
    hierarchy=base/'map/bound-hier.json'
    src_groups=collections.defaultdict(set)
    for name,mod in json.loads(hierarchy.read_text())['modules'].items():
        source=mod.get('attributes',{}).get('src','').split(':')[0]
        if source:src_groups[source].add(label(name.split('$',1)[-1].removeprefix('DeadhorseSoc.')))
    drivers={};state={};owners={}
    for name,cell in cells.items():
        for pin,direction in cell['port_directions'].items():
            if direction=='output':
                for bit in cell['connections'][pin]:
                    if isinstance(bit,int):
                        assert bit not in drivers
                        drivers[bit]=name
        if any(p in cell['connections'] for p in ('CLK','CLKN')):
            state[name]=cell
            found=set().union(*(aliases[b] for b in cell['connections'].get('Q',[])))
            if not found:found=src_groups[cell.get('attributes',{}).get('src','').split(':')[0]]
            owners[name]=({label(name)} if cell['type'] in macro_types else found) or {'other_production_logic'}
    queue=collections.deque(owners)
    while queue:
        name=queue.popleft()
        for pin,direction in cells[name]['port_directions'].items():
            if direction!='input' or pin in ('CLK','CLKN'):continue
            for bit in cells[name]['connections'][pin]:
                source=drivers.get(bit)
                if source is None or source in state:continue
                before=owners.setdefault(source,set());extra=owners[name]-before
                if extra:before.update(extra);queue.append(source)
    partitions={}
    for name,cell in digital.items():
        found=owners.get(name,set())
        group=next(iter(found)) if len(found)==1 else 'shared_interblock_glue' if found else 'output_only_glue'
        row=partitions.setdefault(group,dict(cells_measured=0,area_um2_measured=0,scan_uplift_um2_estimated=0))
        row['cells_measured']+=1;row['area_um2_measured']+=areas[cell['type']]
        if '__dff' in cell['type']:
            replacement=cell['type'].replace('__dff','__sdff');extra=0
            if replacement not in areas:
                assert cell['type']=='gf180mcu_fd_sc_mcu7t5v0__dffnrnq_1'
                replacement='gf180mcu_fd_sc_mcu7t5v0__sdffrnq_1';extra=areas['gf180mcu_fd_sc_mcu7t5v0__inv_1']
            row['scan_uplift_um2_estimated']+=areas[replacement]+extra-areas[cell['type']]
    measured=sum(r['area_um2_measured'] for r in partitions.values())/1e6
    scan=sum(r['scan_uplift_um2_estimated'] for r in partitions.values())/1e6
    clock_path=base/'new-digital-area/result.json';clock=json.loads(clock_path.read_text())
    assert clock['status']=='measured_area_only'
    for name,value in clock['input_sha256'].items():assert digest(ROOT/name)==value
    clock_spent=(clock['digital_area_um2_measured']+clock['scan_uplift_um2_estimated'])/1e6
    assert clock_spent<=.10,'Existing clock/reset digital allowance exceeded'
    allowances=dict(clock_reset_remaining_mm2_estimated=.10-clock_spent,
        rom_mm2_assumed=.50,scan_glue_mm2_assumed=.05,bist_remaining_mm2_assumed=0,
        scan_cell_substitution_mm2_estimated=scan)
    physical=dict(lf_rc_mm2_assumed=.10,por_brownout_mm2_assumed=.15,pad_keepout_mm2_assumed=.50,sram_halo_glue_mm2_assumed=.40)
    placed=(measured+sum(allowances.values()))/.55
    sram=sum(r['area_mm2_estimated'] for r in footprints.values());total=placed+sram+sum(physical.values())
    # Capacity options are estimates, not a decision or a substitute for mapping
    # their additional decode/selection logic. Existing halo/glue allowance stays.
    unit=footprints[macro]['width_um_measured']*footprints[macro]['height_um_measured']/1e6
    options={str(k):dict(extra_macro_instances_estimated=k-16,
        extra_macro_mm2_estimated=(k-16)*unit,total_mm2_estimated=total+(k-16)*unit,
        headroom_mm2_estimated=12.92-total-(k-16)*unit,
        fits_macro_only_estimate=total+(k-16)*unit<=12.92,
        qualification='Additional decode/control area and timing unmeasured; no SRAM growth approved') for k in (16,24,32)}
    result=dict(status='estimated_with_allowances',partitions=partitions,
        mapped_logic_mm2_measured=measured,macro_instances_measured=len(macros),
        macro_footprints=footprints,sram_mm2_estimated=sram,main_sram_options=options,
        digital_allowances=allowances,physical_allowances=physical,utilization_assumed=.55,
        placed_digital_mm2_estimated=placed,total_mm2_estimated=total,ceiling_mm2=12.92,headroom_mm2_estimated=12.92-total,
        partition_method='Exclusive backward endpoint cones, stopping at sequential outputs; named net aliases and source ownership label state. Shared and output-only glue counted once. Allocation of flattened cells, not isolated block areas.',
        basis='Macro area = instance count * pinned LEF width * height. All built BIST/controller/adapter cells are in measured digital area; original 0.05 BIST placeholder replaced, not double-counted. ROM and analog/placement/scan remain assumptions, not signoff.',
        inputs={p.relative_to(ROOT).as_posix():digest(p) for p in [mapped,hierarchy,lib,lock_path,clock_path,Path(__file__)]+views})
    (base/'area-budget.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
    if total>12.92:raise RuntimeError('T35 area-budget stop condition')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',required=True);main(p.parse_args().base)
