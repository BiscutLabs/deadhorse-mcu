import copy,hashlib,json,shutil,subprocess,sys
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root))
from t32_layered_reset import layered
from tools.timing.fanout import verify
source=root/'build/t32/area04/mapped/map-8';out=root/'build/t32/area06/mapped/map-8';out.mkdir(parents=True,exist_ok=False)
design=json.loads((source/'unbuffered.json').read_text());m=design['modules']['DeadhorseSoc']
primary={b for p in m['ports'].values() if p['direction']=='input' for b in p['bits']}
sources={b for c in m['cells'].values() for pin,bs in c['connections'].items() if pin in ('RN','SETN') for b in bs if isinstance(b,int)}-primary
new,inserted,rows=layered(m,sources)
fault=copy.deepcopy(new);first=inserted[0];fault['cells'][first]['connections']['I']=fault['cells'][first]['connections']['Z'][:]
try:verify(m,fault,inserted)
except ValueError:pass
else:raise AssertionError('Buffer cycle escaped')
renames=json.loads((source/'replica-renames.json').read_text())
for old,short in renames.items():
    c=new['cells'].pop(old);new['cells'][short]=c
    c['attributes']['usb_enable_original']='subsystem.usb.'+c['attributes']['usb_enable_original']
design['modules']['DeadhorseSoc']=new
(out/'mapped.json').write_text(json.dumps(design))
for name in ('bound-hier.json','macro-sockets.json','observer-boundary.json','replica-renames.json','splice.json','island-preservation.json'):
    shutil.copyfile(source/name,out/name)
cfg=json.loads((root/'phys/gf180-ws-1x1/block-timing.json').read_text())
lib=root/f'build/riscay-mcu/.tools/physical/pdk/{cfg["library"]}__{cfg["corner"]}.lib'
script=out/'export.ys'
script.write_text('\n'.join([f'read_json {out}/mapped.json','check -assert','scc -expect 0',
    f'tee -o {out}/area.txt stat -liberty {lib}',f'write_json {out}/canonical.json',f'write_verilog -noattr -noexpr {out}/mapped.v','']))
with(out/'export.log').open('w') as f:subprocess.run(['yosys','-Q','-T','-s',str(script)],stdout=f,stderr=subprocess.STDOUT,check=True)
receipt=dict(status='graph_verified_timing_pending',source_sha256=hashlib.sha256((source/'unbuffered.json').read_bytes()).hexdigest(),
    cell='gf180mcu_fd_sc_mcu7t5v0__buf_4',fanout_limit=8,reset_buffers=len(inserted),roots=rows,buffer_cycle_fault='rejected',
    qualification='Only reset tree changes versus area04; USB cells preserved except verified reset input buffering. No RTL or fanout-limit change. Full layers give equal inserted depth for all original sinks on each root. Timing/electrical qualification pending.',
    producer_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),root/'scratch/t32_layered_reset.py',root/'scratch/t32_packed_reset.py']})
(out/'mapping.json').write_text(json.dumps(receipt,indent=2)+'\n');print('Layered reset buffers',len(inserted))
for name in ('partition','budget'):
    target=root/f'scratch/t32_area06_{name}.py'
    target.write_text((root/f'scratch/t32_area04_{name}.py').read_text().replace('build/t32/area04','build/t32/area06'),encoding='utf-8')
    p=subprocess.run(['python',str(target)]);assert p.returncode==0,(name,p.returncode)
