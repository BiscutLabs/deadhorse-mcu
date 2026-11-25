"""Execute production C policy against independent binary/CRC construction."""
import ctypes as c
import os,pathlib,random
import struct
import subprocess
import unittest
from image import bundle,crc,directory,flash,header,words
HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parents[2];SRC=ROOT/'sw/boot'
fault=os.environ.get('DH_BOOT_FAULT','');assert fault in ('','CRC')
OUT=pathlib.Path(os.environ.get('DH_BOOT_TEST_OUTPUT','build/t36/native-policy'+('-'+fault if fault else '')));OUT.mkdir(parents=True,exist_ok=True)
(OUT/'peer.c').write_text('''#include <stdint.h>
unsigned char memory[65536];uint32_t fail_address=0xffffffff;
int dh_flash_read(uint32_t at,uint32_t *out) {
 if(at>65532 || at==fail_address)return 0;
 *out=(uint32_t)memory[at]|((uint32_t)memory[at+1]<<8)|((uint32_t)memory[at+2]<<16)|((uint32_t)memory[at+3]<<24);return 1;
}
''')
subprocess.run(['gcc','-shared','-fPIC','-O2','-Wall','-Wextra','-Werror',*(['-DDH_BOOT_FAULT_CRC'] if fault else []),str(SRC/'policy.c'),str(OUT/'peer.c'),'-o',str(OUT/'policy.so')],check=True)
lib=c.CDLL(str(OUT.resolve()/'policy.so'))
class Directory(c.Structure):_fields_=[('stride',c.c_uint32),('capacity',c.c_uint32)]
class Header(c.Structure):_fields_=[('w',c.c_uint32*24)]
lib.dh_crc.restype=c.c_uint32
lib.dh_crc_byte.restype=c.c_uint32
MISA=0x40101124
class Policy(unittest.TestCase):
 def setUp(self):
  self.d=Directory(16384,65536);c.c_uint32.in_dll(lib,'fail_address').value=0xffffffff
 def valid(self,b, golden=False):return lib.dh_header_valid(c.byref(Header.from_buffer_copy(b)),c.byref(self.d),int(golden),1,MISA)
 def test_crc(self):self.assertEqual(lib.dh_crc(c.c_char_p(b'123456789'),9),0xcbf43926)
 def test_crc_remainders(self):
  def reference(remainder,byte):
   remainder^=byte
   for _ in range(8):remainder=(remainder>>1)^ (0xedb88320 if remainder&1 else 0)
   return remainder
  rng=random.Random(0x36)
  for remainder in [0,0xffffffff]+[1<<bit for bit in range(32)]+[rng.getrandbits(32) for _ in range(32)]:
   for byte in range(256):self.assertEqual(lib.dh_crc_byte(remainder,byte),reference(remainder,byte))
  for length in (0,1,3,4,255,256,1024,14336):
   data=rng.randbytes(length);self.assertEqual(lib.dh_crc(c.c_char_p(data),length),crc(data))
 def test_directory(self):
  self.assertEqual(lib.dh_directory_decode(c.c_char_p(directory()),c.byref(self.d)),1)
  for index,value in [(0,0),(1,3),(2,0),(2,0xfffff000),(3,0x1001000),(3,4096),(4,0),(5,0),(6,0)]:
   w=list(struct.unpack('<8I',directory()));w[index]=value;w[7]=crc(words(w[:7]))
   self.assertEqual(lib.dh_directory_decode(c.c_char_p(words(w)),c.byref(self.d)),0,(index,value))
 def test_header_bounds(self):
  good=header(bytes(range(64)),b'\x6f\0\0\0');self.assertEqual(self.valid(good),1)
  for index,value in [(0,0),(1,2),(2,0),(2,0xffffffff),(3,2),(4,0),(4,14340),(4,0xfffffffc),(5,64),(5,1),(7,0),(7,1028),(8,4),(10,260),(10,1),(12,63),(12,14340),(13,1024),(14,0),(14,1025),(15,0x80000100),(15,0x40000108),(16,0x40000100),(17,0),(18,0),(19,1),(20,1),(21,1),(23,0xffffffff)]:
   w=list(struct.unpack('<24I',good));w[index]=value;w[22]=crc(words(w[:22]))
   self.assertEqual(self.valid(words(w)),0,(index,value))
  bad=bytearray(good);bad[88]^=1;self.assertEqual(self.valid(bad),0)
  self.assertEqual(self.valid(header(b'abcd',b'efgh',generation=0),True),1)
 def load(self,slots):
  b=flash(slots);memory=(c.c_ubyte*65536).in_dll(lib,'memory');memory[:]=b
 def choose(self):
  h=Header();at=c.c_uint32();ok=lib.dh_choose(c.byref(self.d),c.byref(h),c.byref(at),MISA)
  return ok,at.value,h.w[2] if ok else 0
 def test_selection(self):
  p=b'abcd';l=b'efgh';g=bundle(p,l,generation=0);a=bundle(p,l,generation=5);b=bundle(p,l,generation=6)
  for slots,expected in [({0:g,1:a,2:b},(1,36864,6)),({0:g,1:a,2:a},(1,20480,5)),({0:g},(1,4096,0)),({},(0,0,0))]:
   self.load(slots);self.assertEqual(self.choose(),expected)
  bad=bytearray(b);bad[256]^=1;self.load({0:g,1:a,2:bad});self.assertEqual(self.choose(),(1,20480,5))
  self.load({1:bundle(p,l,committed=False)});self.assertEqual(self.choose()[0],0)
 def test_transport_distinct_from_crc(self):
  b=bundle(b'abcd',b'efgh');h=Header.from_buffer_copy(b[:96]);self.load({1:b})
  self.assertEqual(lib.dh_payload_status(20480,c.byref(h)),1)
  c.c_uint32.in_dll(lib,'fail_address').value=20736
  self.assertEqual(lib.dh_payload_status(20480,c.byref(h)),-1)
  c.c_uint32.in_dll(lib,'fail_address').value=0xffffffff
  (c.c_ubyte*65536).in_dll(lib,'memory')[20736]^=1
  self.assertEqual(lib.dh_payload_status(20480,c.byref(h)),0)
if __name__=='__main__':unittest.main()
