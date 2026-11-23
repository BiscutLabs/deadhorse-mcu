# T32 evidence refresh producers

Exact authored Python producer snapshots, not generated proof or measurement
results. Run from the repository root in the pinned environment. Their historical
input/output paths intentionally match the receipts; use fresh paths for a later
replay and record path-only adaptations. Do not overwrite historical results.

- `t32_debug_binding.py`: fresh local/epoch emission identity, no solver run.
- `t32_usb_rebind.py`: fresh USB/observer emission and canonical replay; reuse
  authenticated, unchanged sampling proof jobs with explicit historical metadata.
- `t32_usb_fullsize.py`: full-size throughput and actual slow-service fault.
- `t32_usb_preflight.py`: sampling archive and strict packet/sampling collectors.
  Its first physical collection deliberately remains failed evidence of stale inputs.
- `t32_usb_physical_bind.py`: derivation of a compatible seal for historical
  internal physical results. Its original-lock reconstruction used the pre-T32
  `HEAD` (9b80375109826e41d28cae95b1b80c653bfc34ff); use that explicit commit on
  later replay. Exact historical CRLF hash is required. It does not requalify the
  changed production bus context by itself; its collector failure is preserved.
- `t32_usb_boundary_refresh.py`: fresh both-way production wiring, source Q and
  reset-release/endpoint-gate audit, fresh CQ-table extrema, exact composition
  identity, then new hold/two-way STA on the authenticated historical placement.
  Its final strict collector is the acceptance-input preflight. No collector changes.
- `t32_usb_verifier_rebind.py`: exact historical-source derivation after the three
  reviewed I2C verifier changes. Authenticates original Git bytes, unchanged HDL,
  graphs, libraries and timing artifacts; retains original receipts and explicitly
  labels every numerical result historical. Preflights the unchanged packet,
  sampling and physical collectors. No RTL, solver or physical run is represented
  as fresh by this derivation. Later-added debug proof/replay scripts are separate
  from the historical production-source inventory.
- `t32_floating_buffer.py`: historical diagnostic for final-fast03's faithful-core
  timing failure. Rebuilds one mapped identity-buffer tree, audits exact functional
  connectivity plus wrong-pin/cycle faults, then runs unchanged STA. The candidate
  still fails timing and is not a maintained mapping flow or accepted repair.
- `t32_floating_buffer_general.py`: second diagnostic balancing eligible deep
  data-buffer forests while protecting clock/reset/gate-control and exported
  outputs. Exact graph audit passes but setup worsens; this is rejected evidence,
  not a production mapping policy.

Dependencies remain explicit: original immutable PLAN03/T19 receipts, their sealed
mapped/placed artifacts, pinned libraries, and current `build/t32/replay02` emission
and graph. This is evidence reuse, not clean synthesis/place-and-route from only
these scripts. `../replay.py` supplies the fresh production area/measurement entry
point. Numerical measurements and acceptance limits are in the T32 report.
