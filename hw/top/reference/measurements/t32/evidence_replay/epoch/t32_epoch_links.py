from pathlib import Path
import ast,copy,hashlib,json,subprocess,time,sys
ROOT=Path.cwd();sys.path.insert(0,str(ROOT));from tools.formal import validate_job
out=ROOT/'build/t32/epoch-links01';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
source=ROOT/'build/t32/epoch-fifo02/runner.py';tree=ast.parse(source.read_text());fun=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='attach');exec(compile(ast.Module(body=[fun],type_ignores=[]),str(source),'exec'))
base=json.loads((ROOT/'build/t32/epoch-fifo02/combined.json').read_text());m=base['modules']['DebugEpochFormal'];nets=m['netnames']
for name in ['requests','responses']:
 d=ROOT/'build/t32/epoch-fifo02'/name;r=json.loads((d/'result.json').read_text());assert r['status']=='PASS' and r['returncode']==0
 assert sha(d/'model.json')==r['model_sha256'] and sha(d/'job.sby')==r['config_sha256'];validate_job(d/'job','proof',0,'PASS')
control=ROOT/'build/t32/epoch-partition01';r=json.loads((control/'control.json').read_text());assert r['status']=='PASS' and r['returncode']==0
validate_job(control/'control','proof',0,'PASS');cfg=(control/'control.sby').read_text();assert cfg.count('chformal -assert -remove')==1 and 'chformal -assert -remove c:assert__chisel3_builtin_0' in cfg and '-assume' not in cfg and '-assert2assume' not in cfg
inputs=json.loads((ROOT/'build/t32/epoch-lanes02/inputs.json').read_text());assert all(sha(p)==h for p,h in inputs['source_sha256'].items())
assert {p.name:sha(p) for p in (control/'control/src').glob('*.sv')}=={Path(p).name:h for p,h in inputs['source_sha256'].items()}
ports={'main':'main','aon':'aon','mainUp':'bridge.producer.reset_n','aonUp':'bridge.consumer.reset_n','transportUp':'bridge.requests.writeReset_n','expected':'expected','requestPush':'bridge.requests.push','requestData':'bridge.requests.in','requestValid':'bridge.requests.valid','requestOut':'bridge.requests.out','phase':'bridge.consumer.phase','linkUp':'bridge.consumer.linkUp','poison':'bridge.consumer.poison','active':'active','endpointResult':'result','targetValid':'bridge.consumer.target_rvalid','targetError':'bridge.consumer.target_err','targetData':'bridge.consumer.target_rdata','replyPending':'bridge.consumer.replyPending','reply':'bridge.consumer.reply','responseValid':'bridge.responses.valid','responseData':'bridge.responses.out','sourceValid':'bridge.producer.source_rvalid','sourceError':'bridge.producer.source_err','sourceData':'bridge.producer.source_rdata','fabricValid':'f.master_0_rvalid','fabricError':'f.master_0_err','fabricData':'f.master_0_rdata'}
bind={p:nets[n]['bits'] for p,n in ports.items()}
bind['captured']=[b for p in ['origin','we','be','wdata','addr'] for b in nets['captured_'+p]['bits']]
bind['packet']=[b for p in ['origin','we','be','wdata','addr'] for b in nets['bridge.consumer.packet_'+p]['bits']]
script=out/'observer.ys';script.write_text(f'read_slang --top DebugEpochLinks {out}/emit/DebugEpochLinks.sv\nprep -top DebugEpochLinks -flatten\nwrite_json {out}/observer.json\n')
with(out/'observer.log').open('w') as f:subprocess.run(['yosys','-Q','-T','-s',str(script)],stdout=f,stderr=subprocess.STDOUT,check=True)
obs=json.loads((out/'observer.json').read_text());obs['modules']['DebugFifoOracle']=obs['modules'].pop('DebugEpochLinks')
model,added=attach(base,obs,bind,'links.');(out/'model.json').write_text(json.dumps(model)+'\n')
lemmas=[n for n,c in m['cells'].items() if c['type']=='$check' and c['parameters'].get('FLAVOR')=='assert' and n!='assert__chisel3_builtin_0'];assert len(lemmas)==23
config=out/'job.sby';config.write_text('\n'.join(['[options]','mode prove','depth 96','timeout 120','multiclock on','[engines]','abc pdr','aiger suprove','smtbmc yices','[script]','read_json model.json','hierarchy -top DebugEpochFormal','clk2fflogic','chformal -lower','select -assert-count 33 t:$assert','select -set proved '+' '.join('c:'+n for n in lemmas),'select -assert-count 23 @proved','chformal -assert2assume @proved','select -assert-count 10 t:$assert','select -assert-count 24 t:$assume','opt_clean -purge','[files]',str(out/'model.json')])+'\n')
(out/'runner.py').write_bytes(Path(__file__).read_bytes());command=['sby','-d',str(out/'job'),str(config)];start=time.monotonic()
with(out/'run.log').open('w') as f:
 try:code=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,timeout=180).returncode
 except subprocess.TimeoutExpired:code=124
status=(out/'job/status').read_text().split()[0] if (out/'job/status').exists() else 'ERROR'
r=dict(status=status,returncode=code,seconds=time.monotonic()-start,command=command,bindings=bind,cell_additions=added,lemmas=lemmas,source_sha256=inputs['source_sha256'],model_sha256=sha(out/'model.json'),config_sha256=sha(config))
(out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(status,flush=True)
