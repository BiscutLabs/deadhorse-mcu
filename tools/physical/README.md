# Standalone USB physical diagnostics

This companion flow places, builds clock trees, routes and extracts the existing
mapped USB wrapper. It never invokes CI. It does not implement a production
floorplan, PDN, pads, foundry DRC/LVS or analog metastability signoff. The current
measured design fails its project setup budgets; see
[the validation report](../../docs/spec/usb-physical-validation.md).

`lock.json` pins a separate OpenROAD OCI image and the same GF180 release used
by the project. `run.py` requires an explicit command, mounts only the repository
and disables network access. `fetch.py` runs in the original pinned environment
with explicit network access and verifies archive hashes before extraction.
It does not replace the main environment lock.

Run `usb_prepare.py` in the main environment with an existing USB snapshot and
a fresh `build/` output. It checks source/flow hashes, adds physical tie cells
and writes the OpenROAD invocation. Run that Tcl through the companion runner.
`usb_extract.py` then writes three RC extraction scripts and fifteen PVT/RC STA
scripts. Run the former through OpenROAD and the latter through the pinned
main environment's `sta`. Preserve every log and failed attempt.

`usb_validate.py` audits sources and populated path classes, checks reset
structure and logical connectivity, and adds directed interstage/reset timing.
The original graph parse must exist as `routed.json`; `usb_netlist.py` produces
a fresh pinned-Yosys parse and authenticates that graph against `routed.v`.
`usb_sdc_audit.py` measures the final effective SDC after both SDC inputs;
`--verify` rechecks existing evidence without another timing invocation.
`usb_seal.py` binds inputs, artifacts and all diagnostic sources into a receipt;
its `--verify` audits that receipt without hardware tools.

The historical physical-04 reports stored absolute arrival, including CTS.
Current extraction declares `launch-relative-data-v2`; validation distinguishes
the formats and never subtracts launch insertion twice. Clock-to-Q is retained.
Correction requires one direct rising clock per original flop and preserved
clock-tree connectivity. A different clock topology must fail rather than use
this pin-arrival correction. Endpoint enumeration reports worst observed
corrected delay; it is not exhaustive data-delay selection or signoff.

Boundary input delays are characterized separately per PVT with the unchanged
estimated pad/reset envelope. The diagnostic removes the old boundary values
before reading the corner contract because `write_sdc` emits `-add_delay`.
All multicycle endpoints, clock groups and boundary values are compared as
complete Tcl commands, including continued lines. No new false paths are added.

Focused tests (not a CI tier):

```text
python tools/env/run.py run -- python3 -m unittest discover -s tools/physical -p test_usb_*.py
```

Exact commands, measured results, preserved failures and limitations are in the
validation report. Generated layout, netlists, receipts and logs stay in `build/`.
