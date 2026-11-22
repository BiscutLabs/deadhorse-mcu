"""Exhaustive codes and boundary parameters against Python integer arithmetic."""
import argparse
import ctypes
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[3]

def main(output):
    out=(ROOT/output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    sources=[ROOT/'sw/hal/adc_convert.h',Path(__file__).resolve(),ROOT/'sw/hal/tests/adc_probe.c',ROOT/'tools/env/lock.json']
    hashes=lambda:{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    initial=hashes();commands=[]
    def load(variant):
        cmd=['cc','-std=c11','-Wall','-Wextra','-Werror','-shared','-fPIC',
             '-Isw/hal','sw/hal/tests/adc_probe.c','-o',str(out/(variant+'.so'))]
        if variant=='corrupt':cmd+=['-DADC_TEST_CORRUPT']
        subprocess.run(cmd,cwd=ROOT,check=True);commands.append(cmd)
        lib=ctypes.CDLL(str(out/(variant+'.so')));fn=lib.adc_probe
        fn.argtypes=[ctypes.c_uint16,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_int32,ctypes.POINTER(ctypes.c_uint32)]
        fn.restype=ctypes.c_bool
        return fn
    def oracle(fn):
        count=0
        for numerator,denominator,offset in [(25300,4095,0),(1,1,-4096),
            (0xffffffff,1,0x7fffffff),(0xffffffff,0xffffffff,-0x80000000),(0,7,-1)]:
            for code in range(4096):
                result=ctypes.c_uint32(0xdeadbeef)
                assert fn(code,numerator,denominator,offset,ctypes.byref(result))
                expected=(code*numerator//denominator+offset)%(1<<32)
                assert result.value==expected,('ADC_CONVERSION_MODEL',code,numerator,denominator,offset,result.value,expected)
                count+=1
        return count
    fn=load('correct');count=oracle(fn)
    for code,denominator in [(4096,1),(65535,1),(0,0),(4095,0)]:
        result=ctypes.c_uint32(0xdeadbeef)
        assert not fn(code,1,denominator,0,ctypes.byref(result)) and result.value==0xdeadbeef
    assert not fn(1,1,1,0,None)
    # The same oracle checks a separately compiled fault in the actual result path.
    try:
        oracle(load('corrupt'))
    except AssertionError as error:
        assert error.args[0][0]=='ADC_CONVERSION_MODEL'
        negative=error.args[0]
    else:
        raise AssertionError('ADC_CONVERSION_ORACLE_ACCEPTED_FAULT')
    # Linkability on both cores, separate from the native arithmetic oracle.
    # The compiler's matching libgcc supplies wide integer arithmetic.
    for arch,abi in [('rv32e','ilp32e'),('rv32imfc','ilp32f')]:
        cmd=['riscv64-unknown-elf-gcc','-march='+arch,'-mabi='+abi,'-ffreestanding',
             '-nostdlib','-Os','-Wall','-Wextra','-Werror','-Isw/hal','sw/hal/tests/adc_probe.c',
             '-Wl,-e,adc_probe','-Wl,--no-relax','-lgcc','-o',str(out/(arch+'.elf'))]
        subprocess.run(cmd,cwd=ROOT,check=True);commands.append(cmd)
    assert hashes()==initial
    receipt=dict(status='pass',valid_cases=count,invalid_cases=5,commands=commands,negative=negative,
        source_sha256=initial,compiler=subprocess.check_output(['cc','--version'],text=True).splitlines()[0],
        target_compiler=subprocess.check_output(['riscv64-unknown-elf-gcc','--version'],text=True).splitlines()[0],
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        artifact_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()})
    (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS',count,'valid cases, 5 invalid cases; compiled corruption rejected by ADC_CONVERSION_MODEL; both core ABI links pass')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args();main(a.output)
