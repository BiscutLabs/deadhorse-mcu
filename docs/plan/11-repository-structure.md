# 11 Repository structure

This layout defines where Deadhorse source, verification, and documentation belong.

## What Coldfoot got right

- **`hw/ip/<block>/` as the unit of ownership,** with source, tests, formal
  and docs beside each other for most blocks.
- Keep shared interfaces and types in the shared library.
- **FuseSoC `.core` files** as the declared file list for each block.
- **Separate `asic/`, `fpga/`, `sw/` trees,** so a deployment target never
  leaks into `hw/`.

Deadhorse keeps all four ideas.

## What to fix

Each item was checked in the repository; the count or path is given.

| Problem | Rule for Deadhorse |
| --- | --- |
| Loose files at the root | Root holds only README, licence, agent instructions, build manifests and directories (rule 1) |
| IP directories differ in shape | Every block has the same subdirectories and a manifest (rule 2) |
| Files live away from their owner | A proof, test or document lives with the RTL it is about (rule 3) |
| Duplicates | One copy of everything (rule 4) |
| Symlinks used to surface documents | No symlinks; an index page links instead (rule 4) |
| Build output and binaries in git | Nothing generated is committed (rule 5) |
| Scratch committed | Scratch has an ignored home (rule 5) |
| `.gitignore` of 7,711 lines | All output goes under one ignored directory (rule 5) |
| CI not active | CI lives at the root and is the same command developers run (rule 6) |
| Per-platform wrapper triplets | One cross-platform entry point (rule 6) |
| Absolute paths in documents | Relative links only, checked in CI (rule 7) |
| Names that mislead | A name states what the thing is (rule 8) |
| Assistant and personal tooling mixed in | One place for agent instructions; personal knowledge tools stay out of the repository (rule 9) |
| Application work inside the chip repository | Applications and demos live in their own repository (rule 10) |
| Vendored code without a pin | Adopted code is pinned, recorded and never edited in place (rule 11) |

## Proposed layout

```
deadhorse-mcu/
├── README.md  LICENSE  AGENTS.md
├── build.sbt  fusesoc.conf  .gitignore
├── .github/workflows/          CI, at the root
├── .agents/                    agent skills and instructions, one place
│
├── docs/
│   ├── plan/                   this plan
│   ├── spec/                   normative: register map, 
│   │                           memory map, pinout, boot format
│   ├── design/                 cross-cutting design notes: regions, crossings,
│   │                           sleep, reset
│   ├── decisions/              one short file per decision, numbered
│   └── ledger/                 area, clocked state and timing, one row per commit
│
├── hw/
│   ├── ip/<block>/             one directory per block, identical shape
│   │   ├── README.md           the block's contract
│   │   ├── <block>.core        file list and targets
│   │   ├── rtl/                synthesizable source only
│   │   ├── dv/                 simulation tests and benches
│   │   ├── formal/             harnesses for this block's RTL
│   │   └── doc/                deeper documentation, optional
│   ├── lib/                    shared packages, interfaces, primitives
│   ├── regmap/                 the single register description and its generator
│   ├── vendor/<name>/          adopted IP, unmodified
│   │   ├── <name>.lock.json    upstream URL, commit, licence, import date
│   │   └── patches/            our changes, as patches
│   └── top/
│       ├── reference/          the clocked reference SoC
│       ├── chip/               pad-level wrapper
│       └── stubs/              stand-ins with final ports (USB, reserved node)
│
├── desync/                     region and bank definitions, generator
│                               configuration; generated netlists go to build/
├── analog/<macro>/             generator, characterisation, layout, views,
│                               and a status file
├── phys/gf180-ws-1x1/          PDK lock, slot, pad ring, floorplan,
│                               constraints, flow scripts
├── fpga/<board>/               clocked-reference prototype
│
├── sw/
│   ├── boot/  lite/  flight/   boot ROM, lite-core and flight firmware
│   ├── hal/  include/          drivers; headers generated from the register map
│   └── host/                   PC-side tools: gateway client, loader, calibration
│
├── dv/                         chip-level tests, oracles, airframe model,
│                               interoperability tests
├── tools/                      one entry point, CI driver, structure checks
└── build/                      ignored; every generated file
```

