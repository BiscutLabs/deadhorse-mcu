from pathlib import Path
import json,copy,hashlib,subprocess,time,sys,concurrent.futures,re
ROOT=Path.cwd();sys.path.insert(0,str(ROOT));from tools.formal import validate_job
base=ROOT/'build/t32/epoch-fifo02';out=ROOT/'build/t32/epoch-fifo-fault01';out.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
(out/'runner.py').write_bytes(Path(__file__).read_bytes())
def run(name):
 src=base/name/'model.json';r=json.loads((base/name/'result.json').read_text());assert r['status']=='PASS' and sha(src)==r['model_sha256']
 model=json.loads(src.read_text());m=model['modules']['DebugEpochFormal'];outbit=m['ports']['out']['bits'][0]
 matches=[(n,c) for n,c in m['cells'].items() if outbit in c['connections'].get('Q',[])]
 assert len(matches)==1;n,c=matches[0];assert c['type']=='$aldff';index=c['connections']['Q'].index(outbit)
 d=c['connections']['D'][index];new=max(b for cc in m['cells'].values() for bs in cc['connections'].values() for b in bs if isinstance(b,int))+1
 c['connections']['D'][index]=new
 m['cells']['fault_invert_head_d']=dict(hide_name=0,type='$not',parameters={'A_SIGNED':format(0,'032b'),'A_WIDTH':format(1,'032b'),'Y_WIDTH':format(1,'032b')},attributes={},port_directions={'A':'input','Y':'output'},connections={'A':[d],'Y':[new]})
 folder=out/name;folder.mkdir();(folder/'model.json').write_text(json.dumps(model)+'\n')
 cfg=folder/'job.sby';cfg.write_text('\n'.join(['[options]','mode bmc','depth 96','timeout 120','multiclock on','[engines]','smtbmc yices','[script]','read_json model.json','hierarchy -top DebugEpochFormal',"fminit -seq writeReset_n 0,'z",'clk2fflogic','chformal -lower','select -assert-count 4 t:$assert','select -assert-count 1 t:$assume','[files]',str(folder/'model.json')])+'\n')
 command=['sby','-d',str(folder/'job'),str(cfg)];t=time.monotonic()
 with(folder/'run.log').open('w') as log:code=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=180).returncode
 status=(folder/'job/status').read_text().split()[0]
 validate_job(folder/'job','negative',code,status)
 failed=sorted(set(re.findall(r'Assert failed in DebugEpochFormal: (\S+)',(folder/'job/logfile.txt').read_text())))
 assert failed==[name+'_oracle.assert__chisel3_builtin_2'],failed
 row=dict(status='fault_rejected',command=command,seconds=time.monotonic()-t,failed=failed,actual_mutation=dict(cell=n,port='D',bit=index,before=d,after=new),source_sha256=sha(src),model_sha256=sha(folder/'model.json'))
 (folder/'result.json').write_text(json.dumps(row,indent=2)+'\n');print(name,row['status'],flush=True);return row
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(run,['requests','responses']))
(out/'result.json').write_text(json.dumps(dict(status='pass',jobs=rows),indent=2)+'\n')
