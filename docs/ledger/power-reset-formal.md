# Power/reset formal evidence

T33 local evidence on `2c33976` plus the receipt-hashed working tree.
Measured command:

```
python tools/env/run.py run -- python hw/ip/power_reset/formal/check.py --output build/t33/power-reset-formal02
  -> selector-proof proved; selector-negative fault_rejected; selector-cover covered
  -> demand-proof proved; demand-negative fault_rejected; demand-cover covered; PASS
```

| Job | Kind | Engine | Measured seconds |
| --- | --- | --- | ---: |
| selector-proof | proved | abc pdr | 0.316330 |
| selector-negative | fault_rejected | btor btormc | 0.315797 |
| selector-cover | covered | btor btormc | 0.315650 |
| demand-proof | proved | abc pdr | 0.365752 |
| demand-negative | fault_rejected | btor btormc | 0.365848 |
| demand-cover | covered | btor btormc | 0.365750 |

Selector assertions establish legal active encoding, exactly keyed updates,
invalid-command reporting, and reset-to-default. The actual key bypass fails
its update/error obligations. Both selector directions are covered.
Reset-demand assertions establish oscillator-on after forced demand, immediate
policy cancellation from RUN/STOPPING/light OFF, and fresh startup with a closed
gate from deep OFF. The actual ignored-demand fault fails; deep wake and stopping
cancellation are covered. These use the production BrownoutSelect/OscSequencer.

Assumptions: initial asserted reset, then arbitrary subsequent reset and inputs,
one local AON proof clock. No valid-key, valid-selector, stable-source or legal
request assumption. Full production-width policy counters remain. Existing
120-second per-job cap and 24-step fault/cover search are unchanged. Positive
PDR results are unbounded; cover/fault searches are bounded diagnostics.

The first invocation (`power-reset-formal01`) failed at Scala compilation because
an anonymous child's Bool `fault` output shadowed a Boolean injection argument.
Only the argument/use was renamed to `injectFault`; no solver ran on that attempt.
Independent review checked the precise correction, current source/artifact hashes,
positive statuses, intended fault identities and covers.

Local MMIO, owner/mask/key/reset and analog-model simulations passed in
`build/t33/local01`; the T33 report records the command. This is not a proof of
bus/CDC/reset composition, the analog switching guarantee, source-count minimum,
or shutdown ownership. T34 owns analog characterization; T33 composition remains
open. No task or physical signoff is claimed.

T33 structural continuation, measured at the same commit plus hashed working
tree: `python tools/env/run.py run -- python hw/lib/formal/cdc_proof.py --width 8
--depth 2 --output build/t33/cdc-sealed01` passed the unchanged local FIFO and
side proofs with ABC PDR, both covers and all three actual faults. Measured
command time 24.544097 s. The existing 120-second job cap, cover depth 48 and
all assumptions/assertions remain unchanged. The receipt now seals its model
inputs, prepared artifacts and tools; no exhausted T33 job was rerun.

`CdcSideFormal` directly proves ResetRelease's two-edge local release property;
its early-release implementation fault fails. Initial reset is asserted,
subsequent reset is arbitrary, monitor history is initialized, and sampling is
ideal digital behavior without metastability. The production child HDL matches
the freshly sealed proof child exactly. `build/t33/crossing-binding03` attaches
this scoped source premise to 93 actual ResetRelease instances and preserves
their mapped identity candidates. It does not establish mapping equivalence,
clock readiness, reset distribution, or composition across independent resets.
The FIFO proof remains width 8/depth 2; no other parameterization is inferred.

D86 (user, 2026-11-24) permits T33 closeout with the expensive startup,
shutdown, stale-response and composed CDC/RDC proof obligations explicitly
deferred and unproved. No failed or unresolved proof is relabelled PASS;
entrypoints remain failing-closed. Focused production simulation is separate
evidence. Analog, mapped crossing and physical reset qualification remain open.
