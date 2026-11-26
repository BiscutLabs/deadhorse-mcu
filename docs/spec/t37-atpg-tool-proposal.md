# T37 ATPG tool prerequisite

Status: approved for pinned Quaigh build and scoped qualification under the
user's 2026-11-26 conditional approval after researching alternatives. The
[research](t37-scan-research.md) found no better-supported drop-in option;
independent review agrees. A small combinational interface pilot passes;
production scan qualification is still open. Minimal relevant tests/proofs,
no aggregate CI. Historical preflight findings below explain the original stop.

## Finding

Measured availability probes at production commit
`e7c6cd45721f5cb9d05b942ab923f529e4f7df3e`, recorded by
`python scratch/t37_preflight.py` in `build/t37/preflight01/result.json`:

- The pinned native OpenROAD exposes `scan_replace`, `set_dft_config`,
  `report_dft_plan` and `execute_dft_plan`. This establishes command
  availability only; GF180 scan mapping and production insertion remain unrun.
- Neither the repository OSS CAD environment nor the native physical Nix
  environment contains `fault`, `quaigh`, `nl2bench`, `atalanta` or `atpg`.
  The older pinned OpenROAD Docker image has none of those either.
- Both ABC builds reject `atpg -h` as an unknown command, despite returning
  process status zero. ABC's `faultclasses` computes fault equivalence
  classes; its help does not supply a pattern-generation/replay flow.

At the initial stop no RTL, pad assignment, tool pin, reset, functional behavior
or coverage acceptance had changed. Quaigh is now pinned separately; the
physical-flow pins and production RTL remain unchanged. No numerical S4 coverage floor is specified in the
current S4 brief; achieved coverage and all exclusions still have to be reported.

## Proposed narrow adoption

1. Keep the current OpenROAD, LibreLane, PDK and GF180 cell pins. Use
   OpenROAD for scan-cell replacement/stitching with separate clock-domain
   chains and reviewed reset/gate controls.
2. Add a separately locked **Quaigh** ATPG tool, starting from observed
   upstream HEAD `5b47ca63608d516efc3f225758635df689be70c5`. Record source
   hashes, license and all build dependencies before execution. Its upstream
   project provides stuck-at pattern generation and fault simulation under
   MIT/Apache-2.0 licensing. This is a candidate, not a qualified tool result.
3. Use the existing pinned simulator for independent replay on the actual
   GF180 cell netlist. If a maintained netlist-conversion adapter is needed,
   evaluate **Fault** at `cf5509f1a472e57c81a89ffd675e56ca8536b942`, whose
   documented `nl2bench`/Quaigh interface can supply that conversion. Explicitly
   pin `nl2bench` and any adopted adapter; prove the cut/converted combinational
   semantics against the original cell graph. Do not import Fault's full flake
   or replace the pinned simulator/toolchain. Do not install or invoke the
   proprietary Atalanta/PODEM alternatives bundled with some distributions.
4. First qualify a small representative multi-domain design: real scan cells,
   async reset, shared gate, ordering, functional-mode equivalence and an
   injected stuck-at/chain-break fault. Record fault-site mapping and exact
   denominators, including conversion-introduced/internal versus physical
   cell-pin fault sites. Only then run the production netlist. Unknown,
   aborted and excluded faults remain visible; undetected is not untestable.
5. Report actual stuck-at coverage. Transition coverage stays explicitly
   unsupported/unmeasured unless the pinned tool demonstrates support.
   No invented threshold or automatic waiver. Keep the user's scoped checks
   and no aggregate CI. Any deferred required proof remains an open T37
   acceptance item, including before/after functional-mode equivalence.

This approval would authorize the tool pin/build and focused qualification,
not approve the still-unwritten test-entry/pad/reset contract, remove any T37
acceptance obligation or declare T37 complete. That contract receives the
required independent review before RTL.

## Alternatives considered

Using ABC `faultclasses` alone does not supply the required generator/replay
pipeline. Writing a new ATPG engine would expand scope unnecessarily.
Wholesale adoption of Difetto is not proposed: its upstream describes an
alpha flow with limited/untested macro support and no distinct test SDC;
this chip has SRAM and analog macros and explicit test-clock obligations.

## Sources

- [Quaigh source and ATPG usage](https://github.com/Coloquinte/quaigh).
- [Fault licensing](https://github.com/AUCOHL/Fault) and
  [Quaigh/conversion usage](https://fault.readthedocs.io/en/latest/usage.html).
- [Difetto limitations](https://github.com/donn/difetto).

Candidate revisions were observed with `git ls-remote <source-url> HEAD` on
2026-11-26. Quaigh is now recorded in `tools/physical/atpg.lock.json`;
Fault remains an unadopted alternative. The standalone `nl2bench` converter
can be evaluated without installing Fault. Full physical scan qualification
from step 4 remains open after the initial combinational tool pilot.
