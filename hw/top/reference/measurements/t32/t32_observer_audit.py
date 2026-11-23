"""Read-only live-cone audit; emitted projection is an experiment, not RTL."""
import collections,copy,hashlib,json,re,sys
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root))
from tools.timing.usb_boundary import groups
source=root/'build/t32/area03/mapped/map-8/canonical.json'
design=json.loads(source.read_text());m=design['modules']['DeadhorseSoc']
lib=root/'build/riscay-mcu/.tools/physical/pdk/gf180mcu_fd_sc_mcu7t5v0__ss_125C_3v00.lib'
areas={n:float(re.search(r'\barea\s*:\s*([\d.]+)',b)[1]) for n,b in groups(lib.read_text(),'cell')}
removed_ports={n:p for n,p in m['ports'].items() if n.startswith('rvfi_')}
assert removed_ports and all(p['direction']=='output' for p in removed_ports.values())
retained_ports={n:p for n,p in m['ports'].items() if n not in removed_ports}
drivers={}
for name,c in m['cells'].items():
    for p,d in c['port_directions'].items():
        if d=='output':
            for b in c['connections'][p]:
                if isinstance(b,int):assert b not in drivers;drivers[b]=name
pending=[b for p in retained_ports.values() if p['direction']=='output' for b in p['bits']]
# Explicit keep cells remain roots (notably the qualified USB mapping).
for c in m['cells'].values():
    if c['attributes'].get('keep','0').strip('0'):
        pending.extend(b for p,d in c['port_directions'].items() if d=='output' for b in c['connections'][p])
live=set()
while pending:
    b=pending.pop();name=drivers.get(b)
    if name is None or name in live:continue
    live.add(name);c=m['cells'][name]
    pending.extend(b for p,d in c['port_directions'].items() if d=='input' for b in c['connections'][p])
removed={n:c for n,c in m['cells'].items() if n not in live}
assert removed
def stats(cells):
    area=sum(areas[c['type']] for c in cells.values());scan=0;ff=0
    for c in cells.values():
        if '__dff' not in c['type']:continue
        ff+=1;replacement=c['type'].replace('__dff','__sdff');extra=0
        if replacement not in areas:
            assert c['type']=='gf180mcu_fd_sc_mcu7t5v0__dffnrnq_1'
            replacement='gf180mcu_fd_sc_mcu7t5v0__sdffrnq_1';extra=areas['gf180mcu_fd_sc_mcu7t5v0__inv_1']
        scan+=areas[replacement]+extra-areas[c['type']]
    return dict(cells=len(cells),flops=ff,logic_mm2_measured=area/1e6,scan_mm2_estimated=scan/1e6)
projected=copy.deepcopy(design);p=projected['modules']['DeadhorseSoc']
p['ports']=copy.deepcopy(retained_ports);p['cells']={n:c for n,c in p['cells'].items() if n in live}
# Certificate: every retained port/cell is byte-for-byte identical, all cell
# input dependencies (clock/reset included) are kept or original primary inputs.
assert all(p['cells'][n]==m['cells'][n] for n in live)
inputs={b for x in retained_ports.values() if x['direction']=='input' for b in x['bits']}
for c in p['cells'].values():
    for pin,d in c['port_directions'].items():
        if d=='input':
            for b in c['connections'][pin]:assert isinstance(b,str) or b in inputs or drivers.get(b) in live,(pin,b)
for port in retained_ports.values():
    if port['direction']=='output':
        for b in port['bits']:assert isinstance(b,str) or b in inputs or drivers.get(b) in live
before=stats(m['cells']);after=stats(p['cells']);saving=stats(removed)
budget=json.loads((root/'build/t32/area03/mapped/area-budget02.json').read_text())
total=budget['total_mm2_estimated']-(saving['logic_mm2_measured']+saving['scan_mm2_estimated'])/.55
out=root/'build/t32/soc-area-review';out.mkdir(exist_ok=True)
(out/'observer-projection.json').write_text(json.dumps(projected))
result=dict(status='measured_closed_dead_cone_projection_not_final_acceptance',removed_ports=removed_ports,removed_cells=removed,
    before=before,after=after,saving=saving,total_mm2_estimated=total,headroom_mm2_estimated=12.92-total,
    proof='Exact retained cell next-function/ports unchanged; every retained output and every cell input including clock/reset has only retained drivers or original primary inputs. No observation output can feed retained state or outputs.',
    limitations='No RTL/features changed; tests retain all observers. This is pruning an existing mapped graph, not fresh mapping/placement/timing; allowances unchanged. Source provenance and independent audit required before budget adoption.',
    source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),library_sha256=hashlib.sha256(lib.read_bytes()).hexdigest(),producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
(out/'observer-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ('before','after','saving','total_mm2_estimated','headroom_mm2_estimated')}))
