"""Exact partition of original DBG_EPOCH_DATA, no model width reduction."""
from pathlib import Path
import copy,concurrent.futures,hashlib,json,subprocess,sys,time
ROOT=Path.cwd();sys.path.insert(0,str(ROOT));from tools.formal import validate_job
width=int(sys.argv[1]) if len(sys.argv)>1 else 8
assert width in (1,8)
base=ROOT/'build/t32/epoch-lanes02';out=ROOT/f'build/t32/epoch-data-lanes{width}-02';out.mkdir(parents=True,exist_ok=False)
raw=json.loads((base/'raw.json').read_text());inputs=json.loads((base/'inputs.json').read_text())
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert sha(base/'raw.json')==inputs['raw_sha256']
assert all(sha(p)==h for p,h in inputs['source_sha256'].items())
m=raw['modules']['DebugEpochFormal'];eq=inputs['eq'];original=m['cells'][eq]
assert original['type']=='$eq' and len(original['connections']['A'])==len(original['connections']['B'])==32
# Equality is used only in the observer, never the design or another property.
front=set(original['connections']['Y']);visited=set();terminals=set()
while front:
    new=set()
    for n,c in m['cells'].items():
        if n in visited or not any(front.intersection(bs) for p,bs in c['connections'].items() if c['port_directions'][p]=='input'):continue
        visited.add(n)
        if c['type']=='$check':terminals.add(n);continue
        assert c['type'] in ('$or','$logic_or','$not','$logic_not'),(n,c['type'])
        new.update(b for p,bs in c['connections'].items() if c['port_directions'][p]=='output' for b in bs)
    front=new
assert terminals=={'assert__chisel3_builtin_0'},terminals
(out/'runner.py').write_bytes(Path(__file__).read_bytes())
def job(start):
    case=out/f'bits{start}-{start+width-1}';case.mkdir();model=copy.deepcopy(raw)
    c=model['modules']['DebugEpochFormal']['cells'][eq]
    for p in ('A','B'):c['connections'][p]=c['connections'][p][start:start+width];c['parameters'][p+'_WIDTH']=format(width,'032b')
    (case/'model.json').write_text(json.dumps(model)+'\n')
    cfg=case/'job.sby';cfg.write_text('\n'.join(['[options]','mode prove','depth 96','timeout 120','multiclock on','[engines]',
        'abc pdr','aiger suprove','smtbmc yices','[script]','read_json model.json','hierarchy -top DebugEpochFormal',
        'clk2fflogic','chformal -lower','select -assert-count 16 t:$assert',
        'select -set data_property c:assert__chisel3_builtin_0','chformal -assert -remove t:$assert @data_property %d',
        'opt_clean -purge','select -assert-count 1 t:$assert','select -assert-count 1 t:$assume',
        '[files]',str(case/'model.json')])+'\n')
    command=['sby','-d',str(case/'job'),str(cfg)];t=time.monotonic()
    with(case/'run.log').open('w') as f:
        try:code=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,timeout=180).returncode
        except subprocess.TimeoutExpired:code=124
    status=(case/'job/status').read_text().split()[0] if (case/'job/status').exists() else 'ERROR'
    row=dict(bits=list(range(start,start+width)),command=command,returncode=code,status=status,seconds=time.monotonic()-t,
        model_sha256=sha(case/'model.json'),config_sha256=sha(cfg))
    if status=='PASS':validate_job(case/'job','proof',code,status)
    (case/'result.json').write_text(json.dumps(row,indent=2)+'\n');print(start,status,flush=True);return row
starts=list(range(0,32,width)) if width==8 else [0]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(job,starts))
r=dict(status='pass' if len(starts)*width==32 and all(j['status']=='PASS' for j in rows) else 'unresolved',jobs=rows,
    original_model_sha256=inputs['raw_sha256'],source_sha256=inputs['source_sha256'],eq=eq,observer_only_fanout=sorted(visited),
    qualification='Conjunction of bit slices exactly equals original guarded32-bit property. Entire production widths/clocks/resets retained; no new assumption.',
    complete=list(b for j in rows for b in j['bits'])==list(range(32)))
(out/'result.json').write_text(json.dumps(r,indent=2)+'\n');print(r['status'],flush=True)
