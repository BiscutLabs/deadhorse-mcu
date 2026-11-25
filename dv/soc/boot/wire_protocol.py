"""Independent gateway-v1 byte reference used by the serial-wire campaign."""
import binascii,struct
def crc(data):return binascii.crc32(data)&0xffffffff
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
 return encode(p+struct.pack('<I',crc(p)))
def replies(wire):
 if not wire or wire[-1]!=0:raise ValueError('Missing response delimiter')
 output=[]
 for encoded in wire[:-1].split(b'\0'):
  p=decode(encoded)
  if len(p)<15 or p[0]!=1 or not p[1]&128:raise ValueError('Response header')
  version,op,seq,address,count=struct.unpack('<BBHIH',p[:10])
  if count!=len(p)-14 or crc(p[:-4])!=int.from_bytes(p[-4:],'little'):raise ValueError('Response length/CRC')
  output.append(dict(op=op&127,seq=seq,address=address,payload=p[10:-4]))
 return output
def record(wire,expected_replies=1,delay=0,deadline=96000000):
 return struct.pack('<IIII',delay,len(wire),expected_replies,deadline)+wire