### Blocks expected under `hw/ip/`

`lite_core`, `bus`, `intc`, `power_reset`, `timebase_wdt`, `gpio`, `uart`,
`spi_host`, `i2c_host`, `i2c_target`, `adc_player`, `qspi_flash`, `timers`,
`actuator`, `gateway`, .

### Expected under `hw/vendor/`

`ibex` (performance core),
`usb` (from its implementer, when delivered), and the debug module if D5 is
taken. RISCay's generator is not vendored: it is a pinned build dependency,
as chisel-async is for RISCay.

## Rules

1. **Clean root.** Only the files shown above. A script belongs in `tools/`,
   a test in `dv/` or a block's `dv/`, a note in `docs/`.
2. **Uniform blocks.** Every `hw/ip/<block>/` has a README, a manifest and
   `rtl/`. `dv/` and `formal/` are present or the README says why not.
   Names are lower snake case. A structure check in CI enforces this.
3. **Ownership by location.** A harness, test or document sits in the block
   whose RTL it concerns. Nothing but synthesizable source goes in `rtl/`.
4. **One copy, no symlinks.** Shared material goes in `hw/lib/`. To surface a
   block's document elsewhere, link to it from `docs/README.md`.
5. **Nothing generated is committed.** Netlists, layouts, GDS, waveforms,
   logs, run reports, model files and compiled extensions go under `build/`,
   which is the single ignored output directory. Results worth keeping become
   a ledger row with the commit and the command that reproduces them.
   Tape-out artifacts are release assets, not tree contents. Personal
   scratch goes in an ignored `scratch/`. The one committed results
   directory is `sw/flight/loop-measurement/results/`, kept as the recorded
   evidence for R-CPU-1 and compared by CI.
6. **One command.** `tools/ci.py` runs the same checks locally and in CI, on
   every platform. No per-platform wrapper files.
7. **Relative links only,** verified by a link check in CI.
8. **Honest names.** If it is clocked, it is not called async. If it is a
   stub, it lives in `stubs/`.
9. **Agent material in one place.** `AGENTS.md` at the root and `.agents/`
   for skills. Personal knowledge-base and graph tools are configured outside
   the repository.
10. **The chip only.** Demos, model training and application firmware beyond
    the flight stack live in their own repositories and consume released
    headers and tools.
11. **Vendored code is pinned and untouched.** Each has a lock file. Changes
    are patches, so an upstream update is a re-import, not a merge.

### The block README is a contract

Following RISCay's working method, each block's README states, on one page:
interfaces and protocol; which timing region or island it is in; every delay
with its kind (relative, absolute, simulation-only); reset behaviour; an
area estimate; and its status (planned, reference, generated, routed).

## Where Coldfoot material lands

| Coldfoot | Deadhorse | Change |
| --- | --- | --- |
| `hw/common/` | `hw/lib/` | Same role; misleading names corrected |
| `hw/soc/` | `hw/top/reference/` | |
| `asic/` | `phys/gf180-ws-1x1/` | Slot, pad ring and flow kept; template licence, nested CI, `tmp/` and `final/` not carried |
| `fpga/nexys_video/` | `fpga/nexys_video/` | Vendored Ethernet library pinned or dropped |
| `sw/runtime/` | Reference for `sw/host/` | Build output excluded |
| `scripts/`, `tools/`, root scripts | `tools/` | One entry point |
| `ai/`, `.claude/`, `.githooks/` | `AGENTS.md`, `.agents/` | |
| `demo/`, `snn_visualize/` | Not carried | Separate repository |
| `docs/` reports and investigation logs | `docs/ledger/` rows; the rest not carried | |

## Mixed languages

Deadhorse combines Chisel (RISCay's generator and core), SystemVerilog
(Ibex), Python tools and C firmware. The layout is by
function, not by language. Each block's manifest declares its sources;
`build.sbt` covers the Chisel projects and FuseSoC the SystemVerilog file
lists. Whether to consolidate on one manifest system is left open until the
first spike shows how the generator consumes a SystemVerilog block.
