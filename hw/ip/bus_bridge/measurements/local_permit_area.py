"""Map the authenticated old single-direction binding and new local grant equally."""
import argparse,hashlib,json,pathlib,re,subprocess,sys,time
ROOT=pathlib.Path.cwd();sys.path.insert(0,str(ROOT))
from tools.timing.usb_boundary import groups
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--baseline',required=True);p.add_argument('--proof',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 out=(ROOT/a.output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
 base=ROOT/a.baseline;proof=ROOT/a.proof
 baseline=json.loads((base/'result.json').read_text());proved=json.loads((proof/'result.json').read_text())
 assert baseline['status'] in ('measured','measured_with_D104_exception') and proved['status']=='pass'
 config=ROOT/'phys/gf180-ws-1x1/block-timing.json';cfg=json.loads(config.read_text())
 lib=ROOT/f'build/riscay-mcu/.tools/physical/pdk/{cfg["library"]}__{cfg["corner"]}.lib';assert sha(lib)==cfg['sha256']
 areas={n:float(re.search(r'\barea\s*:\s*([\d.]+)',b)[1]) for n,b in groups(lib.read_text(),'cell')}
 inputs={str(q):sha(q) for q in (pathlib.Path(__file__),config,lib,base/'result.json',proof/'result.json')}
 commands=[];results={}
 def run(lines,name):
  script=out/(name+'.ys');script.write_text('\n'.join(lines)+'\n');start=time.monotonic()
  with (out/(name+'.log')).open('w') as log:r=subprocess.run(['yosys','-Q','-T','-s',str(script)],stdout=log,stderr=subprocess.STDOUT)
  commands.append(dict(command=['yosys','-Q','-T','-s',str(script)],seconds=time.monotonic()-start,returncode=r.returncode));r.check_returncode()
 for label,top,files,receipt,root in (
  ('before','DirectionPermit',[base/'emit'/n for n in ('DirectionPermit.sv','DirectionArbiter.sv','CdcSync.sv')],baseline,base),
  ('after','LocalPermit',[proof/'emit/block/LocalPermit.sv'],proved,proof)):
  for q in files:
   assert sha(q)==receipt['artifact_sha256'][str(q.relative_to(root))];inputs[str(q)]=sha(q)
  hierarchy=out/(label+'-hier.json')
  run(['read_verilog -sv '+' '.join(map(str,files)),f'hierarchy -check -top {top}','proc',f'write_json {hierarchy}'],label+'-import')
  design=json.loads(hierarchy.read_text())
  if label=='before':
   module=design['modules'][top];bits=module['ports'].pop('requestAon')['bits'];assert len(bits)==1;bit=bits[0]
   # Production's removed direction is tied low; permitAon is unconnected.
   module['ports'].pop('permitAon')
   for port in module['ports'].values():port['bits']=['0' if b==bit else b for b in port['bits']]
   for net in module['netnames'].values():net['bits']=['0' if b==bit else b for b in net['bits']]
   for cell in module['cells'].values():
    for name,connection in cell['connections'].items():cell['connections'][name]=['0' if b==bit else b for b in connection]
  bound=out/(label+'-bound.json');bound.write_text(json.dumps(design))
  constr=out/(label+'.constr');constr.write_text(f'set_driving_cell {cfg["library"]}__buf_1\nset_load 50\n')
  mapped=out/(label+'-mapped.json')
  run([f'read_liberty -lib {lib}',f'read_json {bound}',f'hierarchy -check -top {top}',f'synth -top {top} -flatten -nofsm -noabc',f'dfflibmap -liberty {lib}',
   f'abc -liberty {lib} -constr {constr} -D 75000','clean -purge','check -assert',f'write_json {mapped}',f'stat -liberty {lib}'],label+'-map')
  cells=json.loads(mapped.read_text())['modules'][top]['cells'];assert all(c['type'] in areas for c in cells.values())
  results[label]=dict(area_um2_measured=sum(areas[c['type']] for c in cells.values()),flops_measured=sum('__dff' in c['type'] for c in cells.values()),mapped_sha256=sha(mapped))
 assert inputs=={n:sha(pathlib.Path(n)) for n in inputs}
 receipt=dict(status='measured_area_only',blocks=results,commands=commands,input_sha256=inputs,
  delta_um2_measured=results['after']['area_um2_measured']-results['before']['area_um2_measured'],
  scope='Isolated equal SS125 library/50fF/ABC75ns mapping; old production requestAon tied0 and permitAon unused. Independent clocks retained. Not additive whole-map delta or STA.')
 (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(results))
if __name__=='__main__':main()
