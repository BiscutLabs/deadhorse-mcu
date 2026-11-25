"""Native execution of ROM recovery C; peer transport/model, not wire timing."""
import ctypes as c
import os,pathlib,shutil,struct,subprocess,unittest
from image import bundle,crc,flash,header,words
HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parents[2];SRC=ROOT/'sw/boot'
fault=os.environ.get('DH_BOOT_FAULT','');assert fault in ('','RANGE','COMMIT')
OUT=pathlib.Path(os.environ.get('DH_BOOT_TEST_OUTPUT','build/t36/native-recovery'+('-'+fault if fault else '')));OUT.mkdir(parents=True,exist_ok=True)
subprocess.run(['gcc','-shared','-fPIC','-O2','-Wall','-Wextra','-Werror',*(['-DDH_BOOT_FAULT_'+fault] if fault else []),'-I'+str(HERE),'-I'+str(SRC),'-include',str(HERE/'host_overrides.h'),str(SRC/'recovery.c'),str(SRC/'policy.c'),str(HERE/'host_peer.c'),'-o',str(OUT/'recovery.so')],check=True)
def encode(data):
 out=bytearray([0]);at=0;code=1
 for b in data:
  if b==0:out[at]=code;at=len(out);out.append(0);code=1
  else:
   out.append(b);code+=1
   if code==255:out[at]=code;at=len(out);out.append(0);code=1
 out[at]=code;return bytes(out)+b'\0'
def decode(data):
 out=bytearray();i=0
 while i<len(data):
  code=data[i];i+=1
  if not code or i+code-1>len(data):raise ValueError('COBS')
  out+=data[i:i+code-1];i+=code-1
  if code!=255 and i<len(data):out.append(0)
 return bytes(out)
def request(op,seq,address=0,payload=b''):
 p=struct.pack('<BBHIH',1,op,seq,address,len(payload))+payload
 return encode(p+words([crc(p)]))
