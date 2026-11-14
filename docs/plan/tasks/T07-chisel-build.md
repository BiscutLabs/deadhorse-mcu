# T07 Chisel build skeleton

> **Revision needed before hand-off (decision D17, 2026-11-13).** Deadhorse
> is now entirely clocked and does not use chisel-async. This brief was
> written when it did: it takes Chisel through chisel-async's build and
> copies RISCay's `LibrarySource.scala` and `chisel-async-source.json`.
> The revised task is to depend on Chisel 7.16.0 and its compiler plugin
> directly from Maven Central, with the same Scala, sbt, ScalaTest and
> firtool pins, and to drop every chisel-async step and stop condition.
> Do not start this brief until it has been rewritten.

## Goal

Give the repository a working Chisel and chisel-async build: one sbt project
that compiles every block under `hw/`, a first trivial Chisel module with a
test, and SystemVerilog emission into `build/`.

## Why

Deadhorse's own RTL is written in Chisel with chisel-async (decision D16).
Nothing else can be written until the build exists and is pinned the way
RISCay-MCU's is.

## Read first

- [../../../AGENTS.md](../../../AGENTS.md)
- [../11-repository-structure.md](../11-repository-structure.md), "Design
  language and build"
- In RISCay-MCU at `4671317`: `build.sbt`, `project/LibrarySource.scala`,
  `project/chisel-async-source.json`, `project/build.properties`,
  `project/repositories`, `tools/sbt.py`. Copy their approach, not their
  project list.

## Inputs

- T01 and T06 complete. T06 proves the toolchain works on your machine and
  leaves a bootstrapped RISCay checkout at `build/riscay-mcu`.
- Network access to GitHub and `repo.maven.apache.org`. Check with
  `curl -sI https://repo.maven.apache.org/maven2/ | head -1` (must be `200`).

**None of the sbt commands in this brief were run by its author:** Maven
Central was unreachable when it was written. Versions below are RISCay's
pinned ones, read from its files.

## Pinned versions

| Item | Value | Source |
| --- | --- | --- |
| Scala | 2.13.18 | RISCay `build.sbt` |
| Chisel compiler plugin | `org.chipsalliance` `chisel-plugin` 7.16.0, full cross-version | RISCay `build.sbt` |
| sbt | 1.12.4 | RISCay `project/build.properties` |
| ScalaTest | 3.2.20 | RISCay `build.sbt` |
| firtool | 1.160.0 | RISCay setup guide |
| JDK | 21 | RISCay setup guide |
| chisel-async | commit `856fc757517e0ff0c1c8fea9f6d7e61ec32d1172` | RISCay `project/chisel-async-source.json` |

Chisel itself arrives through chisel-async's own build; do not add a second
Chisel dependency.

## May change

New files: `build.sbt`, `project/` (four files), `tools/sbt.py`,
`hw/lib/src/main/scala/deadhorse/lib/Hello.scala`,
`hw/lib/src/test/scala/deadhorse/lib/HelloSpec.scala`,
`hw/top/reference/src/main/scala/deadhorse/top/EmitHello.scala`. Edits to
`tools/ci.py`, `.github/workflows/ci.yml` and `hw/lib/README.md`.

## Steps

1. Copy `project/LibrarySource.scala`, `project/chisel-async-source.json`,
   `project/build.properties` and `project/repositories` from RISCay
   unchanged. Copy `tools/sbt.py` unchanged too. If it needs an edit to run
   here, stop and ask.
2. Write `build.sbt` with RISCay's `ThisBuild` settings, the `asyncLibrary`
   `RootProject`, and the same `settings` sequence. Define one project,
   `hw`, at the repository root's `hw/` directory, depending on
   `asyncLibrary`, whose sources are every `hw/lib/src/main/scala`,
   `hw/ip/*/src/main/scala` and `hw/top/*/src/main/scala` directory, and
   whose tests are the matching `src/test/scala` directories. Use
   `unmanagedSourceDirectories`. Exclude `hw/ip/_template` and `hw/vendor`.
   Set the organization to `io.github.biscutlabs` and the package root to
   `deadhorse`.
3. `Hello.scala`: a Chisel `Module` named `Hello` in package
   `deadhorse.lib` with an 8-bit input, an 8-bit registered output that
   holds the input plus one, and an asynchronous active-low reset to zero.
4. `HelloSpec.scala`: a ScalaTest spec that simulates `Hello` the way
   RISCay's `ClockedCoreSpec` simulates its design (read that file under
   `build/riscay-mcu/verification/` first and follow its harness) and checks
   three input values, plus the reset value.
5. `EmitHello.scala`: an `App` that writes SystemVerilog for `Hello` to the
   directory given as its argument, the way RISCay's `EmitClockedSoc` does.
6. `tools/ci.py`: when `JAVA_HOME` and `CHISEL_FIRTOOL_PATH` are set, run
   `python3 tools/sbt.py "hw/test"`; otherwise print
   `SKIP chisel (toolchain not configured)`.
7. Workflow: add a job that runs the RISCay bootstrap script to obtain the
   JDK, firtool and simulator, exports the four environment variables from
   `build/riscay-mcu/build/riscay_env.sh`, and runs `tools/ci.py`.

## Acceptance checks

With the environment from `build/riscay-mcu/build/riscay_env.sh` loaded:

```sh
python3 tools/sbt.py --bootstrap "hw/compile"                       # success
python3 tools/sbt.py "hw/test"                                      # HelloSpec passes, 4 or more checks
python3 tools/sbt.py "hw/runMain deadhorse.top.EmitHello build/emit/hello"
ls build/emit/hello/*.sv                                            # Hello.sv exists
iverilog -g2012 -o build/emit/hello/a.out build/emit/hello/Hello.sv # compiles
git status --short | grep -c "build/"                               # 0
python3 tools/ci.py                                                 # PASS, and does not print SKIP chisel
```

## Stop and ask

- Maven Central is unreachable.
- The pinned chisel-async commit does not build with these versions.
- RISCay's simulation harness cannot be reused without copying more than
  one small helper. Report what it depends on.
- You need to change any pinned version.

## Out of scope

Any real block, any chisel-async channel or async primitive, the
desynchronization generator, and FuseSoC.
