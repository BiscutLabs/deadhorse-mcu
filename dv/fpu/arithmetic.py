"""Integer recurrence argument for the serial multiplier, separate from RTL tests."""
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]

def check():
    out=ROOT/'build/t12/arithmetic';out.mkdir(parents=True,exist_ok=True)
    results=[]
    for k in range(24):
        # P_k = floor(B/2^k) + A*(B mod 2^k)*2^(24-k).
        # Write B = 2^(k+1)q + 2^k b + r, 0<=r<2^k, b in {0,1}.
        # The step consumes b and shifts the 49-bit sum before narrowing to 48.
        for fault in (False,True):
            name=f'step_{k}'+('_fault' if fault else '')
            shift=1<<(24-k); factor=1<<k
            p=f'(+ (* 2 q) b (* A r {shift}))'
            step=f'(div (+ {p} (* b A {1<<24})) 2)'
            target=f'(+ q (* A (+ r (* b {factor+(1 if fault else 0)})) {shift//2}))'
            script='(set-logic QF_NIA)\n(set-option :timeout 5000)\n'
            script+=''.join(f'(declare-const {n} Int)\n' for n in ('A','q','r','b'))
            script+=f'(assert (and (<= 0 A) (< A {1<<24}) (<= 0 q) (< q {1<<(23-k)}) (<= 0 r) (< r {factor}) (or (= b 0) (= b 1))))\n'
            script+=f'(assert (not (= {step} {target})))\n(check-sat)\n'
            path=out/(name+'.smt2');path.write_text(script)
            result=subprocess.run(['z3',str(path)],cwd=ROOT,capture_output=True,text=True,timeout=8)
            result.check_returncode();status=result.stdout.strip()
            (out/(name+'.log')).write_text(result.stdout+result.stderr)
            if status!=('sat' if fault else 'unsat'):
                raise ValueError(f'Multiply recurrence {name}: {status}')
            results.append(dict(step=k,fault=fault,status=status))
    # The maximum pre-shift sum fits exactly in 49 bits; do not discard its
    # carry. This is the reason the production 24-bit sum uses +&.
    maximum=((1<<48)-1)+((1<<24)-1)*(1<<24)
    assert maximum < 1<<49
    (out/'result.json').write_text(json.dumps(dict(status='pass',results=results,
        scope='integer recurrence, base P0=B and endpoint P24=A*B; not full RTL arithmetic equivalence',
        maximum_pre_shift_sum=maximum),indent=2)+'\n')
    print('PASS multiplier recurrence: 24 integer steps and 24 rejected faults',flush=True)

if __name__=='__main__': check()
