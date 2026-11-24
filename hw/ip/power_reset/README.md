# Power/reset control

T33 work in progress. This AON block adds reset-reason reporting and brownout
threshold control at 0x40000500, owned by the lite core. It uses the shared
registered bus adapter and generated register block; no peripheral map moves.

| Offset | Register | Meaning |
| --- | --- | --- |
| 0x00 | reason | RO: bit0 POR, bit1 brownout, bit2 external pin, bit3 performance watchdog, bit4 lite watchdog |
| 0x04 | threshold | RW two-bit shadow selector, reset00 |
| 0x08 | apply | WO full-word key0x42524f57; reads0 |
| 0x0c | active | RO applied two-bit selector |
| 0x10 | events | W1C bit0 invalid key/selector; set wins clear |

Reason reflects the existing cold-retained sources, sampled on AON. A cold
epoch initially reports POR (pin in POR_BYPASS); a held brownout replaces the
provisional POR classification. Pin/watchdog history persists until cold reset.
Performance watchdog does not reset this block. The loader retains its existing
two-bit watchdog reason ABI and crash counter. Reason is not software-clearable
because its upstream cause sources are sticky.

Only selector00 and01 apply; reserved10/11 and wrong keys set error without
changing the active setting. A single registered bit drives the macro selector;
its other bit is tied low. The bus/configuration and active setting reset to
safe00 with AON service reset. Existing modeled voltage thresholds remain
assumptions, not qualified silicon limits. The approved macro contract forbids
unsafe release pulses during switching, asserts immediately below the new
falling threshold, and requires the full rising-threshold release qualification
after assertion. Supply that remains valid may stay released. Physical validation
belongs to T34; a digital selector/model cannot establish analog safety.

All public data/control outputs are registered (selector high bit is constant).
Bus handshake is supplied by shared wrappers. No new CDC is introduced inside
this block: cause inputs are already AON signals; the analog selector follows
the reviewed macro interface. Area uses the remaining shared clock/reset/power
allowance, not a new allocation. Local MMIO tests and the unbounded keyed-selector
proof pass on the receipt-hashed working tree at 2c33976. Mapped integrated
timing and the planned finite production reset-phase tests also pass their
scoped checks. T33 is complete with D86 exceptions after focused acceptance and
independent review (see the T33 report). Expensive composition proofs remain
deferred and unproved; CDC/RDC, physical reset distribution and the I3 gate
remain unqualified. Aggregate CI was not run. The report discloses an inherited
unrelated I/O test accidentally executed before the corrected scoped run.

Formal assumptions: reset is asserted initially; later resets, key, apply and
selection inputs are arbitrary on a single AON proof clock. No legal-key or
legal-selector assumption is used. Actual key-bypass faults are rejected and
both selector-transition covers are reached. `formal/check.py` also checks
unmaskable reset-demand behavior in the production oscillator policy. These
local proofs do not establish CDC/reset composition or the analog guarantee.

T33's structural reconciliation accounts for every mapped crossing origin and
retains missing/merged state aliases and non-FF storage explicitly. The direct
shared ResetRelease proof is attached only where the production child HDL is
identical to the freshly sealed proof child. This is a local source guarantee,
not reset-tree, mapped transition or CDC/RDC signoff. Missing STA reset paths
originate at untimed raw reset inputs and remain unqualified. See the task
report and `docs/ledger/power-reset-formal.md` for the commands and limits.
