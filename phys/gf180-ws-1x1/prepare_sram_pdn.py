"""Prepare D109 SRAM macro/PDN inputs; fail closed on inventory or geometry drift."""
import argparse,copy,hashlib,json,pathlib,re,sys
import yaml
ROOT=pathlib.Path(__file__).resolve().parents[2];HERE=pathlib.Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def validate(rows,inventory,core,halo):
 if {n:size for n,size,x,y,w,h in rows}!=inventory:raise ValueError('Macro inventory mismatch')
 if len(rows)!=len(inventory):raise ValueError('Duplicate macro')
 for i,(name,size,x,y,w,h) in enumerate(rows):
  if not(core[0]<=x-halo and core[1]<=y-halo and x+w+halo<=core[2] and y+h+halo<=core[3]):raise ValueError('Outside core')
  for other in rows[:i]:
   _,_,ox,oy,ow,oh=other
   if not(x+w+2*halo<=ox or ox+ow+2*halo<=x or y+h+2*halo<=oy or oy+oh+2*halo<=y):raise ValueError('Macro halo overlap')
def main():
 p=argparse.ArgumentParser()
 for n in ('template','elaboration','output'):p.add_argument('--'+n,required=True)
 a=p.parse_args();template,elab,out=[(ROOT/getattr(a,n)).resolve() for n in ('template','elaboration','output')]
 for q in (template,elab,out):q.relative_to(ROOT/'build')
 out.mkdir(parents=True,exist_ok=False)
 checked=json.loads((elab/'result.json').read_text());assert checked['status']=='elaborated_not_physical'
 for n,h in checked['artifact_sha256'].items():assert sha(elab/n)==h
 for n,h in checked['input_sha256'].items():assert sha(ROOT/n)==h
 design=json.loads((elab/'design.json').read_text())['modules'];inventory={}
 def walk(module,path):
  for name,c in design[module]['cells'].items():
   inst=(path+'.' if path else '')+name
   if c['type'] in ('gf180mcu_ocd_ip_sram__sram1024x8m8wm1','gf180mcu_ocd_ip_sram__sram512x8m8wm1'):inventory[inst]=1024 if '1024' in c['type'] else 512
   elif c['type'] in design and not design[c['type']].get('attributes',{}).get('blackbox'):walk(c['type'],inst)
 walk('chip_top','');assert list(inventory.values()).count(1024)==16 and list(inventory.values()).count(512)==4
 plan=yaml.safe_load((HERE/'sram-placement.yaml').read_text());template_lock=json.loads((HERE/'template.lock.json').read_text())
 names=['librelane/macros/macros_3v3.yaml','librelane/pdn/pdn_3v3_sram.tcl','librelane/slots/slot_1x1.yaml']
 inputs={}
 def bind(q):inputs[q.relative_to(ROOT).as_posix()]=sha(q)
 for n in names:assert sha(template/n)==template_lock['files'][n];bind(template/n)
 assert plan['core']==yaml.safe_load((template/names[2]).read_text())['CORE_AREA']
 macro_lock_path=ROOT/'hw/vendor/gf180_sram/gf180_sram.lock.json';macro_lock=json.loads(macro_lock_path.read_text())
 for q in (pathlib.Path(__file__),HERE/'sram-placement.yaml',HERE/'template.lock.json',macro_lock_path,elab/'result.json',elab/'design.json'):bind(q)
 def view(size,suffix):
  macro=f'gf180mcu_ocd_ip_sram__sram{size}x8m8wm1';relative=f'cells/{macro}/{macro}{suffix}'
  q=ROOT/'build/vendor/gf180_sram'/relative;assert sha(q)==macro_lock['files'][relative];bind(q);return q
 dimensions={}
 for size in (1024,512):
  lef=view(size,'.lef');dimensions[size]=tuple(map(float,re.search(r'\bSIZE\s+([\d.]+)\s+BY\s+([\d.]+)\s*;',lef.read_text()).groups()))
 rows=[(g['instance']+f'.physical_{lane}',g['size'],x,g['y'],*dimensions[g['size']]) for g in plan['groups'] for lane,x in enumerate(plan['lane_x'])]
 validate(rows,inventory,plan['core'],plan['halo_um_assumed'])
 rejected=[]
 for fault in ('missing','overlap','outside'):
  bad=list(rows)
  if fault=='missing':bad.pop()
  elif fault=='overlap':bad[1]=(*bad[1][:2],bad[0][2],bad[0][3],*bad[1][4:])
  else:bad[0]=(*bad[0][:2],0,0,*bad[0][4:])
  try:validate(bad,inventory,plan['core'],plan['halo_um_assumed'])
  except ValueError:rejected.append(fault)
  else:raise AssertionError('Geometry fault escaped')
 config=yaml.safe_load((template/names[0]).read_text());macros=config['MACROS']
 macros.pop('gf180mcu_ocd_ip_sram__sram512x8m8wm1')
 # Template artwork paths must keep pointing at authenticated source collateral.
 def artwork(s):
  q=(template/'librelane'/s.removeprefix('dir::')).resolve()
  relative=q.relative_to(template).as_posix();assert sha(q)==template_lock['files'][relative]
  bind(q);return str(q)
 for spec in macros.values():
  for key in ('gds','lef','vh'):
   spec[key]=[artwork(s) for s in spec[key]]
  spec['lib']={k:[artwork(s) for s in v] for k,v in spec['lib'].items()}
 for size in (1024,512):
  macro=f'gf180mcu_ocd_ip_sram__sram{size}x8m8wm1'
  macros[macro]=dict(gds=[str(view(size,'.gds'))],lef=[str(view(size,'.lef'))],vh=[str(view(size,'__blackbox_pp.v'))],
    lib={'*_'+corner:[str(view(size,'__'+corner+'.lib'))] for corner in ('tt_025C_3v30','ff_n40C_3v60','ss_125C_3v00')},
    instances={name:dict(location=[x,y],orientation='N') for name,s,x,y,w,h in rows if s==size})
 config['PDN_MACRO_CONNECTIONS']=[f'{name} VDD VSS VDD VSS' for name,*_ in rows]
 (out/'macros_3v3.yaml').write_text(yaml.safe_dump(config,sort_keys=False))
 pdn=(template/names[1]).read_text();marker='define_pdn_grid \\\n    -macro \\\n    -instances i_chip_core.sram_1'
 assert pdn.count(marker)==1 and pdn.count('-instances i_chip_core.sram_0')==1
 pdn=pdn.split(marker)[0].replace('-instances i_chip_core.sram_0','-instances {'+' '.join(inventory)+'}')
 (out/'pdn_3v3_sram.tcl').write_text(pdn)
 result=dict(status='prepared_sram_only_not_physical_fit',input_sha256=inputs,rows=rows,negative_controls=rejected,
  scope='N-only preliminary SRAM placement and inherited same-width SRAM PDN grid; analog views and complete chip PDN/fit unqualified',halo_um_assumed=plan['halo_um_assumed'])
 result['artifact_sha256']={q.name:sha(q) for q in out.iterdir() if q.is_file()}
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS D109 macro inventory, preliminary bounds/halo checks and three faults; no chip physical fit claim')
if __name__=='__main__':main()
