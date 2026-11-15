# Integer argument for the fast multiplier (D44)

`mul_lemma.py` uses the pinned Z3 executable, not a Python solver installed
outside the environment. `result.json` records each query's result/runtime;
the SMT2 queries and logs are saved beside it. A timeout, unknown result or
unexpected satisfiability result fails the command.

## Statement and domains

Exact mathematical definitions: `q = 2^16`, `W = q^2 = 2^32`.
Let `A = al + q*ah`, `B = bl + q*bh`. Low limbs are integers in `[0,q-1]`.
Unsigned high limbs are in `[0,q-1]`; signed high limbs in `[-q/2,q/2-1]`.
These are the only limb-domain assumptions. MUL uses unsigned limbs because
low-product bits are independent of signed interpretation. MULH uses both
signed high limbs, MULHSU only signed `ah`, and MULHU both unsigned.

The reviewed correspondence to `gen_mult_fast` in the pinned
`hw/vendor/ibex_ref/rtl/ibex_multdiv_fast.sv` is:

```text
p00 = al*bl    p01 = al*bh    p10 = ah*bl    p11 = ah*bh
ALBL: p00
ALBH: t = p01 + floor(p00/q)
AHBL: u = t + p10                  (high-product path)
AHBH: v = p11 + floor(u/q)
P = p00 + q*(p01+p10) + W*p11 = A*B
```

For high-product instructions, `v = floor(P/W)` and the result is `v mod W`.
For MUL the ALBH packed intermediate preserves `p00 mod q` and `t mod q`;
the final packed result is:

```text
(p00 mod q) + q*((p10 + (t mod q)) mod q) = P mod W
```

SMT integer division by positive `q` is floor division, including negative
numerators. C/Scala truncation toward zero would be wrong here.

## Proof decomposition

For each signedness mode, Z3 checks a satisfiable limb domain, the exact
polynomial expansion, a deliberately wrong cross-term shift, intermediate
ranges and a deliberately wrong range. It proves that `p00` fits unsigned
32 bits, `t/u/v` fit signed 34 bits, and `floor(u/q)` fits signed 18 bits;
in unsigned mode `u` is nonnegative. These obligations justify the reviewed
MAC truncation and AHBH upper-slice/sign-extension interpretation.

Separate universal integer carry lemmas treat `p00/p01/p10/p11` as arbitrary
integers and prove the low/high formulas above. They assume no product
equality: the already proved expansion supplies the arithmetic interpretation.
Each carry lemma has a satisfiable domain and a corrupted result/shift that
must be refuted. All positive claims require UNSAT for the negated property;
all negative controls and domain checks require SAT.

## Limits

This proves mathematical statements, not equivalence between these equations
and emitted RTL. That link is independently reviewed against the immutable
reference and exercised by the required fixed-seed `mul_diagnose.py` run.
ALTOPS separately checks bounded core integration and live operand stability.
The optional shared arbitrary-function frontend attempt did not reach a valid
model, so this review/simulation limitation remains. The unabstracted
end-to-end instruction proof remains an unresolved on-demand diagnostic.
