# T18 recovery loader formal ledger

Historical evidence: PLAN05 D93 removes this block; these results do not qualify
the replacement performance-ROM recovery path. Its source remains in git history.

Base `35738fe` plus the T18 sources identified by the aggregate receipt. The
historical `hw/ip/i2c_recovery_loader/formal/README.md`
records the external stimulus, environmental restrictions and fault controls.
The production control uses 2048-byte program and 1024-byte working-memory
configurations in these jobs.

| Obligation | Method | Scope |
| --- | --- | --- |
| Lock retention, write admission and validated start | Unbounded SMT temporal induction with reset base case | Arbitrary frame payloads, resets, memory ready/done, halt and interrupted-frame input at the clocked control boundary |
| Data and completion accounting | BTOR bounded model checking, 90 service edges | One four-byte upload, two distinct data choices, four possible completion edges, early/duplicate completions, malformed and out-of-order writes, SELECT at completion, VERIFY, locked start and warm reboot |

The safety check proves additional invariants for aligned count, accepted
length, LOADING state and pending work. Every strengthening predicate is an
assertion. The environment starts in POR and may assert POR again. The reset
controller asserts the ordinary reset for either cold or warm causes. A
separate cold-only reset drives the lock. No performance reset reaches this
lite block.

Concrete safety covers exercise a memory grant, locked start and a locked,
invalid image following warm reboot. Accounting covers exercise the endpoints
of the scripted data/completion choices. The actual mutations change the
lock flop to clear on warm reset and double the Stored byte-count increment.
The checks require counterexample traces for both.

The first arbitrary-input ABC PDR attempt timed out at 120 seconds
(`build/t18/formal-pilot`). An induction attempt passed the base case but
found an unreachable LOADING state with the image marked programmed in the
inductive step (`build/t18/formal-induction`). Additional checked state
invariants resolved the induction gap. The original safety obligations, full
production capacity and solver timeout remain intact. Wire framing, physical
CDC behavior, SRAM implementation and arbitrary-length CRC correctness are
outside this proof. The separate pin-level simulation exercises complete
multiword uploads against a Java CRC32 oracle.

## Acceptance evidence

Measured on the sources identified by the aggregate receipt at base
`35738fe`, using `python3 hw/ip/i2c_recovery_loader/check.py --output build/t18/check`
in the pinned environment. The standalone formal receipt is
`build/t18/check/formal/result.json`. The fast CI replay reproduced every
outcome. Both runs retained witnesses for the covers and rejected mutations.

| Standalone job | Outcome | Measured seconds |
| --- | --- | ---: |
| T18-SAFETY-COVER | covered | 0.566 |
| T18-SAFETY-CORRUPT | fault_rejected | 1.016 |
| T18-SAFETY-CORRECT | proved | 0.816 |
| T18-ACCOUNTING-COVER | covered | 0.866 |
| T18-ACCOUNTING-CORRUPT | fault_rejected | 1.016 |
| T18-ACCOUNTING-CORRECT | bounded | 3.519 |
