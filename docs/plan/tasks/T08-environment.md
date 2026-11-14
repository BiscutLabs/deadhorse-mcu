# T08 Pinned Linux environment

## Goal

Define a reproducible Linux container usable through Docker/WSL and the same
image for the local check command (D23, local-only decision 2026-11-14). This task can precede T01; it does not create MCU RTL.

## Read first

- [../../../AGENTS.md](../../../AGENTS.md)
- [../13-test-environment.md](../13-test-environment.md)
- [T07-chisel-build.md](T07-chisel-build.md)
- Existing bootstrap and historical measurement tool requirements

## May change

`tools/env/`, environment usage in root README, task report. T01 subsequently
wires the local check command to this environment; no hosted workflow. No global installs or external workspace paths.

## Deliverables and steps

1. Container recipe, immutable base/image digest and tool/dependency lock under
   tools/env. Pin JDK/sbt/Scala/Chisel/firtool, Python with tkinter/PyYAML,
   simulators, RISC-V compiler, QEMU, synthesis/slang, formal engines and timing
   dependencies needed by the briefs. Use recorded upstream sources/hashes;
   do not invent missing versions. Document unresolved compatibility explicitly.
2. Linux entry point that mounts only this repository and puts outputs/caches
   under build/. Host Docker orchestration is allowed; implementation checks
   execute in the pinned image. No platform-specific wrapper scripts.
3. `tools/env/check.py` validates installed versions against locks and runs
   tool smoke commands. Verify repeatability on a clean build and document
   Docker/WSL invocation and the CI image reference.

## Acceptance checks

Proposed commands, **not run by PLAN01**. Run on assignment and record results.

```sh
docker build -f tools/env/Dockerfile -t deadhorse-env:local .
docker run --rm -v "$PWD:/work" -w /work deadhorse-env:local python3 tools/env/check.py
```

Record image digest and resolved pins, repeat the smoke on a clean image, and
confirm no generated artifacts are tracked. Do not claim T07 compile/formal
success from version checks alone. If T01 already exists, run its CI as well.

## Stop and ask

Unavailable pinned sources, incompatible versions, missing formal/timing tools,
or a required dependency outside the approved environment. No ad hoc fallback.
