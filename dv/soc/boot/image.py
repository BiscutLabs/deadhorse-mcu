"""Paired boot ABI3 image construction, independent of the ROM implementation."""
import binascii
import struct

def crc(data):return binascii.crc32(data)&0xffffffff
def words(values):return struct.pack('<'+'I'*len(values),*values)
def directory(stride=16384,capacity=65536):
    if stride<=0 or stride%4096 or capacity%4096 or not 4096+3*stride<=capacity<=0x1000000:raise ValueError('geometry')
    p=words([0x32425352,2,stride,capacity,4096+stride,4096+2*stride,4096])
    return p+words([crc(p)])
def header(perf,lite,config=b'',*,generation=1,start_lite=True,entry=0,allocation=None,lite_data=0,lite_stack=256,committed=True,perf_isa=0x40001104):
    if not perf or len(perf)%4 or len(perf)>14336:raise ValueError('performance bytes')
    if not lite or len(lite)%4 or len(lite)>1024:raise ValueError('lite bytes')
    if len(config)%4 or len(config)>256:raise ValueError('config bytes')
    if entry%2 or not 0<=entry<len(perf):raise ValueError('entry')
    allocation=len(perf) if allocation is None else allocation
    if not len(perf)<=allocation<=14336:raise ValueError('allocation')
    if not 16<=lite_stack<=1024 or not 0<=lite_data<=1024-lite_stack:raise ValueError('lite allocation')
    if not 0<=generation<0xffffffff:raise ValueError('generation')
    p=words([0x33424844,3,generation,int(start_lite),len(perf),entry,crc(perf),len(lite),0,crc(lite),len(config),crc(config),allocation,lite_data,lite_stack,perf_isa,0x40000010,1,256+len(perf)+len(lite)+len(config),0,0,0])
    return p+words([crc(p),0x54494d43 if committed else 0xffffffff])
def bundle(perf,lite,config=b'',**kwargs):
    return header(perf,lite,config,**kwargs)+b'\xff'*160+perf+lite+config
def flash(slots,*,stride=16384,capacity=65536):
    result=bytearray(b'\xff'*capacity);result[:32]=directory(stride,capacity)
    for slot,payload in slots.items():
        if slot not in (0,1,2) or len(payload)>stride:raise ValueError('slot')
        at=4096+slot*stride;result[at:at+len(payload)]=payload
    return result
