"""One mapped identity-buffer forest repair; no RTL/mapping/STA limits changed."""
from pathlib import Path
import copy,csv,hashlib,json,re,subprocess,sys,time
ROOT=Path.cwd();sys.path.insert(0,str(ROOT));from tools.timing.check import electrical_checks
base=ROOT/'build/t32/final-fast03/fast/faithful-floating-timing';out=ROOT/'build/t32/floating-buffer03';out.mkdir(exist_ok=False);shutil=None
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
receipt=dict(status='running',source_sha256={str(Path(__file__)):sha(__file__)},commands=[])
def run(cmd,label):
 t=time.monotonic()
 with (out/(label+'.log')).open('w') as f:c=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT).returncode
 receipt['commands'].append(dict(command=cmd,returncode=c,seconds=time.monotonic()-t));assert c==0,label
lib=ROOT/'build/riscay-mcu/.tools/physical/pdk/gf180mcu_fd_sc_mcu7t5v0__ss_125C_3v00.lib'
(out/'runner.py').write_bytes(Path(__file__).read_bytes())
try:
 (out/'canonical.ys').write_text(f'read_liberty -lib "{lib}"\nread_verilog "{base}/mapped.v"\nhierarchy -check -top DeadhorsePerfCore\nwrite_json "{out}/original.json"\n')
 run(['yosys','-Q','-T','-s',str(out/'canonical.ys')],'canonical')
 d=json.loads((out/'original.json').read_text());m=d['modules']['DeadhorsePerfCore'];root=m['netnames']['_04456_']['bits'][0]
 loads={}
 for n,c in m['cells'].items():
  for p,bits in c['connections'].items():
   if c['port_directions'][p]=='input':
    for i,b in enumerate(bits):loads.setdefault(b,[]).append((n,p,i))
 queue=[(root,0)];old={};targets=[]
 while queue:
  bit,depth=queue.pop()
  for n,p,i in loads.get(bit,[]):
   c=m['cells'][n]
   if re.fullmatch('gf180mcu_fd_sc_mcu7t5v0__buf_[1-4]',c['type']) and p=='I':
    assert n not in old;old[n]=depth+1;queue.append((c['connections']['Z'][0],depth+1))
   else:targets.append((n,p,i,depth))
 assert len(old)==21 and len(targets)==193 and max(old.values())==11
 assert all(p not in ('CLK','CLKN','RN','SETN','E','TE') for n,p,i,dep in targets)
 old_out={m['cells'][n]['connections']['Z'][0] for n in old}
 assert all(not old_out.intersection(p['bits']) for p in m['ports'].values())
 new=copy.deepcopy(m)
 for n in old:del new['cells'][n]
 original_bits=[b for c in m['cells'].values() for bits in c['connections'].values() for b in bits if isinstance(b,int)]
 original_bits.extend(b for row in list(m['ports'].values())+list(m['netnames'].values()) for b in row['bits'] if isinstance(b,int))
 next_bit=max(original_bits)+1
 inserted=[];pending=[(n,p,i) for n,p,i,dep in sorted(targets)];layers=0
 while len(pending)>8:
  following=[];layers+=1
  for k in range(0,len(pending),8):
   chunk=pending[k:k+8];name=f't32_data_buffer_{len(inserted):03d}';bit=next_bit;next_bit+=1
   new['cells'][name]=dict(hide_name=0,type='gf180mcu_fd_sc_mcu7t5v0__buf_4',parameters={},attributes={},port_directions={'I':'input','Z':'output'},connections={'I':[root],'Z':[bit]});inserted.append(name)
   for n,p,i in chunk:new['cells'][n]['connections'][p][i]=bit
   following.append((name,'I',0))
  pending=following
 for n,p,i in pending:new['cells'][n]['connections'][p][i]=root
 # Source aliases to identity-buffer outputs remain same logical signal.
 for a,row in new['netnames'].items():row['bits']=[root if b in old_out else b for b in row['bits']]
 def collapse(model,names):
  model=copy.deepcopy(model);parents={}
  for n in names:
   c=model['cells'][n];assert re.fullmatch('gf180mcu_fd_sc_mcu7t5v0__buf_[1-4]',c['type']);parents[c['connections']['Z'][0]]=c['connections']['I'][0]
  def resolve(b):
   seen=set()
   while b in parents:
    assert b not in seen,'buffer cycle';seen.add(b);b=parents[b]
   return b
  for n in names:del model['cells'][n]
  for c in model['cells'].values():c['connections']={p:[resolve(b) for b in bits] for p,bits in c['connections'].items()}
  for row in model['netnames'].values():row['bits']=[resolve(b) for b in row['bits']]
  return model
 write(out/'collapsed-original.json',collapse(m,old));write(out/'collapsed-candidate.json',collapse(new,inserted))
 assert collapse(m,old)==collapse(new,inserted),'inverse graph mismatch'
 fault=copy.deepcopy(new);n,p,i,_=targets[0];fault['cells'][n]['connections'][p][i]='0'
 assert collapse(m,old)!=collapse(fault,inserted),'wrong pin survived'
 fault=copy.deepcopy(new);fault['cells'][inserted[0]]['connections']['I']=fault['cells'][inserted[0]]['connections']['Z']
 try:collapse(fault,inserted);raise RuntimeError('cycle survived')
 except AssertionError:pass
 actual_loads={}
 for c in new['cells'].values():
  for p,bits in c['connections'].items():
   if c['port_directions'][p]=='input':
    for b in bits:actual_loads[b]=actual_loads.get(b,0)+1
 fanouts=[actual_loads[new['cells'][n]['connections']['Z'][0]] for n in inserted]
 assert max(fanouts)<=8 and actual_loads[root]<=8
 # Original all unrelated cell, clock/reset, port and alias functions match exactly.
 d['modules']['DeadhorsePerfCore']=new;write(out/'candidate.json',d)
 write(out/'transform.json',dict(status='pass',original=str(base/'mapped.v'),original_sha256=sha(base/'mapped.v'),old_buffers=old,inserted=inserted,loads=targets,new_depth=layers,max_fanout=max(fanouts),root_fanout=actual_loads[root],wrong_pin_rejected=True,cycle_rejected=True,inverse='exact entire module equality after removing only identity buffers and resolving their aliases'))
 (out/'export.ys').write_text(f'read_json "{out}/candidate.json"\nhierarchy -check -top DeadhorsePerfCore\ncheck -assert\nstat -liberty "{lib}"\nwrite_verilog -noattr -noexpr "{out}/mapped.v"\n')
 run(['yosys','-Q','-T','-s',str(out/'export.ys')],'export')
 tcl=(base/'timing.tcl').read_text().replace(str(base),str(out));(out/'timing.tcl').write_text(tcl)
 run(['sta','-no_init','-exit',str(out/'timing.tcl')],'sta')
 rows=list(csv.DictReader((out/'paths.tsv').open(),delimiter='\t'));worst=max(rows,key=lambda r:float(r['delay_ns']));electrical=electrical_checks((out/'sta.log').read_text())
 gates=list(csv.DictReader((out/'gate_checks.tsv').open(),delimiter='\t'));assert gates
 area={}
 text=lib.read_text()
 for n in set([m['cells'][n]['type'] for n in old]+['gf180mcu_fd_sc_mcu7t5v0__buf_4']):
  match=re.search(r'cell\s*\(\s*"?'+re.escape(n)+r'"?\s*\)\s*\{(.*?)(?=\n\s*cell\s*\(|\Z)',text,re.S);assert match,n
  area[n]=float(re.search(r'\barea\s*:\s*([0-9.]+)',match[1])[1])
 delta=sum(area[new['cells'][n]['type']] for n in inserted)-sum(area[m['cells'][n]['type']] for n in old)
 receipt.update(status='pass' if float(worst['delay_ns'])<=66.66666666666667 and electrical['max_capacitance_and_slew_violations']==0 and min(float(g['slack_ns']) for g in gates)>=0 else 'fail',worst=worst,budget_ns=66.66666666666667,electrical=electrical,gate_min_slack_ns=min(float(g['slack_ns']) for g in gates),area_delta_um2=delta,old_buffer_count=len(old),new_buffer_count=len(inserted),original_max_depth=11,new_max_depth=layers,qualification='Mapped diagnostic only, no RTL change; unchanged original STA script except netlist/report paths. All function/pin aliases equal after identity collapse. No physical placement claim.')
except Exception as e:receipt.update(status='error',error=repr(e));raise
finally:
 receipt['artifact_sha256']={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='result.json'};write(out/'result.json',receipt)
 print(receipt['status'],flush=True)
