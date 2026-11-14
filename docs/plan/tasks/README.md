# Task briefs

One brief per unit of work. A brief is written so that an agent or engineer
who has not seen the planning conversation can carry it out. Read
[../../../AGENTS.md](../../../AGENTS.md) first; its rules apply to every
brief.

## Status

| ID | Task | Who can take it | Depends on | Status |
| --- | --- | --- | --- | --- |
| [T01](T01-scaffold.md) | Repository scaffold, block template, structure check, CI | Any agent | none | Ready |
| [T02](T02-flight-loop-ci.md) | Put the flight-loop measurement under CI and fix its fragile cross-check | Any agent | T01 | Ready |
| T03 | Historical interconnect study | Any agent, with source access | T01 | Ready |
| T04 | Historical interconnect study | Any agent, with source access | T03 | Ready |
| [T05](T05-regmap-generator.md) | Register-map generator (Python front end, Chisel register block) | Any agent, with Maven Central access | T07 | Ready after T07 |
| [T06](T06-riscay-baseline.md) | Bring up RISCay's toolchain and record its baseline | Any agent, with Maven Central access | T01 | Ready |
| [T07](T07-chisel-build.md) | Chisel build skeleton | Any agent, with Maven Central access | T01, T06 | **Needs revision:** written for chisel-async; see the note at its top |
| [S1](S-spikes.md#s1-core) | Core speed and area spike | Capable agent with review | D1, D2, T06 | Blocked on D1, D2 |
| S2 | Historical interconnect study | Senior engineer or strongest model | T03, T04 | Ready after T04 |
| [S3](S-spikes.md#s3-memory) | Memory and execute-in-place spike | Capable agent with review | T02 | Ready after T02 |
| [S4](S-spikes.md#s4-latency-and-test-access) | Interrupt latency and scan | Capable agent with review | S1 | Blocked on S1 |

T01 first. T02, T03 and T06 can then run in parallel. T07 follows T06, and
T05 follows T07.

Deadhorse RTL is clocked Chisel (decisions D16 and D17). T06, T07, T05 and
every later hardware task need a machine that can reach Maven Central.

## What was verified while writing these briefs

Run on 2026-11-13, Ubuntu 24.04 x86_64.

| Item | Result |
| --- | --- |
| RISCay-MCU tool bootstrap (JDK 21, firtool 1.160.0, sv2v 0.0.13, Icarus 13.0) | Works, using `tools/bootstrap/riscay_bootstrap.sh` |
| RISCay-MCU firmware build | Works: `event_loop` image is 728 bytes |
| RISCay-MCU Python gate | 513 tests pass, 1 expected skip |
| RISCay-MCU full gate (sbt, Scala suites, clocked export) | **Not verified.** Maven Central was unreachable. T06 does this first |
| Any sbt or Chisel command in T07 and T05 | **Not verified,** for the same reason. Versions are RISCay's pinned ones |
| Flight-loop measurement rerun from a clean copy | Reproduces `summary.md` and `summary.json` byte for byte |
| Flight-loop QEMU cross-check | Fragile: off by one instruction on three of four configurations in a rerun. T02 fixes it |
| PDK fetch from pinned release assets | Works, with SHA-256 checks |

## What is not covered by any brief

These need people, or decisions that are still open:

- analog layout and oscillator redesign;
- spike S5, the optional Click lite core (decision D18). Its brief is
  written once the clocked lite core is stable;
- the USB integration contract;
- decisions D1 to D9, D12, D13 and D15;
- everything from Phase 2 onward. Briefs for Phase 2 are written after gate
  G1, when the spikes have replaced the assumptions.

## Writing a new brief

Copy the section headings of an existing brief. A brief is not ready until
its acceptance checks are commands, and the author has run every command it
tells the reader to run or has marked it "not verified" with the reason.
