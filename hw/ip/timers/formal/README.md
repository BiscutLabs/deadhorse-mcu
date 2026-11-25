# General-timer properties

`python hw/ip/timers/formal/check_general.py --output build/plan05/timer-formal-N`
checks all twelve channels in production GeneralTimers, with formal-only monitors.
Initial reset is asserted; resets, LocalBus, capture inputs/qualification and DMA
acknowledgements are arbitrary thereafter. One main clock, no software assumptions.

The50 assertions check that active compare changes only while stopped, starting
or at period rollover; capture stores effectiveTime at the qualified edge; and
output values/enables register their specified controls. They are not a complete
independent functional timer model. Independent simulation checks every mode,
all channels, pulse widths/periods, capture timestamps and boundary updates.
Two additional assertions preserve exact timebase progression/load and the complete clock-hold recurrence. Both8 and9MHz parameters are proved. Watchdog gating is separately tested.

Measured on main29cab7e5 plus receipt-hashed sources with output
`build/plan05/timer-formal03`: positive ABC PDR proof2.522s; early-adoption,
output-inversion and timestamp-corruption negative controls rejected; all12
covers reached. The120-second cap and all assertions remain intact. Earlier
emitter-dependency and hierarchical witness-name bookkeeping failures are retained.

The later `build/plan05/timer-formal04` receipt proves both clock parameters,
rejects time/hold corruption plus the prior three faults, and reaches all12
covers. `check_aux.py --output build/plan05/timer-aux01` proves the unchanged
five DMA-request and seven denied-origin claims, with covers and faults.
`hw/ip/watchdog/formal/check.py --cases break pad` binds its recurrence to
production TimerBreak and the shared timer pin routes; no watchdog-width
proof rerun is implied. Full functional correctness remains simulation scope.
