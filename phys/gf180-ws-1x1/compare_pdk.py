"""Read-only T43 library/view comparison; never installs or switches a PDK."""
import argparse,difflib,hashlib,json,pathlib,re,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from tools.timing.usb_boundary import groups

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bodies(text):return {name:hashlib.sha256(body.encode()).hexdigest() for name,body in groups(text,'cell')}
def normalized(text):
 # Preserve token boundaries and quoted strings while ignoring comments/spacing.
 return tuple(m[0] for m in re.finditer(r'"(?:\\.|[^"\\])*"|/\*.*?\*/|[A-Za-z_][A-Za-z_0-9]*|[0-9]+(?:\.[0-9]+)?|[^\s]',text,re.S) if not m[0].startswith('/*'))

def check_corners(old,new):
 if not old or not new:raise ValueError('missing standard-cell inputs')
 if old.keys()-new.keys():raise ValueError('candidate missing baseline corners: '+str(sorted(old.keys()-new.keys())))

def missing_used(used,definitions):
 return sorted(used-definitions.keys())
def compare(old,new):
 return dict(added=sorted(new.keys()-old.keys()),removed=sorted(old.keys()-new.keys()),
  changed=sorted(n for n in old.keys()&new.keys() if old[n]!=new[n]),unchanged=sum(old[n]==new[n] for n in old.keys()&new.keys()))

def main():
 start=time.monotonic();p=argparse.ArgumentParser()
 p.add_argument('--old',required=True);p.add_argument('--new',required=True)
 p.add_argument('--mapped',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 out=(ROOT/a.output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
 old=(ROOT/a.old).resolve();new=(ROOT/a.new).resolve()
 for path in (old,new):path.relative_to(ROOT/'build')
 scl='gf180mcu_fd_sc_mcu7t5v0';roots=[x/'gf180mcuD/libs.ref'/scl for x in (old,new)]
 libs=[{x.name:x for x in (r/'lib').glob('*.lib')} for r in roots]
 check_corners(*libs)
 hashes={};corners={};used={c['type'] for m in json.loads((ROOT/a.mapped).read_text())['modules'].values() for c in m.get('cells',{}).values() if c['type'].startswith(scl+'__')}
 assert used,'missing production cell inventory'
 for name in sorted(libs[0].keys()&libs[1].keys()):
  left,right=(d[name] for d in libs);hashes[str(left.relative_to(ROOT))]=sha(left);hashes[str(right.relative_to(ROOT))]=sha(right)
  lt,rt=left.read_text(),right.read_text();lc,rc=bodies(lt),bodies(rt);entry=compare(lc,rc)
  entry.update(old_sha256=sha(left),new_sha256=sha(right),missing_used=missing_used(used,rc))
  entry['identical_liberty_tokens_excluding_comments']=normalized(lt)==normalized(rt)
  corners[name]=entry
 lefs=[r/'lef'/(scl+'.lef') for r in roots]
 def macros(path):
  text=path.read_text();result={}
  for match in re.finditer(r'^MACRO\s+(\S+)',text,re.M):
   name=match[1];end=re.search(r'^END\s+'+re.escape(name)+r'\s*$',text[match.end():],re.M)
   assert end,name;body=text[match.start():match.end()+end.end()];result[name]=hashlib.sha256(body.encode()).hexdigest()
  assert result;return result
 lef_macros=list(map(macros,lefs));lef=compare(*lef_macros);lef.update(old_sha256=sha(lefs[0]),new_sha256=sha(lefs[1]),missing_used=missing_used(used,lef_macros[1]))
 for path in lefs:hashes[str(path.relative_to(ROOT))]=sha(path)
 lockpath=ROOT/'hw/vendor/gf180_sram/gf180_sram.lock.json';lock=json.loads(lockpath.read_text());sram=[]
 for name,expected in lock['files'].items():
  if not name.startswith('cells/') or '/specs/' in name or pathlib.Path(name).suffix not in ('.lib','.lef','.gds','.v','.spice'):continue
  pinned=ROOT/'build/vendor/gf180_sram'/name;assert sha(pinned)==expected,name
  matches=list((new/'gf180mcuD/libs.ref/gf180mcu_ocd_ip_sram').rglob(pinned.name))
  assert len(matches)<=1,name
  entry=dict(pinned=name,old_sha256=expected,new_path=None,new_sha256=None,status='not_shipped')
  if matches:
   candidate=matches[0];digest=sha(candidate);entry.update(new_path=str(candidate.relative_to(new)),new_sha256=digest,status='identical' if digest==expected else 'different')
   hashes[str(candidate.relative_to(ROOT))]=digest
   if digest!=expected and pinned.suffix!='.gds':
    diff=''.join(difflib.unified_diff(pinned.read_text().splitlines(True),candidate.read_text().splitlines(True),fromfile=name,tofile=entry['new_path']))
    (out/(pinned.name+'.diff')).write_text(diff)
  sram.append(entry)
 missing=any(c['missing_used'] for c in corners.values()) or bool(lef['missing_used'])
 result=dict(status='stop_missing_used_cell' if missing else 'compared_not_adopted',seconds=time.monotonic()-start,
  command=sys.argv,source_sha256=sha(pathlib.Path(__file__)),helper_sha256=sha(ROOT/'tools/timing/usb_boundary.py'),input_sha256=hashes,
  production_netlist_sha256=sha(ROOT/a.mapped),sram_lock_sha256=sha(lockpath),used_cells=sorted(used),
  corners_added=sorted(libs[1].keys()-libs[0].keys()),corners_removed=sorted(libs[0].keys()-libs[1].keys()),corners=corners,lef=lef,sram=sram,
  sram_switch_approval_required=any(x['status']!='identical' for x in sram),
  scope='Byte/cell inventory comparison only; no timing, electrical or physical equivalence claim; active PDK and pinned SRAM untouched')
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(dict(status=result['status'],corners=len(corners),cell_changed={n:len(v['changed']) for n,v in corners.items()},lef_changed=len(lef['changed']),sram={s:sum(x['status']==s for x in sram) for s in ('identical','different','not_shipped')})))
 if missing:raise SystemExit(1)
if __name__=='__main__':main()
