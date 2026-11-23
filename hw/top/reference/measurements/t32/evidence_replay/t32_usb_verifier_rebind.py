"""Rebind historical USB evidence only over three reviewed verifier-only deltas.
No RTL, models, measured values, collector policy or original receipt is changed.
"""
from pathlib import Path
import copy,hashlib,json,shutil,subprocess,sys,time
ROOT=Path.cwd();sys.path.insert(0,str(ROOT/'hw/ip/usb'));sys.path.insert(0,str(ROOT))
from physical_evidence import collect as physical
from evidence import collect as packet,sampling_evidence
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def local(p):return ROOT/str(p).removeprefix('/work/')
def read(p):return json.loads(Path(p).read_text())
def write(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')
def validate(d):
 for p,h in d.items():assert sha(local(p))==h,p
out=ROOT/'build/t32/usb-verifier-rebind03';out.mkdir(exist_ok=False)
shutil.copyfile(__file__,out/'runner.py')
old=ROOT/'build/t32/usb-boundary-refresh03'
allowed={'hw/ip/i2c_host/formal/check.py','hw/ip/i2c_host/formal/deferred.py','hw/ip/i2c_host/test_formal_deferrals.py'}
result=dict(status='running',runner_sha256=sha(__file__),qualification='Historical timing/area reuse under exact verifier-only source delta; no fresh STA, area, placement or solver run.')
try:
 old_source=old/'bus-source-qualified01/result.json';bound=read(old_source)
 replay_path=ROOT/'build/t32/replay02/result.json';replay=read(replay_path)
 assert bound['source_sha256']==replay['production_source_sha256']
 differences={p:dict(original=h,current=sha(local(p))) for p,h in bound['source_sha256'].items() if sha(local(p))!=h}
 assert set(differences)==allowed,differences
 # Authenticate old versions against immutable Git objects, including recorded line endings.
 for p,d in differences.items():
  raw=subprocess.check_output(['git','show','9b80375:'+p])
  options=[raw,raw.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')]
  if p=='hw/ip/i2c_host/formal/check.py':
   # Historical tracked text had two LF-only timeout-guard lines amid CRLF.
   options.append(b''.join(line if i in (96,97) else line.replace(b'\n',b'\r\n') for i,line in enumerate(raw.splitlines(keepends=True),1)))
  matches=[v for v in options if hashlib.sha256(v).hexdigest()==d['original']]
  assert matches,p
  archive=out/'original-verifiers'/p;archive.parent.mkdir(parents=True,exist_ok=True);archive.write_bytes(matches[0])
  d['archived_original']=str(archive);d['current_is_python_verifier_only']=True
 for key in ('hdl_sha256','artifact_sha256','library_sha256'):validate(bound[key])
 for key in ('source_sha256','input_sha256'):
  if key in replay:validate(replay[key])
 for p,h in replay['artifact_sha256'].items():assert sha(replay_path.parent/p)==h,p
 current={p:sha(local(p)) for p in bound['source_sha256']}
 metadata=dict(original_source=str(old_source),original_source_sha256=sha(old_source),
  original_replay=str(replay_path),original_replay_sha256=sha(replay_path),
  unchanged_source_count=len(current)-3,verifier_only_deltas=differences,
  qualification=result['qualification'],runner_sha256=sha(__file__))
 # Derived replay receipt retains old command timing and numerical results explicitly as historical.
 derived=copy.deepcopy(replay);derived['production_source_sha256']=current;derived['verifier_only_rebinding']=metadata
 write(out/'historical-replay-binding.json',derived)
 bound['source_sha256']=current;bound['verifier_only_rebinding']=metadata
 binding=out/'bus-source-qualified01/result.json';write(binding,bound)
 # Copy every routed fixture byte unchanged, then derive only composition binding metadata.
 bus=out/'bus-physical01';shutil.copytree(old/'bus-physical01',bus)
 copied={str(p.relative_to(bus)):sha(p) for p in bus.rglob('*') if p.is_file()}
 assert all(sha(old/'bus-physical01'/p)==h for p,h in copied.items())
 composition=read(bus/'composition.json');validate(composition['input_sha256'])
 key=[p for p in composition['input_sha256'] if local(p)==old_source];assert len(key)==1
 del composition['input_sha256'][key[0]];composition['input_sha256'][str(binding)]=sha(binding)
 composition['verifier_only_rebinding']=dict(metadata,original_composition_sha256=sha(old/'bus-physical01/composition.json'))
 write(bus/'composition.json',composition)
 # No numerical hold row or original artifact hash changes.
 shutil.copytree(old/'bus-hold01',out/'bus-hold01')
 copied_hold={str(p.relative_to(out/'bus-hold01')):sha(p) for p in (out/'bus-hold01').rglob('*') if p.is_file()}
 assert all(sha(old/'bus-hold01'/p)==h for p,h in copied_hold.items())
 old_hold=old/'bus-hold01/result.json';hold=read(old_hold);validate(hold['artifact_sha256'])
 assert hold['binding_sha256']==sha(old_source)
 hold['binding_sha256']=sha(binding);hold['verifier_only_rebinding']=dict(metadata,original_hold_sha256=sha(old_hold))
 write(out/'bus-hold01/result.json',hold)
 manifest=read(old/'physical-manifest.json');manifest.update(source=str(binding),hold=str(out/'bus-hold01/result.json'),bus=str(bus))
 write(out/'physical-manifest.json',manifest)
 acceptance=read(old/'acceptance-manifest.json');acceptance['physical']=str(out/'physical-manifest.json');write(out/'acceptance-manifest.json',acceptance)
 result.update(rebinding=metadata,copied_fixture_sha256=copied,copied_hold_sha256=copied_hold)
 print('PASS exact verifier-only binding; starting unchanged collectors',flush=True)
 # All three domains preflight under the exact same strict production collectors.
 for top,folder in [('UsbControl','control'),('UsbEngine','engine'),('Usb','usb')]:
  src=ROOT/'build/t32/usb-rebind02/lookahead/emit'/folder
  sources=sorted(src.glob('*.sv'))+sorted(src.glob('*.v'));assert sources
  audit=sampling_evidence(local(acceptance['sampling']),top,sources)
  write(out/('sampling-'+top+'.json'),audit);assert audit['status']=='pass'
  print('PASS sampling '+top,flush=True)
 audit=packet(local(acceptance['packet']),out/'packet-audit');assert audit['status']=='pass'
 print('PASS packet',flush=True)
 audit=physical(out/'physical-manifest.json',ROOT/'build/t32/usb-rebind02/lookahead/emit/usb',out/'physical-audit');assert audit['status']=='pass'
 print('PASS physical',flush=True)
 validate(current)
 result['status']='pass'
except Exception as e:
 result.update(status='failed',error=repr(e));raise
finally:
 result['artifact_sha256']={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file() and p!=out/'result.json'}
 write(out/'result.json',result)
