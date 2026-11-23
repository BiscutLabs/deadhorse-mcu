"""Actual FIFO component composition on the unchanged epoch transition graph."""
from pathlib import Path
import copy,json,hashlib,subprocess,time,sys,concurrent.futures
ROOT=Path.cwd();sys.path.insert(0,str(ROOT));from tools.formal import validate_job
out=ROOT/'build/t32/epoch-fifo02';out.mkdir(exist_ok=False);__import__('shutil').copytree(ROOT/'build/t32/epoch-fifo01/emit',out/'emit');base=json.loads((ROOT/'build/t32/epoch-lanes02/raw.json').read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
inputs=json.loads((ROOT/'build/t32/epoch-lanes02/inputs.json').read_text())
assert sha(ROOT/'build/t32/epoch-lanes02/raw.json')==inputs['raw_sha256']
assert all(sha(p)==h for p,h in inputs['source_sha256'].items())
(out/'runner.py').write_bytes(Path(__file__).read_bytes())

def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def command(cmd,log,limit=180):
 t=time.monotonic()
 with log.open('w') as f:
  try:code=subprocess.run(list(map(str,cmd)),stdout=f,stderr=subprocess.STDOUT,timeout=limit).returncode
  except subprocess.TimeoutExpired:code=124
 return dict(command=list(map(str,cmd)),returncode=code,seconds=time.monotonic()-t)

def attach(model,observer,bindings,prefix):
 result=copy.deepcopy(model);target=result['modules']['DebugEpochFormal'];obs=observer['modules']['DebugFifoOracle']
 assert all(p['direction']=='input' for p in obs['ports'].values())
 assert set(bindings)==set(obs['ports'])
 used={b for c in target['cells'].values() for bs in c['connections'].values() for b in bs if isinstance(b,int)}
 used|={b for n in target['netnames'].values() for b in n['bits'] if isinstance(b,int)}
 nxt=max(used)+1;mapping={}
 for n,bs in bindings.items():
  assert len(bs)==len(obs['ports'][n]['bits'])
  for a,b in zip(obs['ports'][n]['bits'],bs):assert a not in mapping or mapping[a]==b;mapping[a]=b
 incoming=set(mapping)
 def translate(bs):
  nonlocal nxt
  ans=[]
  for b in bs:
   if isinstance(b,int):
    if b not in mapping:mapping[b]=nxt;nxt+=1
    b=mapping[b]
   ans.append(b)
  return ans
 added=[]
 for n,c in obs['cells'].items():
  assert c['type']!='$assume'
  if c['type']=='$check':assert c['parameters']['FLAVOR']=='assert'
  assert not any(b in incoming for p,bs in c['connections'].items() if c['port_directions'][p]=='output' for b in bs)
  key=prefix+n;assert key not in target['cells'];added.append(key)
  nc=copy.deepcopy(c);nc['connections']={p:translate(bs) for p,bs in c['connections'].items()};target['cells'][key]=nc
 # Inverse deletion must recover the exact original graph, not just its ports.
 inv=copy.deepcopy(result)
 for n in added:del inv['modules']['DebugEpochFormal']['cells'][n]
 assert inv==model
 return result,added

portmap={'wc':'writeClock','rc':'readClock','wn':'writeReset_n','rn':'readReset_n','push':'push','data':'in','ready':'ready','pop':'pop','valid':'valid','result':'out'}

def extract(prefix):
 m=base['modules']['DebugEpochFormal'];bits=lambda n:m['netnames'][prefix+n]['bits']
 pp={p:dict(direction='input' if p in ['writeClock','readClock','writeReset_n','readReset_n','push','in','pop'] else 'output',bits=bits(p)) for p in ['writeClock','readClock','writeReset_n','readReset_n','push','in','pop','out','ready','valid']}
 stops={b for p in pp.values() if p['direction']=='input' for b in p['bits']};drivers={}
 for n,c in m['cells'].items():
  for p,bs in c['connections'].items():
   if c['port_directions'][p]=='output':
    for b in bs:
     if isinstance(b,int):assert b not in drivers;drivers[b]=n
 pending=[b for p in pp.values() if p['direction']=='output' for b in p['bits']];cells=set();visited=set()
 while pending:
  b=pending.pop()
  if not isinstance(b,int) or b in stops or b in visited:continue
  visited.add(b);assert b in drivers,('undriven',b);n=drivers[b]
  if n in cells:continue
  cells.add(n);c=m['cells'][n]
  # No producer, consumer, fabric or reset qualification is silently kept/cut.
  src=c['attributes'].get('src','');assert any('/'+x+'.sv:' in src for x in ['CdcFifo','CdcFifo_1','CdcRead','CdcRead_1','CdcWrite','CdcWrite_1','CdcSync','CdcSync_4','ResetRelease']),src
  pending += [b for p,bs in c['connections'].items() if c['port_directions'][p]=='input' for b in bs]
 mm=dict(attributes={'top':'1'},ports=pp,cells={n:copy.deepcopy(m['cells'][n]) for n in sorted(cells)},netnames={p:dict(hide_name=0,bits=d['bits'],attributes={}) for p,d in pp.items()})
 return dict(creator=base.get('creator',''),modules={'DebugEpochFormal':mm}),{k:bits(v) for k,v in portmap.items()},sorted(cells)

def job(label,model,helper=False,negative=False,compose=False):
 folder=out/label;folder.mkdir(exist_ok=False);save(folder/'model.json',model)
 commands=['read_json model.json','hierarchy -top DebugEpochFormal',"fminit -seq writeReset_n 0,'z" if helper else '', 'clk2fflogic','chformal -lower']
 if compose:
  commands+=['select -assert-count 24 t:$assert','select -set data_property c:assert__chisel3_builtin_0','chformal -assert2assume t:$assert @data_property %d','select -assert-count 1 t:$assert','select -assert-count 24 t:$assume']
 else:commands+=['select -assert-count 4 t:$assert','select -assert-count 1 t:$assume']
 commands+=['opt_clean -purge']
 cfg=folder/'job.sby';cfg.write_text('\n'.join(['[options]','mode bmc' if negative else 'mode prove','depth 96','timeout 120','multiclock on','[engines]','smtbmc yices' if negative else 'abc pdr\naiger suprove\nsmtbmc yices','[script]',*filter(None,commands),'[files]',str(folder/'model.json')])+'\n')
 r=command(['sby','-d',folder/'job',cfg],folder/'run.log');status=folder/'job/status';r['status']=status.read_text().split()[0] if status.exists() else 'ERROR'
 r['model_sha256']=sha(folder/'model.json');r['config_sha256']=sha(cfg)
 if r['status'] not in ['TIMEOUT','ERROR']:r['failed_properties']=validate_job(folder/'job','negative' if negative else 'proof',r['returncode'],r['status'])
 save(folder/'result.json',r);print(label,r['status'],flush=True);return r

combined=copy.deepcopy(base);components=[];record=dict(source_sha256=inputs['source_sha256'],original_sha256=inputs['raw_sha256'],components=[])
for name,width in [('requests',72),('responses',33)]:
 hdl=out/f'emit/w{width}/DebugFifoOracle.sv';yp=out/f'observer{width}.ys';jp=out/f'observer{width}.json'
 yp.write_text(f'read_slang --top DebugFifoOracle {hdl}\nprep -top DebugFifoOracle -flatten\nwrite_json {jp}\n')
 rr=command(['yosys','-Q','-T','-s',yp],out/f'observer{width}.log');assert rr['returncode']==0
 observer=json.loads(jp.read_text());component,bindings,cells=extract('bridge.'+name+'.')
 attached,added=attach(component,observer,bindings,name+'_oracle.')
 combined,original_added=attach(combined,observer,bindings,name+'_oracle.')
 assert added==original_added
 row=dict(name=name,width=width,extracted_cell_names=cells,bindings=bindings,observer_sha256=sha(jp),observer_hdl_sha256=sha(hdl),inverse_exact=True)
 record['components'].append(row);components.append((name,attached))
save(out/'combined.json',combined);save(out/'binding.json',record)
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 results=list(pool.map(lambda pair:job(pair[0],pair[1],helper=True),components))
record['proofs']=results;save(out/'result.json',record)
if not all(r['status']=='PASS' for r in results):print('component unresolved',flush=True);sys.exit(1)
# All interface lemmas are proved against literal cell subsets of this same model.
# Compose with the existing original control proof, authenticated separately.
control=ROOT/'build/t32/epoch-partition01';cr=json.loads((control/'control.json').read_text())
assert cr['status']=='PASS' and cr['returncode']==0 and cr['mode']=='prove'
validate_job(control/'control','proof',0,'PASS')
assert {p.name:sha(p) for p in (control/'control/src').glob('*.sv')}=={Path(p).name:h for p,h in inputs['source_sha256'].items()}
m=copy.deepcopy(combined);c=m['modules']['DebugEpochFormal']['cells'][inputs['eq']]
for p in ['A','B']:c['connections'][p]=c['connections'][p][:1];c['parameters'][p+'_WIDTH']=format(1,'032b')
record['pilot']=job('compose-bit0',m,compose=True);save(out/'result.json',record)

