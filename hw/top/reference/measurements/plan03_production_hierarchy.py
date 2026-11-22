import json, subprocess, hashlib
from pathlib import Path
root=Path.cwd()
out=root/'build/plan03/production-measure01'
lib=root/'build/riscay-mcu/.tools/physical/pdk/gf180mcu_fd_sc_mcu7t5v0__ss_125C_3v00.lib'
for mhz in (8,9):
    emit=out/f'emit-{mhz}'
    dest=out/f'map-{mhz}';dest.mkdir(exist_ok=False)
    files=[emit/line.strip() for line in (emit/'filelist.f').read_text().splitlines() if line.strip()]
    script=dest/'import.ys'
    script.write_text('\n'.join([f'read_liberty -lib {lib}',
      'read_slang --keep-hierarchy -DSYNTHESIS --top DeadhorseSoc '+' '.join(map(str,files)),
      'hierarchy -check -top DeadhorseSoc','proc','chformal -remove','memory_collect',
      f'write_json {dest}/hier.json','stat'])+'\n')
    with (dest/'import.log').open('w') as stream:
        subprocess.run(['yosys','-Q','-T','-s',str(script)],stdout=stream,stderr=subprocess.STDOUT,check=True)
    design=json.loads((dest/'hier.json').read_text())
    inv=[]
    def walk(module,path):
        for name,c in design['modules'][module]['cells'].items():
            instance=path+'.'+name if path else name
            if c['type']=='$mem_v2':
                inv.append(dict(instance=instance,module=module,name=name,
                  parameters={k:int(v,2) for k,v in c['parameters'].items() if k in ('WIDTH','SIZE','ABITS','RD_PORTS','WR_PORTS','RD_CLK_ENABLE','WR_CLK_ENABLE')}))
            elif c['type'] in design['modules'] and not design['modules'][c['type']].get('attributes',{}).get('blackbox'):
                walk(c['type'],instance)
    walk('DeadhorseSoc','')
    (dest/'memory-inventory.json').write_text(json.dumps(inv,indent=2)+'\n')
    print(mhz, json.dumps(inv),flush=True)
