# Direction permit verification

`DirectionPermitFormal` instantiates the production two-clock `DirectionPermit`,
including its shared reset-release and synchronizer primitives. Both clocks and
both resets are independent. The only initial constraint asserts both external
resets; resets are unrestricted afterward. Requester reference machines implement
the specified four-phase protocol: hold a request through grant observation,
release on completion or withdrawal, and observe permit low before requesting
again. Demand and completion inputs are otherwise arbitrary. No clock-frequency,
clock-progress or completion fairness assumption is used in the safety proof.

The wrapper assertions check actual output non-overlap in both clock domains and
reset clearing through an independent unconstrained observation clock. Covers
reach both turnover directions and a waiting main request while its clock is low.
The negative control changes the production arbiter's allocation condition to
ignore its revocation interlock. The same port checks must reject the resulting
overlap; the checker does not corrupt observations.

`DirectionArbiterFormal` separately checks the production AON state machine with
arbitrary request and returned-acknowledgment ports. It checks mutual exclusion,
retention while the owning request is asserted, no second turn for an owner while
the other request remains pending, and allocation before four eligible AON edges
elapse. An eligible interval has a request, neither grant, and returned main
acknowledgment low. The four-edge limit is an assumed verification bound proved
for this implementation, not a physical-time claim. A second actual RTL mutation
disables main priority and must fail the turn-taking property.

These are unbounded safety proofs, including a finite-response invariant. They
are not an unconditional wall-time liveness result. Eventual service additionally
requires continuing clocks, the current owner finishing, and the specified
four-phase requests. Those premises let the shared synchronizers complete the
acknowledgment exchange; the arbiter then allocates within its eligible-edge
bound without starving the other pending direction.

Run in the pinned environment:

```
python3 tools/sbt.py "hw/testOnly deadhorse.bus_bridge.DirectionPermitSpec"
python3 hw/ip/bus_bridge/formal/direction_permit_proof.py --output build/t14/direction-proof-01
```

The independent simulation owner model checks alternating turns, held ownership,
stopped-main-clock revocation, restart, no-work withdrawal, reacquisition and
asynchronous reset of either side. Its assumed timeout is 96 AON ticks with main
running once per three ticks during progress waits; the stopped interval is
intentional and excluded from those waits. It runs unchanged against the actual
revocation-interlock mutation and requires rejection.

Measured in this session by the commands above, at baseline commit
`b4680a4529ad629fc4e3577ee42fa83e45e6943d` plus the T14 working changes, on the source hashes recorded in
`build/t14/direction-proof-01/result.json`: both simulation tests pass; both PDR
proof groups pass; the three wrapper covers and two arbiter covers have witnesses;
both actual RTL mutations fail with counterexample witnesses. The driver retains
exact assertion/cover counts and uses a 120-second solver ceiling per job. Results
remain configuration- and source-specific. The top-level T14 report records the
repository commit and complete acceptance evidence.
