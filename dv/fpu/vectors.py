"""Pinned TestFloat plus directed/seeded SoftFloat RISCV reference vectors."""
import hashlib
import json
from pathlib import Path
import random
import subprocess

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM = ROOT / 'build/t12/upstream'
OPS = ['ADD','SUB','MUL','MADD','MSUB','NMSUB','NMADD','DIV','SQRT',
       'MIN','MAX','EQ','LT','LE','SGNJ','SGNJN','SGNJX','CLASS',
       'MV_X_W','MV_W_X','TO_I','TO_U','FROM_I','FROM_U']
RM = ['-rnear_even','-rminMag','-rmin','-rmax','-rnear_maxMag']
FUNCTIONS = {0:'f32_add',1:'f32_sub',2:'f32_mul',3:'f32_mulAdd',7:'f32_div',
             8:'f32_sqrt',11:'f32_eq',12:'f32_lt',13:'f32_le',
             20:'f32_to_i32',21:'f32_to_ui32',22:'i32_to_f32',23:'ui32_to_f32'}
CORNERS = [0,0x80000000,1,0x80000001,0x7fffff,0x807fffff,0x800000,0x80800000,
           0x3e800000,0xbe800000,0x3f000000,0xbf000000,0x3f800000,0xbf800000,
           0x3f800001,0x3f7fffff,0x4effffff,0x4f000000,0xcf000000,0x4f800000,
           0x7f7fffff,0xff7fffff,0x7f800000,0xff800000,0x7fc00000,0xffc12345,
           0x7f800001,0xff800001,0x7fffffff,0xffffffff,0x01000001,0x33800000]


def run(command, **kw):
    return subprocess.run([str(x) for x in command], cwd=ROOT, check=True,
                          text=True, capture_output=True, **kw).stdout


def prepare():
    lock=json.loads((ROOT/'tools/env/fpu.lock.json').read_text())
    for name, pin in lock.items():
        directory=UPSTREAM/('berkeley-'+name+'-3')
        if not directory.exists():
            run(['git','clone',pin['url'],directory])
            run(['git','-C',directory,'checkout','--detach',pin['commit']])
        for path,digest in pin['files'].items():
            if hashlib.sha256((directory/path).read_bytes()).hexdigest()!=digest:
                raise ValueError(f'{name} locked source mismatch: {path}')
    sf=UPSTREAM/'berkeley-softfloat-3'; tf=UPSTREAM/'berkeley-testfloat-3'
    # Force rebuild: make does not track a changed specialization variable or
    # authenticate existing object files in this generated directory.
    run(['make','-B','-C',sf/'build/Linux-x86_64-GCC','SPECIALIZE_TYPE=RISCV','-j4'])
    run(['make','-B','-C',tf/'build/Linux-x86_64-GCC','testfloat_gen','-j4'])
    oracle=ROOT/'build/t12/oracle'
    run(['gcc','-O2','-Wall','-Wextra','-Werror','-fno-builtin-nan',
         '-I'+str(sf/'source/include'),ROOT/'dv/fpu/oracle.c',
         sf/'build/Linux-x86_64-GCC/softfloat.a','-o',oracle])
    return tf/'build/Linux-x86_64-GCC/testfloat_gen', oracle


def generate(output):
    gen,oracle=prepare(); rng=random.Random(0xf012)
    cases=[]; direct_expected={}
    # Every operation/rm receives independent random bit patterns and the full
    # directed pair cross-product, including signaling NaNs and signed zeros.
    for op in range(len(OPS)):
        for rm in range(5):
            for a in CORNERS:
                for b in CORNERS:
                    c=rng.choice(CORNERS)
                    cases.append((op,rm,a,b,c))
            for _ in range(256):
                cases.append((op,rm,*[rng.getrandbits(32) for _ in range(3)]))
            # TestFloat functions provide independent input distributions and
            # expected result/flags. Non-IEEE operations use TestFloat operands.
            function=FUNCTIONS.get(op)
            args=[str(gen),'-seed','61458','-forever','-tininessafter','-exact',RM[rm]]
            args += [function] if function else ['f32','3']
            # TestFloat's finite complete suites have large minimum lengths.
            # Take an explicit 256-vector prefix of its infinite seeded stream;
            # this is sampled coverage, not a claim of exhaustive TestFloat.
            process=subprocess.Popen(args,cwd=ROOT,stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE,text=True)
            lines=[process.stdout.readline() for _ in range(256)]
            process.terminate(); process.wait(timeout=10)
            if any(not line for line in lines):
                raise ValueError('TestFloat stream ended before sample: '+process.stderr.read())
            for line in lines:
                fields=[int(x,16) for x in line.split()]
                values=fields[:-2] if function else fields
                values=(values+[0,0])[:3]
                index=len(cases); cases.append((op,rm,*values))
                if function: direct_expected[index]=tuple(fields[-2:])
    # Fused cancellation where separate multiply then add produces a different
    # answer, and invalid 0*infinity even with a quiet NaN addend.
    for op in range(3,7):
        for rm in range(5):
            for a,b,c in [(0x3f800001,0x3f7ffffe,0xbf800000),
                          (0,0x7f800000,0x7fc12345),
                          (0x00800000,0x3f7fffff,0x80000001)]:
                cases.append((op,rm,a,b,c))
    inputs=''.join(f'{o} {r} {a:08x} {b:08x} {c:08x}\n' for o,r,a,b,c in cases)
    expected=[tuple(int(x,16) for x in line.split())
              for line in run([oracle],input=inputs).splitlines()]
    if len(expected)!=len(cases): raise ValueError('oracle lost vectors')
    for i,e in direct_expected.items():
        if expected[i]!=e: raise ValueError(f'TestFloat/SoftFloat mismatch {cases[i]}: {expected[i]} != {e}')
    output.mkdir(parents=True,exist_ok=True)
    path=output/'vectors.txt'
    path.write_text(''.join(f'{o} {r} {a:08x} {b:08x} {c:08x} {v:08x} {f:02x}\n'
                           for (o,r,a,b,c),(v,f) in zip(cases,expected)))
    receipt=dict(seed=0xf012,count=len(cases),testfloat_expected=len(direct_expected),
                 sha256=hashlib.sha256(path.read_bytes()).hexdigest(),operations=OPS,rounding_modes=list(range(5)))
    (output/'vectors.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS reference vectors',receipt['count'],flush=True)
    return path


if __name__=='__main__':
    generate(ROOT/'build/t12')
