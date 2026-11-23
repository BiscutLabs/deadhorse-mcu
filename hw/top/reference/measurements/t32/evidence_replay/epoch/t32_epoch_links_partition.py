from pathlib import Path
import json,hashlib,subprocess,time,sys
ROOT=Path.cwd();sys.path.insert(0,str(ROOT));from tools.formal import validate_job
base=ROOT/'build/t32/epoch-links01';out=ROOT/'build/t32/epoch-links-partition01';out.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();model=base/'model.json'
original=json.loads((base/'runner.py').read_text()) if False else json.loads((base/'model.json').read_text())
cs=original['modules']['DebugEpochFormal']['cells'];names={n for n,c in cs.items() if c['type']=='$check' and c['parameters'].get('FLAVOR')=='assert'}
assert len(names)==33
proved=sorted(n for n in names if not n.startswith('links.') and n!='assert__chisel3_builtin_0');assert len(proved)==23
sequence=['links.assert__chisel3_builtin','links.assert__chisel3_builtin_3','links.assert__chisel3_builtin_4','links.assert__chisel3_builtin_5','links.assert__chisel3_builtin_6','links.assert__chisel3_builtin_7','links.assert__chisel3_builtin_0','links.assert__chisel3_builtin_1','links.assert__chisel3_builtin_2','assert__chisel3_builtin_0']
(out/'runner.py').write_bytes(Path(__file__).read_bytes());receipt=dict(status='running',model_sha256=sha(model),initial_proved=proved[:],jobs=[])
for i,name in enumerate(sequence):
 f=out/f'property{i}';f.mkdir();cfg=f/'job.sby';removed=sorted(names-set(proved)-{name})
 cfg.write_text('\n'.join(['[options]','mode prove','depth 96','timeout 120','multiclock on','[engines]','abc pdr','aiger suprove','smtbmc yices','[script]','read_json model.json','hierarchy -top DebugEpochFormal','clk2fflogic','chformal -lower','select -assert-count 33 t:$assert','select -set proved '+' '.join('c:'+n for n in proved),f'select -assert-count {len(proved)} @proved','chformal -assert2assume @proved',*(['chformal -assert -remove '+' '.join('c:'+n for n in removed)] if removed else []),'select -assert-count 1 t:$assert',f'select -assert-count {len(proved)+1} t:$assume','opt_clean -purge','[files]',str(model)])+'\n')
 # Every added assumed property must have this exact immutable model's PASS receipt.
 for prior in receipt['jobs']:
  assert prior['status']=='PASS' and prior['model_sha256']==sha(model)
  validate_job(out/prior['folder']/'job','proof',prior['returncode'],'PASS')
 t=time.monotonic();cmd=['sby','-d',str(f/'job'),str(cfg)]
 with(f/'run.log').open('w') as log:
  try:code=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,timeout=180).returncode
  except subprocess.TimeoutExpired:code=124
 status=(f/'job/status').read_text().split()[0] if (f/'job/status').exists() else 'ERROR'
 row=dict(property=name,folder=f.name,status=status,returncode=code,command=cmd,seconds=time.monotonic()-t,model_sha256=sha(model),config_sha256=sha(cfg),assumed=proved[:])
 receipt['jobs'].append(row);print(name,status,flush=True)
 (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
 if status!='PASS':receipt['status']='unresolved';break
 validate_job(f/'job','proof',code,status);proved.append(name)
else:receipt['status']='pass'
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
