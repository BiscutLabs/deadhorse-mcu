"""Production boot_main C against independent paired images and retained RAM.

Native functional evidence only: no core, CDC, SRAM arbitration or pin timing.
"""
import ctypes as c
import os,pathlib,subprocess,unittest
from image import bundle,flash
HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parents[2];SRC=ROOT/'sw/boot'
fault=os.environ.get('DH_BOOT_FAULT','');assert fault in ('','WARM_SKIP_RELOAD')
OUT=pathlib.Path(os.environ.get('DH_BOOT_TEST_OUTPUT','build/t41/native-warm'+('-'+fault if fault else '')))
OUT.mkdir(parents=True,exist_ok=True)
subprocess.run(['gcc','-shared','-fPIC','-O2','-Wall','-Wextra','-Werror',
 *(['-DDH_BOOT_FAULT_'+fault] if fault else []),'-I'+str(SRC),'-include',str(HERE/'host_boot_overrides.h'),
 str(SRC/'main.c'),str(SRC/'policy.c'),str(HERE/'host_boot_peer.c'),'-o',str(OUT/'boot.so')],check=True)
lib=c.CDLL(str((OUT/'boot.so').resolve()))
def val(name):return c.c_uint32.in_dll(lib,name).value
def put(name,value):c.c_uint32.in_dll(lib,name).value=value
def memory(base,size):return (c.c_ubyte*size).from_address(base)

class Warm(unittest.TestCase):
 def setUp(self):
  lib.host_boot_init();self.perf=bytes(range(64));self.lite=bytes(range(32));self.config=b'CFG1'
  self.load(True);self.assertEqual(lib.host_boot_run(),1)
  self.assertEqual(list((c.c_uint32*5).in_dll(lib,'entered')),[0x20000000,0x20003800,4,7,65])
 def load(self,start):
  (c.c_ubyte*65536).in_dll(lib,'flash_bytes')[:]=flash({1:bundle(self.perf,self.lite,self.config,generation=7,start_lite=start)})
 def warm(self,cause=8):lib.host_boot_warm(cause)
 def check_release(self):
  self.assertEqual(val('releases'),1)
  self.assertEqual(bytes((c.c_ubyte*14336).in_dll(lib,'release_perf'))[:len(self.perf)],self.perf)
  self.assertEqual(bytes((c.c_ubyte*1024).in_dll(lib,'release_lite'))[:len(self.lite)],self.lite)
 def test_matching_images_skip_both_copies_and_pass_causes(self):
  memory(0x20003800,4)[:]=b'LIVE'
  for cause in (4,8,16,32,1|4|8|16|32):
   self.warm(cause);self.assertEqual(lib.host_boot_run(),1);self.check_release()
   self.assertEqual(val('payload_reads'),0)
   self.assertEqual(bytes(memory(0x20003800,4)),b'LIVE')
   self.assertEqual((c.c_uint32*5).in_dll(lib,'entered')[4],cause)
 def test_corrupt_either_image_reloads_both_before_release(self):
  for addresses in ((0x20000004,),(0x30000004,),(0x20000004,0x30000004)):
   for at in addresses:memory(at,1)[0]^=1
   self.warm();self.assertEqual(lib.host_boot_run(),1)
   self.check_release()
   self.assertEqual(val('payload_reads'),(len(self.perf)+len(self.lite))//4)
   self.assertEqual(bytes(memory(0x20000000,len(self.perf))),self.perf)
   self.assertEqual(bytes(memory(0x30000000,len(self.lite))),self.lite)
 def test_bad_context_and_uncommitted_hardware_context_fail_closed(self):
  before=bytes(memory(0x20003900,128))
  for at in (0x20003900,0x20003904,0x20003914,0x20003974):
   memory(0x20003900,128)[:]=before;memory(at,1)[0]^=1
   self.warm();self.assertEqual(lib.host_boot_run(),3);self.assertEqual(val('releases'),0)
  memory(0x20003900,128)[:]=before;self.warm();put('boot_status',9)
  self.assertEqual(lib.host_boot_run(),3)
 def test_missing_changed_and_corrupted_same_bundle_fail_closed(self):
  raw=bytes((c.c_ubyte*65536).in_dll(lib,'flash_bytes'))
  for fault_at in (20480+8,20480+256):
   (c.c_ubyte*65536).in_dll(lib,'flash_bytes')[:]=raw
   (c.c_ubyte*65536).in_dll(lib,'flash_bytes')[fault_at]^=1
   memory(0x20000000,1)[0]=self.perf[0]^1 # require reload independently in each case
   self.warm();self.assertEqual(lib.host_boot_run(),3);self.assertEqual(val('releases'),0)
  (c.c_ubyte*65536).in_dll(lib,'flash_bytes')[:]=raw
  put('flash_fail',20480);self.warm();self.assertEqual(lib.host_boot_run(),3)
 def test_lite_start_false_remains_held(self):
  lib.host_boot_init();self.load(False);self.assertEqual(lib.host_boot_run(),1)
  self.warm();self.assertEqual(lib.host_boot_run(),1)
  self.assertEqual(val('releases'),0);self.assertEqual(val('boot_status')&3,1)

if __name__=='__main__':unittest.main()
