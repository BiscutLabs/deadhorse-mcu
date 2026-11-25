# T24 limited output pin mux proofs

Measured command on `72bcfac` plus local source hashes:

```sh
python tools/env/run.py run -- python3 hw/ip/pinmux/formal/check.py --output build/t24/formal-frozen
```

Receipt `build/t24/formal-frozen/result.json`: PASS. The production pad and
register wrapper use their full widths. The receipt binds 34 source hashes
and 348 artifact hashes, including each emitted correct/fault/cover model.
Times below are measured runner wall time per solver invocation, not estimates.

| Job | Assertions | Result / engine | Measured seconds | Covers / depth | Actual fault / result |
| --- | ---: | --- | ---: | --- | --- |
| pad | 9 | proved, ABC PDR | 0.265 | 5 reached, depth8 | stuck-high output enable rejected |
| reset | 4 | proved, ABC PDR | 0.266 | 2 reached, depth8 | enable flop resets high, rejected |
| denied | 5 | proved, ABC PDR | 0.366 | 1 reached, depth16 | owner check bypassed, rejected |

All cover/fault jobs use btormc. These are finite witnesses, not bounded
substitutes for the positive proofs. No timeout occurred and no triage rung
was needed. The 120-second cap remains unchanged.

Assumptions: initially asserted reset, arbitrary thereafter, one digital
main clock. Denied transactions map owner1 to origin0 while all other tags
are preserved, covering every non-owner. No other input restrictions, helper
assumptions, reduced-width models or memory abstractions.

The pad proof independently remembers prior selections/data/enables and checks
sampled output behavior. The reset monitor uses constant-false monitor reset,
so its assertions remain active while the production reset is asserted. It
checks sampled digital reset outputs after asynchronous-reset conversion;
inter-edge reset behavior is tested by stopped-clock simulation. Top-level
reset wiring, clock retention and raw GPIO input/wake composition are simulation
claims, not these standalone proofs. No analog, physical hold/RDC or pad timing
claim follows from them.

Independent source review identified the original reset-monitor gap; the
explicit reset job and actual reset-value fault above close it. Review also
checked clock-demand continuity, source ordering, profile isolation and the
corrected timer fixture. The first integration fixture failure is retained
in `scratch/t24-integration-first.log`; mode values were corrected to the
documented compare/OE configuration without changing RTL behavior or checks.

## T43/D110 physical pad boundary, 2026-11-25

Command (pinned environment):
`python phys/gf180-ws-1x1/dv/pad_boundary.py --output build/t43/pad-boundary04`.
Receipt baseline is `721027d` plus the source hashes in that receipt. The scalar
combinational `chip_pad_feedback` instance is proved by Yosys SAT with every input
unconstrained: IE/OE exclusivity, requested drive/data preservation, local
feedback while driving and receiver feedback while released. No assumptions,
state induction or sequential depth. **Measured** positive solver command time
is 0.073983 s. Three negative controls (illegal enables, raw receiver while
driving, inverted output) all fail the same assertions as required.

The same runner passes four-state Icarus checks against the original foundry
pad model and the build-only disabled-pull compatibility model. It covers
released input, output, external contention and open-drain low/release/stretch.
The scalar proof is not a whole-chip temporal, strength, specify or USB
electrical proof. Existing pinmux/GPIO core-port tests and properties are
unchanged; D110 explicitly changes only driven-pad external readback semantics.
Independent review checked the proof, mutants and original/patched simulations.
