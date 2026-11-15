"""D44 integer lemmas for RV32MFast; not an RTL equivalence proof."""
import argparse
import json
import sys

from common import inputs, output_dir, run

Q = 1 << 16
WORD = Q * Q


def limbs(signed_a, signed_b):
    declarations = ''.join(f'(declare-const {name} Int)\n' for name in ('al', 'ah', 'bl', 'bh'))
    for name, signed in (('al', False), ('ah', signed_a), ('bl', False), ('bh', signed_b)):
        lower, upper = (-Q//2, Q//2-1) if signed else (0, Q-1)
        declarations += f'(assert (and (<= {lower} {name}) (<= {name} {upper})))\n'
    return declarations + f'''
(define-fun a () Int (+ al (* {Q} ah)))
(define-fun b () Int (+ bl (* {Q} bh)))
(define-fun p00 () Int (* al bl))
(define-fun p01 () Int (* al bh))
(define-fun p10 () Int (* ah bl))
(define-fun p11 () Int (* ah bh))
'''


def stages():
    # gen_mult_fast: ALBL product, ALBH + upper(ALBL), AHBL + saved ALBH,
    # then AHBH + arithmetic upper(AHBL). SMT div by positive Q is floor.
    return f'''
(define-fun t () Int (+ p01 (div p00 {Q})))
(define-fun u () Int (+ t p10))
(define-fun v () Int (+ p11 (div u {Q})))
(define-fun expanded () Int (+ p00 (* {Q} (+ p01 p10)) (* {WORD} p11)))
(define-fun packed_low () Int (+ (mod p00 {Q}) (* {Q} (mod (+ p10 (mod t {Q})) {Q}))))
'''


def solve(output, name, body, expected, logic='QF_NIA'):
    path = output/(name+'.smt2')
    path.write_text(f'(set-logic {logic})\n(set-option :timeout 600000)\n' + body +
                    '\n(check-sat-using (then (using-params simplify :som true) smt))\n')
    result = run(['z3', '-smt2', path], output, name, timeout=630)
    status = result.stdout.strip()
    if status != expected:
        raise RuntimeError(f'{name}: expected {expected}, got {status}; no proof claimed')
    return dict(status=status, seconds=result.elapsed_seconds)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = output_dir(args.output)
    (output/'result.json').write_text('{"status":"running"}\n')
    inputs()
    run([sys.executable, 'tools/env/check.py'], output, 'environment')
    checks = {}
    for name, sa, sb in (('mul', False, False), ('mulh', True, True),
                         ('mulhsu', True, False), ('mulhu', False, False)):
        domain = limbs(sa, sb) + stages()
        checks[name+'-domain'] = solve(output, name+'-domain', domain, 'sat')
        checks[name+'-expansion'] = solve(output, name+'-expansion', domain +
            '(assert (not (= (* a b) expanded)))', 'unsat')
        checks[name+'-shift-fault'] = solve(output, name+'-shift-fault', domain +
            f'(assert (not (= (* a b) (+ p00 (* {2*Q} (+ p01 p10)) (* {WORD} p11)))))', 'sat')
        bound = 1 << 33
        # Truncated 34-bit MAC intermediates and the signed/unsigned 18-bit
        # upper slice preserve these mathematical values in the real range.
        ranges = (f'(and (<= 0 p00) (< p00 {WORD}) '
                  f'(<= {-bound} t) (< t {bound}) (<= {-bound} u) (< u {bound}) '
                  f'(<= {-2*Q} (div u {Q})) (< (div u {Q}) {2*Q}) '
                  f'(<= {-bound} v) (< v {bound})' +
                  (' (<= 0 u)' if not sa and not sb else '') + ')')
        checks[name+'-ranges'] = solve(output, name+'-ranges', domain + f'(assert (not {ranges}))', 'unsat')
        checks[name+'-range-fault'] = solve(output, name+'-range-fault', domain +
            f'(assert (not (< p00 {Q})))', 'sat')
        print(f'PROVED integer expansion/ranges: {name}; wrong shift/range rejected', flush=True)
    # Universal carry identities. These quantify arbitrary integer partial
    # products; expansion above supplies their interpretation. No product
    # equality is assumed. This separates polynomial and division reasoning.
    abstract = ''.join(f'(declare-const p{i} Int)\n' for i in ('00', '01', '10', '11')) + stages()
    for name, property_text, fault in (
        ('low', f'(= packed_low (mod expanded {WORD}))',
         f'(= (+ packed_low 1) (mod expanded {WORD}))'),
        ('high', f'(= v (div expanded {WORD}))',
         f'(= (+ p11 (div u {Q//2})) (div expanded {WORD}))')):
        checks[name+'-domain'] = solve(output, name+'-domain', abstract, 'sat', 'QF_LIA')
        checks[name] = solve(output, name, abstract+f'(assert (not {property_text}))', 'unsat', 'QF_LIA')
        checks[name+'-fault'] = solve(output, name+'-fault', abstract+f'(assert (not {fault}))', 'sat', 'QF_LIA')
    (output/'result.json').write_text(json.dumps(dict(status='proved (integer lemmas)', checks=checks,
        assumptions='16-bit unsigned low limbs; signed/unsigned high-limb ranges by instruction; universal integer carry lemmas',
        limitation='Correspondence to RTL is independently reviewed and simulated, not formally proved'), indent=2)+'\n')
    print('PROVED integer multiply lemmas; domains reachable; negative controls refuted; RTL linkage remains review/simulation')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'FAIL integer lemma: {exc}', file=sys.stderr)
        sys.exit(1)
