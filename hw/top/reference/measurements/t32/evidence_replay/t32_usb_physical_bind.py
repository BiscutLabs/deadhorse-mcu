"""Authenticate historical physical evidence after unrelated tool-lock additions.

No STA/placement rerun; never claim the historical tool binaries were rebuilt
identically. The original 475 non-lock sealed inputs and timing results remain.
"""
from pathlib import Path
import copy,hashlib,json,subprocess,sys
ROOT=Path.cwd();sys.path.insert(0,str(ROOT/'hw/ip/usb'))
from physical_evidence import collect
out=ROOT/'build/t32/usb-physical-binding03';out.mkdir(parents=True,exist_ok=False)
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
origin=ROOT/'build/plan03/usb-closure/physical-hold01-receipt02.json'
seal=json.loads(origin.read_text());git_bytes=subprocess.check_output(['git','show','HEAD:tools/env/lock.json'])
# The sealed checkout was CRLF. Reconstruct only that checkout representation,
# then demand the exact original hash before parsing or accepting anything.
old_bytes=git_bytes.replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')
assert hashlib.sha256(old_bytes).hexdigest()==seal['file_sha256']['tools/env/lock.json']
old=json.loads(old_bytes);new=json.loads((ROOT/'tools/env/lock.json').read_text())
expected=copy.deepcopy(old)
key='apt_packages'
assert key in expected
expected[key]+=['automake','libtool','pkg-config']
expected['versions']['openocd']='0.12.0'
new_archives=[x for x in new['sources'] if x['name'] in ('openocd.tar.gz','jimtcl.tar.gz')]
assert len(new_archives)==2
assert {x['name']:x['commit'] for x in new_archives}=={
    'openocd.tar.gz':'9ea7f3d647c8ecf6b0f1424002dfc3f4504a162c',
    'jimtcl.tar.gz':'a77ef1a6218fad4c928ddbdc03c1aedc41007e70'}
assert {x['name']:x['sha256'] for x in new_archives}=={
    'openocd.tar.gz':'704995583c5132bfeefd341585d6fc797940cd9c619c83c4971757720829db8a',
    'jimtcl.tar.gz':'fd111331a08ef7bad4eaa6e20f8c122977b5a26aeeac29873e0b19bb719048f3'}
expected['sources']+=new_archives
expected['openocd_configure']=['--prefix=/opt/openocd','--enable-remote-bitbang',
    '--enable-internal-jimtcl','--disable-internal-libjaylink','--disable-doxygen-html','--disable-doxygen-pdf']
assert new==expected,'Existing tool/archive/config changed'
for name,h in seal['file_sha256'].items():
    if name!='tools/env/lock.json':assert digest(Path(name.replace('/work/',str(ROOT)+'/')))==h,name
(out/'original-lock.json').write_bytes(old_bytes)
(out/'rebinder.py').write_bytes(Path(__file__).read_bytes())
derived=copy.deepcopy(seal)
derived['file_sha256']['tools/env/lock.json']=digest(ROOT/'tools/env/lock.json')
derived['evidence_reuse']=dict(original_seal=str(origin),original_seal_sha256=digest(origin),
    original_lock=str(out/'original-lock.json'),original_lock_sha256=digest(out/'original-lock.json'),
    original_lock_reconstruction='HEAD git blob with LF-to-CRLF checkout conversion; exact historical sealed SHA-256 required',
    rebinder_sha256=digest(Path(__file__)),unchanged_nonlock_inputs=len(seal['file_sha256'])-1,
    qualification='All physical commands and measurements are historical and reused, not rerun. New lock hash binds compatibility only. No claim of identical rebuilt binaries.',
    lock_change='Only OpenOCD/Jim archives, OpenOCD version/configure flags and automake/libtool/pkg-config; every pre-existing entry identical')
derived_path=out/'derived-seal.json';derived_path.write_text(json.dumps(derived,indent=2)+'\n')
manifest=json.loads((ROOT/'build/plan03/usb-closure/physical-manifest03.json').read_text())
manifest['seal']=str(derived_path)
manifest_path=out/'physical-manifest.json';manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
r=collect(manifest_path,ROOT/'build/t32/usb-rebind02/lookahead/emit/usb',out/'audit')
assert r['status']=='pass'
accept=dict(schema=1,physical=str(manifest_path),
    sampling='build/t32/usb-acceptance-inputs01/sampling-manifest.json',
    packet='build/t32/usb-acceptance-inputs01/packet-manifest.json')
(out/'acceptance-manifest.json').write_text(json.dumps(accept,indent=2)+'\n')
print('PASS strict physical collector; historical timing reused, no STA rerun',flush=True)
