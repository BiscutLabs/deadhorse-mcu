# PLAN03 verification-debt attempt

One focused, authorized B5 attempt per task, on the unchanged production RTL
of main 736ed5c (B4 documentation/source-snapshot commit 58833fd does not change
these models). Every number below is **measured** by the commands below; source,
model, configuration and artifact hashes identify the exact executed snapshot.
No RTL, assertion, assumption, bound or solver cap changed. Each solver retains
the existing 120-second cap; wall times include process/setup overhead.

## Method and scope

DMA uses Z3 induction on only the remaining range assertion; prior aggregate
Yices/suprove/ABC and singleton ABC attempts are preserved, not rerun. Lite ADDI
and watchdog use exact partitions of all 14/12 original assertions on the concrete
model, one ABC PDR job per assertion. Deleted siblings are never assumed.
`opt_clean` removes dead cones only. No new cutpoints or helper invariants.
This is one new focused rung under PLAN03, not a reset of the historical ladder.

Fresh emission matches every original correct, cover and faulty variant byte
for byte. Read-only audits authenticate original configuration templates,
source copies used by solvers, reset assumptions, return codes, actual property
names, concrete cover witnesses and intended fault IDs against the historical
receipts. Positive partitions are checked against their actual status tuples
and prepared assertion/assumption inventories. No timed-out job is rerun to
authenticate it. All measurements and audit exports remain under build/plan03.

All three models restrict reset only initially; later inputs/resets are
arbitrary. DMA/lite have one initial reset assumption, watchdog has initial
POR and normal reset (two). No fairness, input-rate or internal-state assumptions
are added. ADDI uses the same pinned riscv-formal model and defines. Memory
address and four store-byte predicates are trivial for ADDI's zero masks;
their passes are not five extra instruction proofs.

Existing actual faults exercise DMA origin (index 1, not range), lite next-PC
(index 5), watchdog crash count (early/retention faults, index 1) and hold duration
(index 3). They do not individually qualify every new singleton proof. Solver
PASS below means unbounded claim proved on this model; complete fault-qualified
block/ISA acceptance remains open. No full RF/CSR/interrupt correctness follows.

## Original assertion accounting

DMA's other nine engine assertions and seven wrapper-denial assertions already
proved and were not rerun. The remaining range job is included below. All ADDI
and watchdog assertions appear exactly once.

| Task | Index / original claim | Result | Engine | Wall seconds |
| --- | --- | --- | --- | ---: |
| dma | 3: Memory offer within performance SRAM | unresolved (TIMEOUT) | smtbmc z3 | 122.107791 |
| lite | 0: Trap classification | proved; fault scope above | abc pdr | 1.217072 |
| lite | 1: rs1 address | proved; fault scope above | abc pdr | 1.167267 |
| lite | 2: rs2 address | proved; fault scope above | abc pdr | 1.166318 |
| lite | 3: rd address | proved; fault scope above | abc pdr | 1.166910 |
| lite | 4: Destination data | unresolved (TIMEOUT) | abc pdr | 121.345359 |
| lite | 5: Next PC | proved; fault scope above | abc pdr | 13.679837 |
| lite | 6: Memory address (trivial for ADDI) | trivial for ADDI | abc pdr | 1.117029 |
| lite | 7: Read mask zero | proved; fault scope above | abc pdr | 1.216275 |
| lite | 8: Write mask zero | proved; fault scope above | abc pdr | 1.216641 |
| lite | 9: Store lane0 (trivial for ADDI) | trivial for ADDI | abc pdr | 1.166261 |
| lite | 10: Store lane1 (trivial for ADDI) | trivial for ADDI | abc pdr | 1.166246 |
| lite | 11: Store lane2 (trivial for ADDI) | trivial for ADDI | abc pdr | 1.165892 |
| lite | 12: Store lane3 (trivial for ADDI) | trivial for ADDI | abc pdr | 1.416749 |
| lite | 13: Trap writes zero | proved; fault scope above | abc pdr | 1.667285 |
| watchdog | 0: Cause sticky | proved; fault scope above | abc pdr | 0.365224 |
| watchdog | 1: Crash count | unresolved (TIMEOUT) | abc pdr | 121.140678 |
| watchdog | 2: Expiry holds reset and cause | unresolved (TIMEOUT) | abc pdr | 121.137226 |
| watchdog | 3: Reset-hold duration | proved; fault scope above | abc pdr | 0.366098 |
| watchdog | 4: Active iff remaining nonzero | proved; fault scope above | abc pdr | 1.416800 |
| watchdog | 5: Remaining <= captured period | unresolved (TIMEOUT) | abc pdr | 121.234406 |
| watchdog | 6: Warning threshold | unresolved (TIMEOUT) | abc pdr | 121.385230 |
| watchdog | 7: Expiry stops active | unresolved (TIMEOUT) | abc pdr | 121.193416 |
| watchdog | 8: Feed reload | unresolved (TIMEOUT) | abc pdr | 121.290008 |
| watchdog | 9: Countdown decrement | proved; fault scope above | abc pdr | 1.516364 |
| watchdog | 10: Error on start | proved; fault scope above | abc pdr | 0.365644 |
| watchdog | 11: Legal start | unresolved (TIMEOUT) | abc pdr | 121.754450 |

