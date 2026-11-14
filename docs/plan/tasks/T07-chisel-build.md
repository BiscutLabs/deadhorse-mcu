# T07 Clocked Chisel build and formal smoke test

## Goal

Create a direct pinned Chisel build with a registered example, independent
behavioral test, emitted RTL and formal smoke tests. No chisel-async dependency,
core implementation or vendor import in this task.

## Read first

- [../../../AGENTS.md](../../../AGENTS.md)
- [../11-repository-structure.md](../11-repository-structure.md)
- [../12-formal-verification.md](../12-formal-verification.md)
- [../13-test-environment.md](../13-test-environment.md)
- [T08-environment.md](T08-environment.md) and T06's baseline report when available
- Pinned RISCay build/simulation conventions in its repository-local checkout;
  do not copy LibrarySource.scala or chisel-async-source.json

## Inputs

T01, T08 and T06 complete. Use T08's Linux image locally and in CI. Versions
carried from the prior brief: Scala 2.13.18, Chisel and full-cross-version
compiler plugin 7.16.0, sbt 1.12.4, ScalaTest 3.2.20, firtool 1.160.0, JDK 21.
These are proposed pins pending T08/T07 execution, not verified build results.
Resolve any incompatible pin explicitly; never silently float a dependency.

## May change

`build.sbt`, `project/`, `tools/sbt.py`, `hw/lib/`, emitter under
`hw/top/reference/src/main/scala/`, formal smoke configuration under
`hw/lib/formal/`, `tools/formal_smoke.py`, `tools/ci.py`, CI workflow, report.
Use T08 locks; changes to pins require an explicit recorded resolution.

## Steps

1. Depend directly on pinned Chisel and compiler plugin. Adapt the launcher to
   Deadhorse paths/package conventions. Exclude vendor/template directories from
   automatic new-source discovery. Do not import the async build graph.
2. Compile shared library, block and top source/test directories under one sbt
   build, consistent with the repository structure. Outputs/caches under build/.
3. Implement Hello with an 8-bit input and registered 8-bit output equal to
   input plus one modulo 256, asynchronous active-low reset to zero, and a Chisel
   emitter accepting an output path. Test reset and at least three input values,
   including wraparound, against an independent behavioral expectation.
4. Add formal assertions, assumptions and covers beside the example, with a
   deliberately incorrect variant as negative control. Demonstrate the BTOR2
   and SymbiYosys routes and distinguish bounded from unbounded outcomes.
5. Wire compilation, simulation, emission and formal smoke into mandatory CI.
   Missing configured tools are failures, not SKIP successes.

## Acceptance checks

Run inside T08's image. **Not executed/verified by this documentation revision**;
the commands define interfaces to create in this task.

```sh
python3 tools/sbt.py "hw/compile"
python3 tools/sbt.py "hw/test"
python3 tools/sbt.py "hw/runMain deadhorse.top.EmitHello build/emit/hello"
iverilog -g2012 -o build/emit/hello/a.out build/emit/hello/Hello.sv
python3 tools/formal_smoke.py --output build/t07/formal
python3 tools/ci.py
```

Require behavioral test success, both formal routes reporting expected true,
false and cover outcomes, and an unbounded smoke property where the plan
requires proof. Record tool versions and logs; no generated files tracked.

## Stop and ask

Pinned dependencies cannot resolve/build; a required formal route cannot run;
only bounded results are available where proof is required; tools would need
unpinned installation. Report evidence rather than skip or weaken checks.

## Out of scope

CPU/FPU, actual CDC block, async primitives, and any new handwritten Verilog or
SystemVerilog. Formal wrappers/properties are Chisel or tool configuration.
