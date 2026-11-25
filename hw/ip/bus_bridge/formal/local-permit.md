# LocalPermit (T42 / D108)

Production `toAon` has no opposing direction after PLAN05. Its local grant
samples `request` on the main clock, resets low and retains the four-phase
low interval required by BridgeSource. Qualified main reset is supplied by
the production top; this primitive adds no reset tree or crossing.

`LocalPermitFormal.scala` proves the actual production primitive's one-edge
request correspondence and reset-low behavior. The latter is observed on an
independent clock outside the resetting domain. Only assumption: reset is low
initially; subsequent reset, request and both clocks are arbitrary. There is
no requester/fairness/clock-ratio assumption. This is not a proof of the whole
bridge, FIFO, wake controller or physical metastability/reset timing.

`python hw/ip/bus_bridge/formal/local_permit_proof.py --output build/t42/local-proof01`
ran in the pinned environment on main f534b34 plus source-hashed D108 changes.
Two assertions proved unbounded with ABC PDR (measured 0.316023 s). Actual
stuck-high, extra-cycle and incorrect-reset-value faults failed the same
assertions; three covers exercise grant, revoke and regrant. Job cap remains
120 s, cover depth64. No timeout or new abstraction was required. See T42's
report/receipt for exact hashes, wall times and transport simulation coverage.
