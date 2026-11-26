# Reviewed template adaptations

The canonical upstream files and hashes remain in template.lock.json.
`prepare_chip.py` materializes them, records each original/replacement hash,
and applies the following local changes under build. No upstream file is edited
in place. Independent T43 review covers the socket wiring and D110 behavior.

| File | Local change | Scope |
| --- | --- | --- |
| src/chip_core.sv | Replace example counter/SRAM user design with authored Deadhorse production socket binding | Production integration, no feature/profile change |
| src/chip_pad_feedback.sv | Add legal pad enable/local-feedback logic | D110 approved contract |
| src/generated_defines.svh | Select existing 1x1 slot, fd_io and OCD SRAM | Existing template configuration mechanism |
| src/chip_top.sv | No production change; named simulation copy adds LF/POR model-stimulus ports and connections | Verification only; real pads and core feature set retained |
| librelane config (build copy) | `prepare_fit.py` binds emitted production RTL, explicit3.3V corners, actual SRAM/analog views and placements | Pre-global-placement smoke; production multidomain timing measured separately |
| librelane/pdn/pdn_cfg.tcl (build copy) | Select existing3.3V SRAM branch and append `analog_pdn.tcl` local supply rings/stripes | Real macro power-pin access; canonical template unchanged |

`analog/physical/bind_power.py` explicitly joins the two analog supply aliases
to the approved common VDD/VSS before the template power stage. It rejects
unexpected/signal consumers, checks actual master obstructions, and records
the four moved pins. It changes no signal net or macro geometry. The local
PDN uses the checked lower supply-access band; semantic overlap and polygon
DRC checks are required after generation, not inferred from a successful flow.

`dv/pad_model.py` separately records a simulation-only foundry-model adaptation:
four `rnmos #1` disabled-pull primitives become `bufif1 #1`, preserving other
bytes and delays. Verilator does not support rnmos. This view is legal only with
all PU/PD tied zero, checked in the fixture; original and patched models run the
same four-state Icarus tests. It is never selected for production, physical
extraction, pad characterization or enabled-pull simulation. Power-port and
specify behavior are not qualified by the digital boot test.
