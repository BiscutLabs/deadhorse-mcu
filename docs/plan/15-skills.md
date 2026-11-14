# 15 Skills

Six skills teach an agent how to do the recurring kinds of work in this
project. The plan and the briefs say what to build; the skills say how to do
it well. Load the skills listed for your task before you start it.

Where a skill and `AGENTS.md`, a brief or a plan document disagree, the
repository document wins.

## The skills

| Skill | Teaches | Verified? |
| --- | --- | --- |
| `deadhorse-task-execution` | Reading a brief, tracking progress, labelling numbers, acceptance checks, the report, when to stop and ask | Process only; mirrors `AGENTS.md` |
| `clocked-chisel-block-design` | Registered outputs, skid buffers, multi-cycle arithmetic, synchronous memories, clock-domain crossings, clock gating, reset, black-boxing vendored code | Rules from the plan; no code compiled in this repository yet |
| `chisel-formal-properties` | Deriving properties from the specification, proved versus bounded, symbolic data tracking, covers, negative controls, signs of a vacuous proof | Method only; tool chain not yet run here |
| `gf180-synth-timing-check` | PDK fetch, yosys with the slang front end, known tool failures and fixes, reading area reports, the timing budget | Area flow run and reproduced; timing step not yet run |
| `reference-model-testing` | Block tests in ScalaTest, system tests on the four-target interface, reference models, actuator checkers, negative controls | Rules from the plan; frameworks not yet run here |
| `regmap-authoring` | The register-map YAML format, choosing access types, register-map design rules, pre-generation checks | Format is a draft; generator not yet built |

The skills are kept under `.agents/skills/<name>/SKILL.md`.

## When to use each

### Always

| When | Skill |
| --- | --- |
| Starting, working on or finishing any brief | `deadhorse-task-execution` |

### By kind of work

| You are about to... | Load |
| --- | --- |
| Write or review Chisel RTL for a block | `clocked-chisel-block-design` |
| Touch a clock-domain crossing, a clock gate, the clock mux or reset | `clocked-chisel-block-design` |
| Wrap vendored SystemVerilog in a black box | `clocked-chisel-block-design` |
| Define or change a block's registers | `regmap-authoring` |
| Write, run or review formal properties or a proof | `chisel-formal-properties` |
| Write or review a block test, a system test, a model or a checker | `reference-model-testing` |
| Synthesize anything to GF180, report area, or check a timing budget | `gf180-synth-timing-check` |
| Fix a block that is over its timing budget | `gf180-synth-timing-check`, then `clocked-chisel-block-design` |

A new hardware block normally needs four, in this order: `regmap-authoring`,
`clocked-chisel-block-design`, `chisel-formal-properties`,
`reference-model-testing`, and then `gf180-synth-timing-check` before it is
called done.

### By task

`deadhorse-task-execution` applies to every row and is not repeated.

| Task | Skills |
| --- | --- |
| PLAN01, T08 Pinned environment, T01 Scaffold and CI | none beyond task execution |
| T02 Historical flight-loop CI | `reference-model-testing` (seeds, negative controls, no weakened checks) |
| T03 Transport import | `gf180-synth-timing-check`, where its checks run synthesis |
| T05 Register generator | `regmap-authoring`, `reference-model-testing`, `chisel-formal-properties` (generated properties) |
| T06 RISCay baseline | `gf180-synth-timing-check` (reference area) |
| T07 Clocked Chisel build | `clocked-chisel-block-design`, `chisel-formal-properties` (smoke test) |
| T09 GF180 timing flow | `gf180-synth-timing-check` |
| T10 Ibex reference and harness | `reference-model-testing`, `chisel-formal-properties` (negative controls, proved versus bounded) |
| T11 Ibex conversion | `clocked-chisel-block-design`, `chisel-formal-properties`, `gf180-synth-timing-check` |
| T12 FPU | `clocked-chisel-block-design`, `chisel-formal-properties`, `reference-model-testing`, `gf180-synth-timing-check` |
| T13 F integration | `clocked-chisel-block-design`, `chisel-formal-properties`, `reference-model-testing`, `gf180-synth-timing-check` |
| S1 Core measurement | `gf180-synth-timing-check`, `reference-model-testing` |
| S3 Memory | `reference-model-testing` |
| S4 Latency and test | `gf180-synth-timing-check`, `reference-model-testing` |

The briefs are the authority on what each task involves. If a brief has
changed so that this table no longer fits it, follow the "By kind of work"
table.

### By phase

| Phase | Work | Skills most used |
| --- | --- | --- |
| P0 Foundation | Scaffold, vendoring, build, baselines | `deadhorse-task-execution`, `gf180-synth-timing-check` |
| P1 Spikes | Measuring cores and memory | `gf180-synth-timing-check`, `chisel-formal-properties` |
| P2 SoC and FPGA | Every new block; integration; system tests | All six. Each block brief names its own |
| P3 Physical | Timing closure, equivalence | `gf180-synth-timing-check`, `chisel-formal-properties` (equivalence) |
| P4 Silicon | Bring-up with the shared tests | `reference-model-testing` |

## Work with no skill

These need a senior engineer or the strongest available model, and a skill
would give false confidence: the
optional Click lite core (spike S5), analog macros, and the flight firmware's
control design. A fixed-point flight-firmware skill is worth writing once
that work starts and its conventions are known.

## Keeping skills honest

- The skills were written on 2026-11-14 against the plan as it stood on
  2026-11-13. The plan has been reconciled since. Where a skill names a
  detail the plan no longer holds (a core choice, a script path, a number),
  the plan and the brief win, and the mismatch is reported.

- A skill contains only commands and patterns that have been run in this
  project, or it says plainly that they have not. Each skill ends with a
  "Status of this skill" section.
- When a task proves an unverified part of a skill (the Chisel build, the
  formal smoke test, the timing flow), the task's report says so, and the
  skill is updated by a person: remove the caveat, add the working command.
- When a task finds a skill is wrong, report it under "Open issues". Do not
  edit the skill as part of an unrelated task.
- New briefs include a **Skills** line listing what to load.
