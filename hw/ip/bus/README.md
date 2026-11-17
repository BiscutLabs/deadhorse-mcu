# Local request/response fabric (T14)

Status: implementation in progress. Contract: [bus specification](../../../docs/spec/bus.md).
Single clock, asynchronous active-low reset supplied with synchronous release.
One transaction outstanding globally; round-robin arbitration among eligible
masters. Region base/size pairs are disjoint and aligned powers of two.
An endpoint may still reject a request using its ownership/memory policy.
Trusted origin travels with the payload; integration owns origin assignment.

`admit` gates new selection per target (the crossing direction permit for a
bridge). Denied bridge candidates do not reserve a slot. `allow` is per-master
policy at local grant. Misalignment, unmapped and denied requests return errors.
`waiting` reports offered work per target, registered, for admission/wake.
`completed` pulses per target after a local response (including timeout); bridge
permit release additionally requires the bridge's transport-abort acknowledgement.

Registered request/grant/response outputs break combinational chains. The
requester holds req and payload until grant. Targets respond at least one edge
after target grant. `limits` count edges from local master grant through return;
local defaults128; a bridge region uses its inner watchdog plus8 (131080 for
the baseline bridge). Completion on final edge wins. Timed-out slots
are quarantined until a late response drains or `quiescent` acknowledges no old
work remains; other targets are serviceable. Reset requires external endpoint
isolation before `admit` enables an independently reset target.

Control reset values: idle, no grants/responses/requests, priority0, no quarantine.
No endpoint side effects are implemented here. Preliminary area target is part
of T14's assumed0.05mm2 combined fabric/bridge/mailbox; measurement is pending.
Formal input assumptions and exact configurations will accompany results.
