"""Emitted RTL/model induction plus integer recurrence argument; no Ibex cycle claim."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'dv/core'))
from common import output_dir, run
from equiv import compare, negatives
from state_equiv import STATE
from mul_lemma import solve

TOP = 'IterativeMultiply'
W = 1 << 32


def arithmetic(out):
    """C_k=q_k+A*p_k*2^(32-k), B=q_k*2^k+p_k.

    Splitting q_k=2*q_next+bit makes the step linear in P=A*p_k.
    A separate polynomial identity links P_next to the next processed prefix.
    Enumerating all 32 positions avoids any symbolic exponent assumption.
    """
    checks = {}
    def lemma(name, domain, statement, fault, logic='QF_LIA'):
        checks[name+'-domain'] = solve(out,name+'-domain',domain,'sat',logic)
        checks[name] = solve(out,name,domain+f'(assert (not {statement}))','unsat',logic)
        checks[name+'-fault'] = solve(out,name+'-fault',domain+f'(assert (not {fault}))','sat',logic)
    ints = lambda *names: ''.join(f'(declare-const {n} Int)\n' for n in names)
    lemma('base',ints('b')+f'(assert (and (<= 0 b) (< b {W})))\n',
          '(and (= (+ b (* 0 4294967296)) b) (= (mod b 1) 0) (= (div b 1) b))',
          '(= (mod b 1) 1)')
    for k in range(32):
        scale = 1 << (32-k)
        domain = ints('p','q')+'(assert (<= 0 q))\n'
        lemma(f'parity-{k}',domain,f'(= (mod (+ q (* p {scale})) 2) (mod q 2))',
              f'(= (mod (+ q (* p {scale})) 2) (- 1 (mod q 2)))')
        domain = ints('q','p','b') + f'(assert (and (<= 0 q) (<= 0 p) (< p {1<<k}) (= b (+ (* q {1<<k}) p))))\n'
        next_p = f'(+ p (* (mod q 2) {1<<k}))'
        lemma(f'decomposition-{k}',domain,
              f'(and (= b (+ (* (div q 2) {1<<(k+1)}) {next_p})) (<= 0 {next_p}) (< {next_p} {1<<(k+1)}))',
              f'(= b (+ (* (div q 2) {1<<(k+1)}) {next_p} 1))')
        for bit in (0, 1):
            name = f'step-{k}-{bit}'
            domain = '(declare-const a Int)\n(declare-const p Int)\n(declare-const q Int)\n'
            c = f'(+ (* 2 q) {bit} (* p {scale}))'
            next_c = f'(+ (div {c} 2) (* {bit*(W//2)} a))'
            expected = f'(+ q (* (+ p (* {bit*(1<<k)} a)) {scale//2}))'
            checks[name] = solve(out, name, domain + f'(assert (not (= {next_c} {expected})))', 'unsat', 'QF_LIA')
            checks[name+'-fault'] = solve(out, name+'-fault', domain +
                f'(assert (not (= (+ {next_c} 1) {expected})))', 'sat', 'QF_LIA')
    # Polynomial linkage for arbitrary processed prefix and digit weight.
    polynomial = ''.join(f'(declare-const {n} Int)\n' for n in ('a','p','weight','bit'))
    identity = '(= (+ (* a p) (* bit a weight)) (* a (+ p (* bit weight))))'
    checks['prefix-product'] = solve(out, 'prefix-product', polynomial + f'(assert (not {identity}))', 'unsat')
    checks['prefix-fault'] = solve(out, 'prefix-fault', polynomial +
        '(assert (not (= (+ (* a p) (* bit a weight) 1) (* a (+ p (* bit weight))))))', 'sat')
    # No overflow is discarded by the 65-bit temporary; division by two
    # restores a 64-bit combined accumulator for every representable input.
    domain = '(declare-const c Int)\n(declare-const a Int)\n' + \
        f'(assert (and (<= 0 c) (< c {W*W}) (<= 0 a) (< a {W})))\n'
    temp = f'(+ c (* (mod c 2) a {W}))'
    checks['range'] = solve(out, 'range', domain +
        f'(assert (not (and (<= 0 {temp}) (< {temp} {2*W*W}) (< (div {temp} 2) {W*W}))))', 'unsat')
    checks['range-fault'] = solve(out, 'range-fault', domain +
        f'(assert (not (< {temp} {W*W})))', 'sat')
    domain = ints('b','q','p') + f'(assert (and (<= 0 b) (< b {W}) (<= 0 p) (< p {W}) (<= 0 q) (= b (+ (* q {W}) p))))\n'
    lemma('endpoint',domain,'(and (= q 0) (= p b))','(= q 1)')
    # Prove the same word projection through Euclidean witnesses, avoiding
    # a single expensive nested div/mod query. Existence and uniqueness are
    # checked, so the witness decomposition excludes no integer input.
    for modulus in (W,W*W):
        lemma(f'euclidean-exists-{modulus}',ints('c'),
              f'(and (= c (+ (* {modulus} (div c {modulus})) (mod c {modulus}))) (<= 0 (mod c {modulus})) (< (mod c {modulus}) {modulus}))',
              f'(= c (+ 1 (* {modulus} (div c {modulus})) (mod c {modulus})))')
        domain = ints('c','q','r')+f'(assert (and (= c (+ (* {modulus} q) r)) (<= 0 r) (< r {modulus})))\n'
        lemma(f'euclidean-unique-{modulus}',domain,
              f'(and (= q (div c {modulus})) (= r (mod c {modulus})))',
              f'(= (+ q 1) (div c {modulus}))')
    domain = ints('c','h','l','a','b','q','r')+f'(assert (and (= c (+ (* {W} h) l)) (<= 0 l) (< l {W}) (= (- h a b) (+ (* {W} q) r)) (<= 0 r) (< r {W})))\n'
    corrected = f'(- c (* {W} a) (* {W} b))'
    packed = f'(+ (* {W} r) l)'
    lemma('word-projection-compose',domain,
          f'(and (= {corrected} (+ (* {W*W} q) {packed})) (<= 0 {packed}) (< {packed} {W*W}) (= {corrected} (+ (* {W} (- h a b)) l)))',
          f'(= {corrected} (+ 1 (* {W*W} q) {packed}))')
    for sa in (0,1):
        for sb in (0,1):
            domain = '(declare-const a Int)\n(declare-const b Int)\n'
            product = f'(* (- a {sa*W}) (- b {sb*W}))'
            corrected = f'(- (* a b) (* {sa*W} b) (* {sb*W} a))'
            checks[f'signed-{sa}{sb}'] = solve(out, f'signed-{sa}{sb}', domain +
                f'(assert (not (= {product} (+ {corrected} {sa*sb*W*W}))))', 'unsat')
            checks[f'signed-fault-{sa}{sb}'] = solve(out, f'signed-fault-{sa}{sb}', domain +
                f'(assert (not (= {product} (+ {corrected} {sa*sb*W*W+1}))))', 'sat')
    return checks


def elaborate(source, out, name):
    script = out / (name+'.ys')
    target = out / (name+'.json')
    script.write_text(f'read_slang --top {TOP} {source}\nprep -top {TOP} -flatten\n'
                      f'memory_map\nopt_clean\ncheck -assert\nwrite_json {target}\n')
    run(['yosys','-Q','-T','-s',script], out, name)
    return target


def covers(candidate, out):
    witnesses = {}
    a, b = 0x80000001, 0xffffffff
    for mode, scenario in [(m,'complete') for m in range(4)] + [(3,'stall'),(3,'reset-restart')]:
        name = f'cover-{mode}-{scenario}'
        finish = {'complete':37, 'stall':38, 'reset-restart':56}[scenario]
        x = a-W if mode&1 else a
        y = b-W if mode&2 else b
        value = ((x*y) >> 32) & (W-1)
        script = out/(name+'.ys')
        changes = ' -set-at 14 enable_i 0' if scenario=='stall' else \
                  (' -set-at 20 rst_ni 0' if scenario=='reset-restart' else '')
        script.write_text(f'read_json {candidate}\nprep -top {TOP}\nasync2sync\ndffunmap\n' +
            f'sat -seq {finish+2} -set-def-inputs -set rst_ni 1 -set-at 1 rst_ni 0 '
            f'-set enable_i 1 -set ready_i 0 -set a_i {a} -set b_i {b} '
            f'-set signed_mode_i {mode} -set high_i 1 '
            f'-set-at {finish} valid_o 1 -set-at {finish} result_o {value} '
            f'-set-at {finish} ready_i 1 -set-at {finish+1} valid_o 0 '
            f'-set-at {finish+2} valid_o 0 {changes} -show-ports -dump_vcd {out}/{name}.vcd\n')
        result = run(['yosys','-Q','-T','-s',script],out,name)
        if 'SAT solving finished - model found:' not in result.stdout:
            raise RuntimeError(f'Unreachable witness {name}')
        witnesses[name] = dict(status='covered',depth=finish+2)
    return witnesses


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    out = output_dir(args.output)
    receipt = dict(status='running', assumptions=[], kind='RTL-to-mathematical-machine induction plus integer recurrence lemmas',
                   ibex_cycle_equivalence=False)
    result = out/'result.json'
    result.write_text(json.dumps(receipt,indent=2)+'\n')
    try:
        run([sys.executable, 'tools/env/check.py'],out,'environment')
        run([sys.executable,'tools/sbt.py',
             f'set hw / Compile / unmanagedSources += file("{ROOT}/hw/ip/perf_core/formal/MultiplyModel.scala")',
             f'hw/runMain deadhorse.perf_core.EmitMultiplyModel {out.relative_to(ROOT)}/model'],out,'model-emit',timeout=600)
        candidate = (ROOT/args.candidate).resolve()
        if not candidate.is_relative_to(ROOT/'build'):
            raise ValueError('Candidate must be repository build output')
        model = out/'model/IterativeMultiply.sv'
        gold = elaborate(model,out,'gold')
        gate = elaborate(candidate,out,'candidate')
        proof = out/'transition'; proof.mkdir(exist_ok=True)
        if compare(TOP,gold,gate,proof) != 'proved':
            raise RuntimeError('Emitted transition/reset/output mismatch')
        negatives(TOP,gold,gate,proof)
        design = json.loads(gate.read_text())
        mod = design['modules'][TOP]
        faults = []
        # Each state component has its own deliberate next-state fault.
        for n,c in mod['cells'].items():
            if c['type'] not in STATE:
                continue
            aliases = [name for name,wire in mod['netnames'].items() if wire['bits']==c['connections']['Q']]
            label = sorted(aliases,key=lambda s: (not s.endswith('_q'),len(s)))[0]
            bad = copy.deepcopy(design)
            target = bad['modules'][TOP]
            newbit = max(b for w in target['netnames'].values() for b in w['bits'] if isinstance(b,int))+1
            con = target['cells'][n]['connections']
            # Invert the top bit, including carry into hi_q and sign capture.
            target['cells']['__fault'] = dict(type='$not', parameters={'A_SIGNED':'0','A_WIDTH':'1','Y_WIDTH':'1'},
                attributes={},port_directions={'A':'input','Y':'output'},connections={'A':[con['D'][-1]],'Y':[newbit]})
            con['D'][-1] = newbit
            directory = out/('fault-'+label); directory.mkdir(exist_ok=True)
            path = directory/'candidate.json'; path.write_text(json.dumps(bad))
            if compare(TOP,gold,path,directory) != 'failed':
                raise RuntimeError(f'Unrejected {label} fault')
            faults.append(label)
        if len(faults) != 9:
            raise RuntimeError('Unexpected state inventory; review proof correspondence')
        lemmas = out/'integer'; lemmas.mkdir(exist_ok=True)
        receipt.update(arithmetic=arithmetic(lemmas), state_faults=faults, covers=covers(gate,out),
            candidate_sha256=hashlib.sha256(candidate.read_bytes()).hexdigest(),
            model_sha256=hashlib.sha256(model.read_bytes()).hexdigest(), status='proved',
            linkage='all emitted state/reset/clock/enable/output transitions proved against mathematical machine; composition of integer lemmas with bitvector machine is independently reviewed, not one end-to-end solver theorem')
        print('PASS iterative multiply: emitted transition induction, all state faults and integer lemmas',flush=True)
    except Exception as exc:
        receipt.update(status='failed',error=str(exc))
        raise
    finally:
        result.write_text(json.dumps(receipt,indent=2)+'\n')


if __name__ == '__main__': main()
