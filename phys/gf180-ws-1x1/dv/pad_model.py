"""Authenticated, zero-pull-only Verilator compatibility view; not physical IP."""
import hashlib,json,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def prepare(output):
 lock=ROOT/'phys/gf180-ws-1x1/pdk-lock.json'
 archive=ROOT/'build/t43/pdk-candidate/gf180mcu_fd_io.tar.zst'
 assert sha(archive)==json.loads(lock.read_text())['archives'][archive.name]['sha256']
 name='gf180mcuD/libs.ref/gf180mcu_fd_io/verilog/gf180mcu_fd_io.v'
 original=subprocess.check_output(['tar','--zstd','-xOf',str(archive),name])
 source=ROOT/'build/t43/pdk-candidate'/name;assert source.read_bytes()==original
 # Verilator lacks resistive-MOS primitives. All chip pad pulls are tied off;
 # replacement primitives are therefore always disabled. No strength claim.
 assert original.count(b'rnmos #1')==4
 output.write_bytes(original.replace(b'rnmos #1',b'bufif1 #1'))
 return dict(original=source.relative_to(ROOT).as_posix(),original_sha256=sha(source),
  archive_sha256=sha(archive),patch='Four rnmos #1 pull primitives -> bufif1 #1, only with all PU/PD=0',
  patched_sha256=sha(output),helper_sha256=sha(pathlib.Path(__file__)),scope='Simulation compatibility only; no pull/strength/electrical equivalence')
