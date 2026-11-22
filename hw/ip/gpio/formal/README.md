# T21 GPIO properties

`python3 dv/soc/check_io_formal.py --output build/<fresh> --cases wake gpio_denied`
runs the focused checks in the pinned environment, without CI.

Wake safety checks acknowledgement, sticky pending until clear, explicit
APPLY+CLEAR disarm, and a newly applied matching level. Covers exercise wake
and disarm. Inverting the actual pending output must fail a pending assertion.
Later ordinary level detection and clear-vs-active-level priority also have
pin simulation tests; these are not claimed as complete wake liveness proofs.

Denied-owner checks cover every non-owner tag (input0 maps to1, owner0), arbitrary
bus/pin inputs, immediate denial response and unchanged outputs/enables/IRQ/wake.
Bypassing the owner test must fail response or state assertions. Both clocks
are tied for this safety proof; shared CDC qualification and asynchronous
simulation cover the transport separately, not through an invented fairness
assumption. Initial reset low, arbitrary thereafter, is the only formal assume.

ABC PDR is unbounded; cover/fault witnesses are finite, under a 120-second cap.
Exact property and assumption inventories, source/model hashes and concrete
witness validation fail closed. No analog metastability or physical timing claim.
