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

`dv/pad_model.py` separately records a simulation-only foundry-model adaptation:
four `rnmos #1` disabled-pull primitives become `bufif1 #1`, preserving other
bytes and delays. Verilator does not support rnmos. This view is legal only with
all PU/PD tied zero, checked in the fixture; original and patched models run the
same four-state Icarus tests. It is never selected for production, physical
extraction, pad characterization or enabled-pull simulation. Power-port and
specify behavior are not qualified by the digital boot test.
