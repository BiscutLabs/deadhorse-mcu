"""Attribute passive T42 traces; verify every word against independent flash bytes."""
import argparse,bisect,csv,hashlib,json,pathlib,statistics,time

BASE=0x30000000
STAGES=('cpu_offer','cpu_take','offer_up','ask_up','permit_up','admit_up','source_req_up',
 'source_take','request_push','request_pop','target_req_up','target_take','ram_req_up',
 'ram_take','ram_reply','target_reply','response_push','response_pop','source_reply','cpu_reply','retire')
PAIRS=(('cpu_offer','ask_up'),('ask_up','permit_up'),('permit_up','source_take'),
 ('source_take','request_pop'),('request_pop','target_take'),('target_take','ram_take'),
 ('ram_take','ram_reply'),('ram_reply','target_reply'),('target_reply','response_pop'),
 ('response_pop','retire'),('cpu_offer','retire'))
def rows(path):
 with path.open() as f:
  return [{k:v if k=='event' else int(v) for k,v in r.items()} for r in csv.DictReader(f)]
def expected(path,slot):
 data=path.read_bytes();word=lambda n:int.from_bytes(data[n:n+4],'little')
 start=4096+slot*word(8);at=start+256+word(start+16)
 return data[at:at+word(start+28)]
def analyze(trace,image):
 assert len(image)%4==0 and image
 assert trace[0]['event']=='begin' and trace[-1]['event']=='end'
 assert sum(r['event']=='begin' for r in trace)==sum(r['event']=='end' for r in trace)==1
 assert all(a['tick']<=b['tick'] and a['aon_edges']<=b['aon_edges'] for a,b in zip(trace,trace[1:]))
 transactions=[];current=None
 for r in trace:
  lite=BASE<=r['address']<BASE+len(image)
  if r['event']=='cpu_offer' and lite:
   assert current is None,'overlapping CPU offers'
   current={}
  if current is not None:
   if r['event'] in STAGES:
    if r['event']=='retire' and not lite:continue
    assert r['event'] not in current,'duplicate transfer stage '+r['event']
    current[r['event']]=r
  if r['event']=='retire' and lite:
   assert current is not None,'unoffered or duplicate retirement'
   assert set(current)==set(STAGES),set(STAGES)-set(current)
   assert all(current[a]['tick']<=current[b]['tick'] for a,b in zip(STAGES,STAGES[1:]))
   offer=current['cpu_offer'];assert (offer['address'],offer['write'])==(r['address'],r['write'])
   n=len(transactions);count=len(image)//4
   assert n<2*count and r['address']==BASE+4*(n%count) and r['write']==int(n<count),'missing/reordered word'
   value=int.from_bytes(image[4*(n%count):4*(n%count)+4],'little')
   assert r['data']==value,'word differs from independent flash image'
   # Stage addresses are source-held labels, not downstream data evidence.
   assert all(current[s]['address']==r['address'] for s in STAGES[6:]),'stage attribution changed'
   transactions.append(current);current=None
 assert current is None and len(transactions)==len(image)//2,'incomplete copy/readback'
 # Grant withdrawal can overlap flash/CPU work after a retirement. Report it
 # separately; do not add it to end-to-end time a second time.
 falling=[r for r in trace if r['event']=='permit_down']
 falling_ticks=[r['tick'] for r in falling]
 asking_ticks=[r['tick'] for r in trace if r['event']=='ask_up']
 for t in transactions:
  at=bisect.bisect_right(falling_ticks,t['response_pop']['tick'])
  next_ask=bisect.bisect_right(asking_ticks,t['response_pop']['tick'])
  end=asking_ticks[next_ask] if next_ask<len(asking_ticks) else trace[-1]['tick']
  assert bisect.bisect_left(falling_ticks,end)-at==1,'missing/duplicate grant withdrawal before next ask'
  t['permit_down']=falling[at]
 def stats(values):return dict(min=min(values),mean=statistics.mean(values),max=max(values),sum=sum(values))
 result=dict(words_each_way=len(image)//4,measured_quanta=trace[-1]['tick']-trace[0]['tick'],
  measured_aon_edges=trace[-1]['aon_edges']-trace[0]['aon_edges'],
  estimated_ms=(trace[-1]['tick']-trace[0]['tick'])/96000,
  assumed_quantum_hz=96000000,assumed_aon_hz=32000,stages={},transactions=transactions)
 for write,label in ((1,'copy'),(0,'readback')):
  selected=[t for t in transactions if t['retire']['write']==write]
  result['stages'][label]={a+' -> '+b:{'measured_quanta':stats([t[b]['tick']-t[a]['tick'] for t in selected]),
   'measured_aon_edges':stats([t[b]['aon_edges']-t[a]['aon_edges'] for t in selected])} for a,b in PAIRS}
  result['stages'][label]['response_pop -> permit_down (overlaps following work)']={
   'measured_quanta':stats([t['permit_down']['tick']-t['response_pop']['tick'] for t in selected]),
   'measured_aon_edges':stats([t['permit_down']['aon_edges']-t['response_pop']['aon_edges'] for t in selected])}
  result[label+'_phase_quanta']=selected[-1]['retire']['tick']-selected[0]['cpu_offer']['tick']
 # Disjoint wall-time accounting; CPU/flash driver can overlap bus work, so
 # the residual is explicitly not a measurement of pure CPU execution time.
 bus=False;flash=bool(trace[0]['data']);last=trace[0]['tick'];totals=dict(lite_transaction=0,flash_selected_outside_lite_transaction=0,other_main_work=0)
 for r in trace:
  key='lite_transaction' if bus else 'flash_selected_outside_lite_transaction' if flash else 'other_main_work'
  totals[key]+=r['tick']-last;last=r['tick']
  if r['event']=='cpu_offer' and BASE<=r['address']<BASE+len(image):bus=True
  if r['event']=='retire' and BASE<=r['address']<BASE+len(image):bus=False
  if r['event']=='flash_on':flash=True
  if r['event']=='flash_off':flash=False
 assert not bus and sum(totals.values())==result['measured_quanta']
 result['disjoint_quanta']=totals
 result['retired_instructions']=sum(r['event'] in ('instruction','retire') for r in trace)
 return result
