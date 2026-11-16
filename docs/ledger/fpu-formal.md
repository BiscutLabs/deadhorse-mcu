# Standalone FPU formal ledger

T12 evidence is measured on base commit `3dfa92ea25cea14f3fde0ee0b3f318c849815285`
plus the T12 working tree, through the pinned Linux environment. Exact source
hashes are in `build/t12/result.json`; emitted-source cutpoint manifests are
in `build/t12/formal/*/abstraction.json`. Commands below use prefix
`python tools/env/run.py run --`. See [T12 report](../plan/tasks/reports/T12.md)
for the full acceptance and timing results. The subsequent canonical Git-blob/
line-ending correction is qualified by fresh compilation and byte-identical
emitted production RTL; `build/t12/provenance/result.json` binds the original
passing receipts to the corrected source hashes.

| Obligation | Command and result | Scope |
| --- | --- | --- |
| Instrumentation equals production | `python3 hw/ip/fpu/formal/check.py`: exact named-state binding proved; output, next-state and gained-reset faults rejected | All original state, outputs, enables and reset semantics, before arithmetic abstraction. Monitors are stripped for this comparison. No behavioral assumption. |
| Request capture, one outstanding transaction, registered handshake/busy, held response, cancel/abort, completion deadlines, post/round input stability and capture sequencing | Same command: ABC PDR PASS | **Unbounded control proof, arithmetic abstracted.** Initial-cycle reset is the only environmental assumption; subsequent reset, requests, operands, opcodes, rounding, cancel and response-ready are unrestricted. Busy need not end while a response is held; computation must present that response within its deadline. |
| Every operation plus a held response | Same command: 25 covers reached in a 44-frame search | Bounded witness search, fixed zero operands, legal rounding, one request, held response; terminal-frame search. |
| Cancel/reaccept, cancel at divider completion, cancel/request collision and held-response consumption | Same command: four covers reached in a 14-frame search | Bounded witness search, special-case DIV, valid/ready/cancel unrestricted. Old depth 12 missed the registered consumption cover at frame 12; the unchanged cover passes in the corrected window. |
| Normal DIV and SQRT completion | Same command: two covers reached in a 64-frame search | Bounded witness search with fixed 1.0/2.0 operands, legal rounding, one request and held response. |
| Response-after-cancel, corrupt-held-result, stalled-multiply-counter faults | Same command: all three rejected with counterexamples | BMC witnesses, depths 8/8/44 respectively. The stalled-counter witness fixes a concrete MADD request. These stimulus restrictions never enter the normal PDR proof. |
| Prefix addition | `python3 hw/ip/fpu/formal/check_add.py`: PASS, all five carry faults rejected | Unbounded combinational equality to ordinary modular addition at widths 25/26/28/32/51; no assumptions. |
| Serial multiplication recurrence | `python3 dv/fpu/arithmetic.py`: PASS, 24 integer steps and 24 faulty recurrences rejected | Integer arithmetic argument under 24-bit unsigned operand bounds, not full RTL multiplication equivalence. |

Measured elapsed times from `build/t12/formal/result.json`: normal PDR
16.831 s; operation covers 94.774 s; protocol covers 2.777 s; division covers
13.733 s; cancel fault 0.873 s; held-response fault 3.472 s; progress fault
7.681 s. The full formal command, including emission and production binding,
took 158.577 s. The adder command took 11.130 s and the integer recurrence
command 0.866 s, from `build/t12/result.json`. These are measured host run
times for the pinned environment and source snapshot above.

Arithmetic cutpoints are fresh unconstrained combinational values. State-holding
outputs/aliases, register enables, counters, valid/ready, resets and cancellation
remain original. The divider cut is `div.trialComputed`, before its actual
register. Missing cutpoints/properties, unmatched production state or missing
witnesses fail acceptance. Exact cutpoint and retained-alias lists accompany
each generated proof.

The multiplication argument uses P0=B and the invariant
Pk=floor(B/2^k)+A*(B mod 2^k)*2^(24-k), giving P24=A*B. The pre-shift sum needs
49 bits. This mathematical recurrence does not claim an end-to-end IEEE product
proof. The FMA sum is assembled over three 17-bit chunks with carried carry;
result correctness remains independently reference-tested.

The divider trial subtracts unsigned operands of at most 27 bits, so its
difference fits signed 28 bits. The exact prefix-adder proof qualifies that
subtraction; the cached next-loop term is captured with the updated quotient
and fraction state. The full modified divider and rounding algorithm are
reference-tested, not labeled formally equivalent IEEE arithmetic.

The complete FPU reference sweep is sampled, not exhaustive. Formal control
does not replace result/flag comparison against TestFloat/SoftFloat and the
pinned RISC-V simulator. Processor integration is outside this ledger.
