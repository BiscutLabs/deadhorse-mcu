# Boot release properties

Run `python tools/env/run.py run -- python hw/ip/boot_control/formal/check.py --output build/t28/formal-N`.
The output must be new. Each job keeps the existing120-second cap. Neither CI
tier is invoked. Positive jobs use unbounded ABC PDR; concrete BTOR witnesses
cover reachable states and reject actual RTL faults within12 sampled edges.
The witness depth is not a proof bound.

| Model | Properties | Assumptions / scope |
| --- | --- | --- |
| BootReleaseFormal | boot_seen recurrence; released recurrence; error recurrence; released implies boot_seen | Initially epoch reset low, then epoch/service reset and all inputs arbitrary; one AON clock |
| BootOwnerFormal | denied origin never releases; every response errors | Same reset model; generated MMIO and adapter; input origins restricted by construction to all seven denied tags |

The control recurrence checks service-reset retention, same-edge START/RELEASE
rejection and correct-key qualification. Initial and repeated whole-reset
clearing also has stopped-clock and whole-top simulation checks. It does not
claim image authenticity or current lite health. No software sequencing or
request-stability assumptions are used. The owner case proves only denied
owners; legal transactions are exercised by the independent bus oracle.

Faults bypass the prior-START check, key check and actual adapter owner check.
Covers exercise seen-before-release, service reset after release, an error,
denied response and START concurrent with a granted request. Receipt checks
assertion/assumption counts, concrete witnesses, expected failed property
identities, source/model hashes and solver return/status.

Reset pulses entirely between sample edges and analog recovery/removal are
outside this sampled proof. BootReleaseSpec separately exercises asynchronous
assertion with stopped clocks using the production shared ResetRelease.
BootControlSpec interrupts the transport before acceptance, after acceptance,
and after key-pulse generation before consumption, then checks no replay.
The whole-top test uses real loader wires and both actual cores. These digital
checks do not close physical RDC, pad reset or clock-tree qualification.

Current results and provenance are recorded in the T28 report and the formal
ledger. Earlier failed generation attempts and receipts stay under build/t28.
