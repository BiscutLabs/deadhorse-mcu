# T19 USB formal ledger

All results below are **measured**, using the pinned environment at Git base
`a280df4fa17516a2ac8507628a6f12e3c4128895` plus uncommitted T19 sources.
Emitted source hashes in each receipt identify the actual checked model.
They do not certify later source changes. T19 remains incomplete.

Commands below are prefixed with `python tools/env/run.py run --`.

| Contract | Actual result | Receipt / command |
| --- | --- | --- |
| Byte-width shared FIFO ordering, retention, reset and Gray/release safety | Unbounded ABC PDR pass; reachable covers and data/Gray/reset faults rejected | `python3 hw/lib/formal/cdc_proof.py --width 8 --depth 2 --output build/t19/formal-cdc-01` |
| Production four-sample cadence | Unbounded ABC PDR pass; cover and early-enable fault pass | `build/t19/formal-02/cadence/`, from `python3 hw/ip/usb/formal/check.py --json build/t19/regmap/usb_regs.json --output build/t19/formal-02` |
| Non-owner accesses cannot produce side effects | Unbounded ABC PDR pass; covers and bypass-owner fault pass | `build/t19/formal-02/denied/`, same command |
| Reduced-threshold host-resume capture/retention | Unbounded ABC PDR pass; cover and dropped-wake fault pass | `build/t19/formal-resume-final/resume/` |
| EP0 address/configuration side-effect qualification | Unbounded ABC PDR pass; reachable address/configuration/replacement-SETUP covers and premature-status fault pass | `build/t19/formal-control-final/control/`; this does not establish packet-boundary phase equivalence |
| Raw reset/VBUS pad safety | Unbounded ABC PDR pass; active-reset cover and ignored-reset fault pass | `build/t19/formal-lane-01/pads/` |
| Retained SIE register-enable implication | Yosys SAT pass with arbitrary register values/PHY outputs; always-enabled prepared-register fault rejected | `python3 hw/ip/usb/formal/sie_enable.py --output build/t19/sie-enable-03` |
| IN accepted-byte integrity, replay/commit, stability and service | **Unresolved**; full-byte and lane-zero proofs timed out | `build/t19/formal-in-01/`, `formal-portfolio-01/in/`, `formal-in-lane-02/in_bit0/` |
| OUT packet commit/rollback, byte integrity, stability and service | **Unresolved**; full-byte and lane-zero proofs timed out | `build/t19/formal-out-01/`, `formal-portfolio-01/out/`, `formal-lane-01/out_bit0/` |

The packet-buffer covers reached concrete witnesses, and planted missing
commit/publish faults produced counterexamples. The latest IN lane-zero job
also reached its service cover and rejected permanently withheld valid.
These are not substitutes for the unresolved positive proofs. One bit lane
does not establish byte-wide integrity; the other lanes were not swept after
lane zero timed out.

## Timeout diagnosis

The initial ABC PDR jobs retained the existing 120-second solver cap. The
portfolio added Z3 induction without changing assertions, assumptions or the
cap. The final cone-reduction diagnostic checks one named data bit while
retaining the actual byte-wide RTL and all control assertions; it also timed
out. No timeout is accepted as a deferral or a bounded proof.

Measured prepared original models contain 304 cells/nine memories (IN) and
316 cells/nine memories (OUT), from independent pinned Yosys `stat -width`
inspection of the preserved `design_prep.il`. The symbolic oracle removes the
need for a second full reference RAM, but the DUT RAM remains in the proof.
For the IN portfolio, Z3 basecase logs reach step twelve in under a second,
step twenty-four around seven seconds, and step thirty-five around 108
seconds; these are solver log timestamps, not separate completed BMC jobs.
Initial IN cover witnesses reach at most twenty-three steps; OUT at most
seventeen. No bound was reduced or reported as unbounded.

Further proof engineering needs an explicit scoped plan under the formal
timeout-triage workflow: separate the control/service conjunction from
integrity, and consider independently proved helper invariants or a sound
arbitrary-entry abstraction. Freeing RAM data for a byte-equality assertion,
assuming DUT valid, increasing the timeout, or dropping an assertion is not
an acceptable repair.

See [the harness contract](../../hw/ip/usb/formal/README.md) for every input
restriction and abstraction. Digital proofs do not establish analog CDC,
physical reset recovery, USB electrical compliance or whole-system wake.
The SIE certificate alone does not authorize multicycle timing.