def main():
 start=time.monotonic()
 p=argparse.ArgumentParser();p.add_argument('--profile',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
 a.output.resolve().relative_to(pathlib.Path('build').resolve());a.output.mkdir(parents=True,exist_ok=False)
 receipt=json.loads((a.profile/'result.json').read_text());assert receipt['status'] in ('measured','measured_with_D104_exception')
 prepared=a.profile/'prepared/prepared.json'
 assert hashlib.sha256(prepared.read_bytes()).hexdigest()==receipt['artifact_sha256']['prepared/prepared.json']
 cases=json.loads(prepared.read_text())['cases'];results={};faults=[]
 for name in ('watcher-held','max-lite-held'):
  trace_path=a.profile/(name+'.csv');flash_path=a.profile/'prepared'/(name+'.flash')
  for path in (trace_path,flash_path):assert hashlib.sha256(path.read_bytes()).hexdigest()==receipt['artifact_sha256'][str(path.relative_to(a.profile))]
  trace=rows(trace_path);image=expected(flash_path,cases[name]['selected_slot']);result=analyze(trace,image)
  assert result['measured_quanta']==receipt['cases'][name]['lite_load_quanta']
  tx=result.pop('transactions');(a.output/(name+'-words.json')).write_text(json.dumps(tx,indent=2)+'\n')
  results[name]=result
  # Mutate observations, not RTL. These controls validate attribution/oracle
  # rejection only; they are not the future transport RTL negative controls.
  at=next(i for i,r in enumerate(trace) if r['event']=='retire' and r['address']==BASE)
  for fault in ('wrong-data','dropped-word','duplicate-word','missing-withdrawal','duplicate-withdrawal'):
   altered=[dict(r) for r in trace]
   if fault=='wrong-data':altered[at]['data']^=1
   elif fault=='dropped-word':del altered[at]
   elif fault=='duplicate-word':altered.insert(at,dict(altered[at]))
   else:
    withdraw=next(i for i,r in enumerate(altered) if r['event']=='permit_down')
    if fault=='missing-withdrawal':del altered[withdraw]
    else:altered.insert(withdraw,dict(altered[withdraw]))
   try:analyze(altered,image)
   except AssertionError:faults.append(name+':'+fault)
   else:raise AssertionError('negative control escaped: '+fault)
 result=dict(status='pass',seconds=time.monotonic()-start,profile_receipt_sha256=hashlib.sha256((a.profile/'result.json').read_bytes()).hexdigest(),
  analyzer_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),cases=results,negative_controls=faults,
  limitations='Internal stage labels follow one outstanding source word, not a concurrent-master oracle; clocks assumed; pure CPU compute versus peripheral polling not separated')
 (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS two complete copy/readback traces and ten corrupted-trace controls')
if __name__=='__main__':main()
