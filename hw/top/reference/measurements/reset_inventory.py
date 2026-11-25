"""Count reset endpoints in a production Yosys hierarchy, before technology mapping.

Wire/port aliases and one-bit inversion normalize to one control identity.
Combinationally equivalent but separately synthesized expressions stay separate.
Count unique sequential Q bits, not a sum of overlapping source cones. RAM,
macro internals and latches are outside the explicit-flop count. This is a
structural inventory, not CDC/RDC, functional, or physical acceptance.
"""
from pathlib import Path
import argparse,json,hashlib,collections,subprocess,time,sys,re
ROOT=Path(__file__).resolve().parents[4]
parser=argparse.ArgumentParser(description=__doc__)
inputs=parser.add_mutually_exclusive_group(required=True)
inputs.add_argument('--hier',type=Path)
inputs.add_argument('--emit',type=Path)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
BASE=args.output.resolve()
BASE.relative_to(ROOT/'build')
BASE.mkdir(parents=True,exist_ok=True)
if args.emit:
 emit=args.emit.resolve();emit.relative_to(ROOT/'build')
 cfg=json.loads((ROOT/'phys/gf180-ws-1x1/block-timing.json').read_text(encoding='utf-8'))
 lib=ROOT/f'build/riscay-mcu/.tools/physical/pdk/{cfg["library"]}__{cfg["corner"]}.lib'
 assert hashlib.sha256(lib.read_bytes()).hexdigest()==cfg['sha256']
 lock=json.loads((ROOT/'hw/vendor/gf180_sram/gf180_sram.lock.json').read_text(encoding='utf-8'))
 libs=[lib]
 for cell in (lock['macro'],lock['retained_macro']):
  relative=f'cells/{cell}/{cell}__{cfg["corner"]}.lib'
  view=ROOT/'build/vendor/gf180_sram'/relative
  assert hashlib.sha256(view.read_bytes()).hexdigest()==lock['files'][relative]
  libs.append(view)
 definitions={
  'LfRcMacro':{'vdd':('inout',1),'vss':('inout',1),'enable':('input',1),'trim':('input',6),'test':('input',1),'clock':('output',1),'ready':('output',1)},
  'PorBrownoutMacro':{'vdd':('inout',1),'vss':('inout',1),'threshold':('input',2),'test':('input',1),'supplyReset_n':('output',1),'powerOn_n':('output',1),'brownout':('output',1)}}
 analog={'modules':{}}
 for module,ports in definitions.items():
  m=dict(attributes={'blackbox':'1'},ports={},cells={},netnames={});bit=2
  for pin,(direction,width) in ports.items():
   bits=list(range(bit,bit+width));bit+=width
   m['ports'][pin]=dict(direction=direction,bits=bits)
   m['netnames'][pin]=dict(hide_name=0,bits=bits,attributes={})
  analog['modules'][module]=m
 (BASE/'analog-interfaces.json').write_text(json.dumps(analog),encoding='utf-8')
 files=[emit/line.strip() for line in (emit/'filelist.f').read_text(encoding='utf-8').splitlines() if line.strip()]
 src=BASE/'hier.json'
 script=BASE/'import.ys'
 lines=[f'read_liberty -lib {p}' for p in libs]+[f'read_json {BASE}/analog-interfaces.json',
  'read_slang --keep-hierarchy -DSYNTHESIS -DENABLE_INITIAL_MEM_ --top DeadhorseSoc '+' '.join(map(str,files)),
  'hierarchy -check -top DeadhorseSoc','proc','chformal -remove','memory_collect',f'write_json {src}']
 script.write_text('\n'.join(lines)+'\n',encoding='utf-8')
 images=[]
 for source in files:
  for filename in re.findall(r'\$readmem[hb]\s*\(\s*"([^"\n]+)"',source.read_text(encoding='utf-8')):
   image=(ROOT/filename).resolve();image.relative_to(ROOT/'build');images.append(image)
 dependencies=files+libs+images+[script,Path(__file__),emit/'filelist.f',BASE/'analog-interfaces.json',
  ROOT/'phys/gf180-ws-1x1/block-timing.json',ROOT/'hw/vendor/gf180_sram/gf180_sram.lock.json']
 def seal():return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in dependencies}
 before=seal()
 started=time.monotonic()
 with (BASE/'import.log').open('w',encoding='utf-8') as log:
  rc=subprocess.run(['yosys','-Q','-T','-s',str(script)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT).returncode
 receipt={'command':f'yosys -Q -T -s {script.relative_to(ROOT)}','exit_code':rc,'wall_seconds':time.monotonic()-started,
  'sha256':before}
 (BASE/'import-receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
 if rc:raise SystemExit(rc)
 assert seal()==before, 'Import dependencies changed during measurement'
else:
 src=args.hier.resolve();src.relative_to(ROOT/'build')
t0=time.monotonic();mods=json.loads(src.read_text(encoding='utf-8'))['modules']
parent={}; aliases=collections.defaultdict(set); cells=[]; releases=[]; boxes=[]
def find(x):
 parent.setdefault(x,x)
 if parent[x]!=x:parent[x]=find(parent[x])
 return parent[x]
def union(a,b):
 a,b=find(a),find(b)
 if a!=b:parent[b]=a
def walk(typ,path,ports=None):
 m=mods[typ]
 def bit(b):return ('const',b) if isinstance(b,str) else (path,b)
 if ports:
  for p,v in m['ports'].items():
   for a,b in zip(v['bits'],ports.get(p,[])):union(bit(a),b)
 for n,v in m.get('netnames',{}).items():
  if not v.get('hide_name'):
   for i,b in enumerate(v['bits']):aliases[bit(b)].add(path+'.'+n+(f'[{i}]' if len(v['bits'])>1 else ''))
 if re.fullmatch(r'ResetRelease(?:_[0-9]+)?',typ.split('$')[0]):
  releases.append({'instance':path,'clk':bit(m['ports']['clk']['bits'][0]),'source':bit(m['ports']['reset_n']['bits'][0]),'output':bit(m['ports']['released']['bits'][0])})
 for n,c in m.get('cells',{}).items():
  p=path+'.'+n; con={k:[bit(b) for b in bs] for k,bs in c['connections'].items()};ct=c['type']
  if ct in mods and not int(mods[ct].get('attributes',{}).get('blackbox','0'),2):walk(ct,p,con)
  else:
   cc={'instance':p,'type':ct,'connections':con,'directions':c.get('port_directions',{}),'parameters':c.get('parameters',{}),'src':c.get('attributes',{}).get('src','')}
   cells.append(cc)
   if ct in mods:boxes.append(cc)
   if ct=='$buf':
    for a,b in zip(con['A'],con['Y']):union(a,b)
walk('DeadhorseSoc','DeadhorseSoc')
a2=collections.defaultdict(set)
for b,n in aliases.items():a2[find(b)].update(n)
aliases=a2
for c in cells:c['connections']={p:[find(b) for b in v] for p,v in c['connections'].items()}
for r in releases:
 for p in ('clk','source','output'):r[p]=find(r[p])
def name(b):
 b=find(b)
 if b[0]=='const':return b[1]
 ns=aliases.get(b,())
 return min(ns,key=lambda n:('_GEN' in n or '._' in n,n.count('.'),len(n),n)) if ns else str(b)
# Normalize wire buffers and single-bit logical inversion only. Keep a polarity
# bit so source names do not hide asserted-high versus asserted-low controls.
inv={}; drivers=collections.defaultdict(list)
for c in cells:
 con=c['connections']
 if c['type'] in ('$not','$logic_not') and len(con['A'])==len(con['Y'])==1:inv[con['Y'][0]]=con['A'][0]
 for p,bs in con.items():
  if c['directions'].get(p)=='output':
   for b in bs:drivers[b].append(c)
def canonical(b):
 seen=set();pol=0
 while b in inv and b not in seen:seen.add(b);b=inv[b];pol^=1
 return b,pol
seq=[]; latches=[]; memories=[]; groups=collections.defaultdict(list)
for c in cells:
 typ=c['type'];con=c['connections']
 if typ.startswith('$') and ('ff' in typ.lower() or 'latch' in typ.lower()) and typ not in (
  '$dff','$dffe','$adff','$adffe','$aldff','$aldffe','$sdff','$sdffe','$sdffce','$dlatch','$adlatch'):
  raise ValueError('Unclassified sequential cell: '+c['instance']+' '+typ)
 if typ=='$mem_v2':memories.append(c);continue
 if typ in ('$dlatch','$adlatch'):latches.append(c);continue
 if typ in ('$dff','$dffe','$adff','$adffe','$aldff','$aldffe','$sdff','$sdffe','$sdffce'):
  seq.append(c)
  for rp in ('ALOAD','ARST','SRST'):
   if rp in con:
    assert len(con[rp])==1
    b,pol=canonical(con[rp][0]);groups[b].append((c,rp,pol))
# Every output cell bit is counted once even when reset-source cones overlap.
all_q={b for c in seq for b in c['connections']['Q']}
reset_q={b for rows in groups.values() for c,_,_ in rows for b in c['connections']['Q']}
rr_q={b for c in seq if any(c['instance'].startswith(r['instance']+'.') for r in releases) for b in c['connections']['Q']}
# Source cones stop at state or macro/primary input; no behavioral simplification.
def leaves(b,seen=None):
 seen=set() if seen is None else seen
 if b in seen:return {name(b)+' (cycle)'}
 if b[0]=='const':return set()
 ds=[c for c in drivers[b] if c['type']!='$buf']
 if not ds:return {name(b)}
 ans=set()
 for c in ds:
  if c in seq or c in latches or c in boxes or c['type']=='$mem_v2':ans.add(name(b));continue
  for p,bs in c['connections'].items():
   if c['directions'].get(p)=='input':
    for bb in bs:ans.update(leaves(bb,seen|{b}))
 return ans
rows=[]
for i,(b,rs) in enumerate(sorted(groups.items(),key=lambda x:name(x[0])),1):
 qs={q for c,_,_ in rs for q in c['connections']['Q']}
 row={'id':f'R{i:03}','net':name(b),'aliases':sorted(aliases.get(b,())), 'sources':sorted(leaves(b)), 'flop_bits':len(qs),'clocks':sorted({name(c['connections']['CLK'][0]) for c,_,_ in rs}), 'consumers':[{'instance':c['instance'],'type':c['type'],'pin':p,'inversion':pol,'reset_polarity_parameter':c['parameters'].get(p+'_POLARITY'),'width':len(c['connections']['Q']),'q':[name(q) for q in c['connections']['Q']]} for c,p,pol in rs]}
 rows.append(row)
rr=[]
for r in sorted(releases,key=lambda r:r['instance']):
 rb,_=canonical(r['output']);sb,_=canonical(r['source'])
 rr.append({'instance':r['instance'],'clock':name(r['clk']),'source':name(r['source']),'source_leaves':sorted(leaves(r['source'])),'released':name(r['output']),'source_reset_groups':[x['id'] for b,x in zip(sorted(groups,key=name),rows) if b==sb], 'direct_downstream_bits':sum(x['flop_bits'] for b,x in zip(sorted(groups,key=name),rows) if b==rb),'flop_bits':2})
summary={'release_instances':len(rr),'release_flop_bits':len(rr_q),'distinct_reset_control_nets_inversion_normalized':len(rows),'reset_controlled_flop_bits':len(reset_q),'all_explicit_flop_bits':len(all_q),'nonreset_flop_bits':len(all_q-reset_q),'latch_bits':sum(len(c['connections']['Q']) for c in latches),'inferred_memory_instances':len(memories),'blackbox_instances':len(boxes)}
result={'commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'hierarchy_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'command':' '.join(sys.argv),'hierarchy':str(src.relative_to(ROOT)),'summary':summary,'reset_groups':rows,'releases':rr,'blackboxes':[{'instance':c['instance'],'type':c['type']} for c in boxes],'latches':[{'instance':c['instance'],'width':len(c['connections']['Q'])} for c in latches]}
assert sum(row['flop_bits'] for row in rows)==len(reset_q), 'Reset controls overlap: do not double count'
assert len(rr_q)==2*len(rr), 'Unexpected ResetRelease implementation'
result['wall_seconds']=time.monotonic()-t0
(BASE/'reset-inventory.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2));print('wall_seconds',result['wall_seconds'])
lines=['| Instance (relative to DeadhorseSoc) | Clock net | Reset source | Released net | Release bits | Direct reset-controlled bits |','| --- | --- | --- | --- | ---: | ---: |']
for r in rr:lines.append('| '+ ' | '.join(str(r[k]).replace('DeadhorseSoc.','') for k in ('instance','clock','source','released','flop_bits','direct_downstream_bits'))+' |')
(BASE/'release-table.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
lines=['| ID | Reset control net (inversion normalized) | Clock net(s) | Unique flop bits | Consumer modules |','| --- | --- | --- | ---: | --- |']
for r in rows:
 cs=sorted({c['instance'].rsplit('.',1)[0].replace('DeadhorseSoc.','') for c in r['consumers']})
 lines.append('| '+ ' | '.join((r['id'],r['net'].replace('DeadhorseSoc.',''),', '.join(c.replace('DeadhorseSoc.','') for c in r['clocks']),str(r['flop_bits']),', '.join(cs)))+' |')
(BASE/'reset-table.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

