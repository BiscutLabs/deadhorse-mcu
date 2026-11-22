# T31 Retained locked-image restart

Withdrawn by D73 (2026-11-21). The text below is historical, unimplemented
proposal material. The recovery loader's existing feature set and reset/lock
policy remain frozen; no extension is authorized.

## Goal and authorization boundary

Continue assigned RTL on main without CI. Prepare the narrowly scoped optional
restart extension in docs/spec/retained-loader-restart.md. Implementation is
blocked until the user approves changing the existing warm-reset image-
invalidation policy. Do not infer that approval from this brief or progress.

## Read first

AGENTS; plan README, STATUS, task index, skills15; plans03/04/06/07/11–14/16;
recovery-loader and proposed retained-restart contracts; T18/T25/T28/T30 reports;
loader control/provenance/tests/formal, SocRetainedMemory and LiteHart admission,
BootControl, shared ResetRelease and full SoC reset bindings.
Skills: task execution, clocked Chisel, reference testing, formal properties,
formal timeout triage and GF180 timing. No new register map is proposed.

## Deliverables, after the reset-policy decision

1. Record the explicit decision and finalize the independently reviewed contract.
2. Optional descriptor retention and fenced restoration; preserve old profiles,
   lock semantics, all host commands and the physical memory/clock interfaces.
   No automatic restart and no cold-reset reuse of unverified retained contents.
3. Prove descriptor provenance/reset safety and locked-program write exclusion on
   production logic, with covers/faults and existing caps. Tests use independent
   host/checksum models and public memory/wire interfaces. No unchecked premise.
4. Actual full-SoC explicit warm restart of the locked image, accepted-START
   ownership and performance release, including reset-boundary negative controls.
5. Fresh mapped timing, complete profiles, frozen focused checks, independent
   review and report. Neither CI tier runs. No inherited proof retries.

## May change

Own brief/index/STATUS row/log, approved decision entry; narrow recovery-loader
extension and provenance, SoC option/emitter/admission/retained-memory assertions;
focused tests, proof/timing/preparation runners, affected contracts and ledgers.
Keep inherited local work separate. No vendor edits, private CDC, new clocks,
flash ABI, automatic boot policy, program-memory permissions bypass or CI.

## Acceptance commands

Proposed commands, not implemented or run: pinned
`python dv/soc/check_retained_restart.py --output build/t31/<fresh-directory>`
with old-profile loader regressions, new control/memory/full-SoC tests, capped
formal jobs, mapped timing and complete profiles. Freeze implementation before
that run and independently audit exact receipts. Report every unresolved job.

## Stop conditions

The pending reset-policy decision is mandatory before RTL. Stop for any further
architecture/behavior conflict, changed proof assumption or acceptance limit,
or exhausted formal triage budget. Do not claim firmware/physical qualification
or automatic warm boot from an explicitly host-commanded restart.