class Recovery(unittest.TestCase):
 serial=0
 def setUp(self):
  Recovery.serial+=1;p=OUT/f'instance{Recovery.serial}.so';shutil.copyfile(OUT/'recovery.so',p)
  self.lib=c.CDLL(str(p.resolve()));self.lib.host_init();self.seq=0
  self.mem=(c.c_ubyte*65536).in_dll(self.lib,'flash_bytes');self.mem[:]=flash({0:bundle(b'abcd',b'efgh',generation=0),1:bundle(b'abcd',b'efgh',generation=4)})
 def val(self,name):return c.c_uint.in_dll(self.lib,name).value
 def set(self,name,value):c.c_uint.in_dll(self.lib,name).value=value
 def feed(self,data):
  self.set('input_at',0);self.set('input_size',len(data));self.set('output_size',0)
  (c.c_ubyte*4096).in_dll(self.lib,'input_bytes')[:len(data)]=data
  while self.val('input_at')<len(data):self.lib.host_poll()
  raw=bytes((c.c_ubyte*4096).in_dll(self.lib,'output_bytes')[:self.val('output_size')]);out=[]
  for p in raw.split(b'\0'):
   if not p:continue
   d=decode(p);self.assertEqual(crc(d[:-4]),int.from_bytes(d[-4:],'little'));out.append(d)
  return out
 def cmd(self,op,address=0,payload=b''):
  self.seq+=1;out=self.feed(request(op,self.seq,address,payload));self.assertEqual(len(out),1);return out[0][10:-4]
 def test_capability_permissions_duplicates(self):
  self.assertEqual(self.cmd(5),b'\0\1'+words([0x35304844,0x117]))
  for address in (0,0x20000000,0x20003900,0x20003a80,0x30000000,0x40010000,0xfffffffc):
   self.assertEqual(self.cmd(2,address,words([123])+b'\x0f'),b'\2')
  self.assertEqual(self.cmd(3,0x20003980,b'abcd'),b'\0\4\0')
  self.assertEqual(self.cmd(1,0x20003980),b'\0abcd')
  self.assertEqual(self.cmd(2,0x20003980,b'WXYZ\x05'),b'\0')
  self.assertEqual(self.cmd(1,0x20003980),b'\0WbYd')
  packet=request(3,100,0x20003984,b'1234');self.assertEqual(self.feed(packet),self.feed(packet))
  self.assertEqual(self.feed(request(3,100,0x20003984,b'5678'))[0][10:-4],b'\1\0\0')
  self.assertEqual(self.cmd(4,0,words([0x44524853])),b'\1')
 def test_stream_commit_and_busy(self):
  h=header(b'abcd',b'efgh',generation=5,committed=False)
  # Second request arrives while BEGIN is validating flash: BUSY, no write.
  replies=self.feed(request(0x10,1,1,h)+request(3,2,0x20003980,b'1234'))
  self.assertEqual(sorted(d[10] for d in replies),[0,5]);self.assertEqual(self.val('erases'),4)
  self.seq=2;self.assertEqual(self.cmd(0x11,256,b'abcdefgh'),b'\0')
  self.assertEqual(self.cmd(0x12),b'\0')
  self.assertEqual(self.val('program_commit_index'),self.val('programs'))
  self.assertEqual(bytes(self.mem[36864:36864+96]),header(b'abcd',b'efgh',generation=5))
  self.assertEqual(bytes(self.mem[36864+256:36864+264]),b'abcdefgh')
  old=self.val('programs');self.assertEqual(self.feed(request(0x12,self.seq))[0][10:-4],b'\0');self.assertEqual(self.val('programs'),old)
 def test_uncertain_newest_never_erased(self):
  for at in (20480,20480+256):
   self.set('fail_address',at)
   self.assertEqual(self.cmd(0x10,0,header(b'abcd',b'efgh',generation=5,committed=False)),b'\3')
   self.assertEqual(self.val('erases'),0)
 def test_malformed_preserves_session(self):
  self.assertEqual(self.cmd(0x10,1,header(b'abcd',b'efgh',generation=5,committed=False)),b'\0')
  bad=bytearray(request(0x11,200,256,b'abcdefgh'));bad[-2]^=1
  self.assertEqual(self.feed(bad),[])
  self.assertEqual(self.cmd(0x11,256,b'abcdefgh'),b'\0')
  self.assertEqual(self.cmd(0x12),b'\0')
 def test_bad_data_cancels_session(self):
  self.assertEqual(self.cmd(0x10,1,header(b'abcd',b'efgh',generation=5,committed=False)),b'\0')
  self.assertEqual(self.cmd(0x11,260,b'abcdefgh'),b'\1')
  self.assertEqual(self.cmd(0x11,256,b'abcdefgh'),b'\1')
  self.assertEqual(self.val('programs'),0)
 def test_power_loss_each_mutation(self):
  class Directory(c.Structure):_fields_=[('stride',c.c_uint32),('capacity',c.c_uint32)]
  class Header(c.Structure):_fields_=[('w',c.c_uint32*24)]
  original=bytes(self.mem)
  for cut in range(1,31):
   self.setUp();self.set('cut_after',cut)
   status=self.cmd(0x10,1,header(b'abcd',b'efgh',generation=5,committed=False))
   if status==b'\0':status=self.cmd(0x11,256,b'abcdefgh')
   if status==b'\0':status=self.cmd(0x12)
   self.assertEqual(status,b'\3',cut)
   self.assertEqual(bytes(self.mem[:36864]),original[:36864],cut)
   h=Header();at=c.c_uint32();d=Directory(16384,65536)
   self.assertEqual(self.lib.dh_choose(c.byref(d),c.byref(h),c.byref(at),0x40101124),1,cut)
   self.assertEqual(h.w[2],5 if cut==30 else 4,cut)
if __name__=='__main__':unittest.main()
