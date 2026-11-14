# T01 Repository scaffold, block template, structure check, CI

## Goal

Create the directory layout in
[../11-repository-structure.md](../11-repository-structure.md), a template
for hardware blocks, a script that enforces the layout rules, and a CI
workflow that runs it.

## Read first

- [../../../AGENTS.md](../../../AGENTS.md)
- [../11-repository-structure.md](../11-repository-structure.md), all of it

## Starting state

The repository contains `README.md`, `AGENTS.md`, `docs/plan/`, `docs/spec/`,
`sw/flight/loop-measurement/`, `tools/bootstrap/` and
. Do not move or edit these.

## May change

New files only, plus `README.md` at the root (add a short "Layout" section
linking to the structure document). Nothing under `docs/plan/` except your
report.

## Steps

1. **Directories.** Git does not track empty directories. For each
   directory in the proposed layout that does not exist, create it with a
   `README.md` of two to five lines saying what belongs there, taken from the
   structure document. Directories: `docs/design`, `docs/decisions`,
   `docs/ledger`, `hw/ip`, `hw/lib`, `hw/regmap`, `hw/vendor`,
   `hw/top/reference`, `hw/top/chip`, `hw/top/stubs`, `desync`, `analog`,
   `phys/gf180-ws-1x1`, `fpga`, `sw/boot`, `sw/lite`, `sw/hal`, `sw/include`,
   `sw/host`, `dv`, `.agents`.
2. **`.gitignore`** at the root with exactly: `build/`, `scratch/`,
   `__pycache__/`, `*.pyc`, `.venv/`, `venv/`.
3. **Block template** at `hw/ip/_template/`: `README.md` with the contract
   headings from the structure document (interfaces and protocol; timing
   region; delays with their kind; reset behaviour; area estimate; status),
   `_template.core` (a minimal FuseSoC CAPI2 file listing `rtl/_template.sv`),
   `rtl/_template.sv` (an empty module), and empty-but-present `dv/README.md`
   and `formal/README.md`.
4. **Structure check** at `tools/check_structure.py`, Python 3.10 or later,
   standard library only. It takes the repository root as an optional
   argument, prints one line per violation as `RULE path: message`, and exits
   1 if there is any. Rules:

   | Rule id | Check |
   | --- | --- |
   | `ROOT_FILES` | Tracked files at the root are only: `README.md`, `LICENSE`, `AGENTS.md`, `build.sbt`, `fusesoc.conf`, `.gitignore` |
   | `BLOCK_SHAPE` | Every directory under `hw/ip/` has `README.md`, `<name>.core` and `rtl/` |
   | `BLOCK_NAME` | Every directory under `hw/ip/` and `hw/vendor/` is lower snake case (`_template` allowed) |
   | `RTL_ONLY` | Files under any `hw/ip/*/rtl/` have extension `.sv`, `.v`, `.svh`, `.vh` or `.scala`, or are named `.gitkeep` |
   | `NO_SYMLINK` | No tracked symbolic links |
   | `NO_LARGE` | No tracked file over 1 MiB, except paths listed in `tools/structure_allow.json` |
   | `NO_GENERATED` | No tracked file with extension `.vcd`, `.fst`, `.gds`, `.oas`, `.log`, `.o`, `.elf`, `.pyc`, `.pt`, `.pyd`, and no tracked path containing `/build/` or `/obj_dir/` |
   | `NO_PLATFORM_WRAPPER` | No tracked `.ps1`, `.cmd` or `.bat` |
   | `REL_LINKS` | In every tracked `.md`: no link target starting with `/` or matching a drive letter; every relative link target exists |
   | `VENDOR_LOCK` | Every directory under `hw/vendor/` has `<name>.lock.json` |

   Use `git ls-files` to list tracked files; if the directory is not a git
   repository, walk the tree and skip `build/`, `scratch/` and `.git/`.
   `tools/structure_allow.json` starts as `{"large": []}`.
5. **Tests** at `tools/test_check_structure.py` using `unittest`. For every
   rule, one test builds a temporary directory that violates only that rule
   and asserts the rule id is reported, and one test asserts a clean tree
   reports nothing.
6. **CI entry point** at `tools/ci.py`: runs the unit tests under `tools/`,
   then `check_structure.py` on the repository; exits non-zero if either
   fails; prints `PASS` on success.
7. **Workflow** at `.github/workflows/ci.yml`: on push and pull request, on
   `ubuntu-24.04`, check out, set up Python 3.12, run `python tools/ci.py`.

## Deliverables

The files named in the steps.

## Acceptance checks

Run each and paste the result into your report.

```sh
python3 tools/ci.py                          # prints PASS, exits 0
python3 -m unittest discover -s tools -p 'test_check_structure.py' -v   # 11 or more tests, all ok
python3 tools/check_structure.py             # no output, exits 0
```

## Stop and ask

- An existing file in the starting state violates one of the rules. Report
  which; do not move it and do not weaken the rule.
- You think a rule in the table is wrong.

## Out of scope

Any RTL, any build of hardware, sbt or FuseSoC configuration beyond the
template's `.core` file, and the root `LICENSE` (open question Q8).