## Step-0 table for remaining claims

Prepared statistics use Yosys `read_rtlil .../model/design.il; stat; write_json`;
the audit sums actual sequential Q widths (including `$ff`/`$anyinit`) and cells.
These are formal model statistics, not synthesis area. Historical growth and
cover measurements are retained from the block ledgers without unchanged reruns.

| Task / assertion | Cells / sequential bits / memories | Requested depth | Reached / diagnosis |
| --- | --- | ---: | --- |
| dma 3 | 833 / 459 / 0 | 36 | Z3 basecase checking step 18; arbitrary-state induction fails, not a reachable counterexample |
| lite 4 | 899 / 978 / 0 | 32 | ABC PDR maximum observed frame 4; no reachable counterexample |
| watchdog 1 | 131 / 269 / 0 | 20 | ABC PDR maximum observed frame 5; no reachable counterexample |
| watchdog 2 | 121 / 206 / 0 | 20 | ABC PDR maximum observed frame 5; no reachable counterexample |
| watchdog 5 | 87 / 137 / 0 | 20 | ABC PDR maximum observed frame 7; no reachable counterexample |
| watchdog 6 | 107 / 170 / 0 | 20 | ABC PDR maximum observed frame 4; no reachable counterexample |
| watchdog 7 | 120 / 205 / 0 | 20 | ABC PDR maximum observed frame 5; no reachable counterexample |
| watchdog 8 | 124 / 205 / 0 | 20 | ABC PDR maximum observed frame 5; no reachable counterexample |
| watchdog 11 | 103 / 205 / 0 | 20 | ABC PDR maximum observed frame 3; no reachable counterexample |

| Historical diagnostic | Quarter / half-depth measured growth | Concrete cover evidence | Logic remaining in the hard cone |
| --- | --- | --- | --- |
| DMA aggregate | BMC9:1.168 s; BMC18:5.125 s, bounded | First bounds 4,6,7,9,18 | 32-bit cursor, 16-bit remaining count and offer relation; no RAM |
| Lite concrete ADDI | BMC8:0.566 s; BMC16:1.116 s, bounded | Successful and trapping ADDI first k6 | RF/operand history and retirement result relation |
| Watchdog original aggregate | BMC5:0.416 s; BMC10:9.874 s, bounded | Original first bounds 4,4,4,9,10; corrected full-width cover witnesses authenticated | Countdown, captured settings, retained count and checker history |

Original model figures and historical attempts are in the
[DMA](../ledger/dma-formal.md), [lite](../ledger/lite-core-formal.md) and
[watchdog](../ledger/watchdog-formal.md) ledgers. No shallow result substitutes
for an unresolved positive claim.

## Next smallest changes, not attempted

- DMA: separately prove cursor + remaining × stride stays within SRAM, plus
  selected/offer consistency, before discharging the original range assertion.
- Lite: prove the retirement/saved-operand/result relationship; RF consistency
  and full machine semantics remain separate. Do not assume the desired data.
- Watchdog: prove checker captured-settings/active-register and retained-count
  relations; retain independent reset semantics and all original claims.

These are helper-invariant work under triage rung 6 and need a separately
approved scope/time box. PLAN03 stops these properties here and continues B6.
No larger sweep, new solver cap, assumption or RTL restructuring is proposed.

## Commands and evidence

Commands use `python tools/env/run.py run --`:

```text
python dv/soc/plan03_debt.py --case dma --output build/plan03/debt01/dma
python dv/soc/plan03_debt.py --case lite --output build/plan03/debt01/lite
python dv/soc/plan03_debt.py --case watchdog --output build/plan03/debt01/watchdog
python dv/soc/plan03_debt_audit.py --case dma --input build/plan03/debt01/dma --output build/plan03/debt01/audit02-dma
python dv/soc/plan03_debt_audit.py --case lite --input build/plan03/debt01/lite --output build/plan03/debt01/audit02-lite
python dv/soc/plan03_debt_audit.py --case watchdog --input build/plan03/debt01/watchdog --output build/plan03/debt01/audit02-watchdog
```

Positive runners return 1 for unresolved partitions; that is recorded, not a
passing aggregate. Audits return 0 only for consistent evidence. DMA's executed
runner is archived with its receipt hash; subsequent tooling added the pinned
ADDI reference-file hash before running lite, without changing DMA's solver
model or configuration. Initial audit exports remain; audit02 adds reviewed
status/name/imported-source/diagnostic-hash guards without rerunning solvers.
