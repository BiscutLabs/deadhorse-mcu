# Pinned local Linux environment

Install Docker Desktop with Linux containers (WSL integration on Windows), or
Docker Engine on Linux. Host Python only orchestrates Docker; checks use Python
from the image. From the repository root:

```sh
python tools/env/run.py build
python tools/env/run.py run -- python3 tools/env/check.py
python tools/env/run.py run
```

The last command runs `python3 tools/ci.py`: environment smoke, tool unit tests,
and structure checks, including new untracked files. There is no GitHub Actions
workflow. Here, CI means the local repeatable check gate.

`build/env/image.json` records the immutable local image ID and environment input
fingerprint. Runs use that ID, never the mutable `deadhorse-env:local` tag, and
reject changed environment inputs until rebuilt. Rebuild from clean layers with
`python tools/env/run.py build --clean`; checksum-verified download caching is
retained. Only this repository is mounted, at `/work`. Outputs, home, temporary
files and tool caches go under `build/env/`. Runs have networking disabled;
future dependency-resolution tasks can explicitly use
`python tools/env/run.py --network bridge run -- COMMAND`.

`lock.json` pins the platform, base and certificate image digests, Ubuntu package
snapshot, release archives, Python wheels, Maven artifacts and source commits.
The certificate image supplies public CA trust to bootstrap HTTPS downloads;
no private keys, MCU certificates or firmware signatures are involved. TLS and
artifact checksum verification remain enabled. OpenSTA and CUDD are built from
locked source because this Ubuntu snapshot does not package OpenSTA.

OpenOCD 0.12.0 is built from its locked source commit with the separately
pinned JimTcl submodule and remote-bitbang support. T32 drives actual simulated
JTAG pins; the environment version probe alone does not qualify debug behavior.

The installed Ubuntu package inventory and tool versions are recorded and
checked; smoke receipts live in `build/env/smoke/receipt.json`. Scala/Chisel
primary artifacts are checksum pinned, but the full transitive sbt build,
Chisel elaboration, simulation/formal integration and compatibility qualification
belong to T07. Version checks do not prove hardware correctness or GF180 timing.

The locked OSS CAD release supplies Icarus 14 development and native Yosys
0.71+34; these differ from the historical Icarus 13/Yosys 0.33 measurements.
Ubuntu's historical Yosys is also available explicitly as `/usr/bin/yosys`.
T06 must qualify historical replay and resolve any required simulator pin;
T08 does not claim that the historical results have been reproduced.

## Non-formal validation runs

`DEADHORSE_NO_FORMAL=1` explicitly omits only the environment check's two
Z3 solver probes, including in nested environment checks. The receipt records
the omission; tool versions, pinned artifacts and compiler checks still run.
The default retains both solver controls. This variable does not disable
hardware formal jobs: a non-formal suite must also select only simulation,
unit, synthesis and timing commands.
