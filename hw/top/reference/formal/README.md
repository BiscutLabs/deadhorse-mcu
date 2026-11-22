# SoC control composition

## Inactive logical pads

`SocInactiveFormal.scala` binds the real `SocInactivePads` to unconstrained
inputs. Six assertions require safe QSPI, actuator, JTAG, GPIO, timer and ADC outputs and
enables at every sample, with no reset masking and no assumptions. An input
cover checks all input bits high; four faults independently enable actuator,
GPIO, timer or ADC outputs.
This is an unbounded proof of static tie-offs, not of implemented peripherals.

Run `python tools/env/run.py run -- python3 hw/top/reference/formal/check_inactive.py --output build/t20/i1/inactive-proof-fresh`.
The runner preserves assertions with firtool optimization disabled and static
assert lint disabled so the actual fault reaches the solver. It requires the
six-assertion/zero-assumption inventory and each fault identity.
`build/t20/i1/pin-contract-proof/result.json` records ABC PDR PASS, cover PASS,
and all intended counterexamples, source/artifact hashes and timings. Earlier
emission/lowering failures remain archived; they are not negative witnesses.

## I1 glue

After `dv/soc/prepare_i1.py`, run the following focused command separately for
`error`, `slot`, `memory` and `nested`, always using a fresh output directory:

```sh
python tools/env/run.py run -- python3 hw/top/reference/formal/check_i1_control.py --block slot --output build/t20/i1/slot-fresh
```

These are ABC PDR unbounded safety proofs; Z3 supplies cover witnesses and
actual faulty-subclass counterexamples. The job cap remains 120 seconds;
covers/fault search use 32 steps. Exact assertion inventories, cover counts,
harness hashes and mandatory hierarchical fault identities are checked.
Receipts bind sources and all emitted/solver artifacts. Current results and
commands are in [the SoC formal ledger](../../../../docs/ledger/soc-formal.md).

| Job | Contract checked | Fault |
| --- | --- | --- |
| error | Registered error response once per accepted request; real destination drain credit matches outstanding work | Invert endpoint response-valid |
| slot | Accepted request owns its response, at most one downstream dispatch with unchanged payload, reset cancellation, truthful quiet, finite error-backend completion | Invert slot response-valid |
| memory | Full-size retained memory permissions, response latency, zero write/error reply, exclusive bus/loader port and completion only after an allowed loader write | Invert loader completion |
| nested | Real child fabric cannot acknowledge quiet with activity, isolation or pending endpoint work | Force quiet high |

Premises are explicit: both reset inputs start low and may change arbitrarily
thereafter. Error/slot/memory use a generated one-outstanding requester that
holds request and payload through acceptance; this is an environment restriction
even though no Chisel `assume` is used. The slot's downstream endpoint is the
real finite error target. Nested uses the production 128-edge fabric and a
legal endpoint model whose response delay is chosen arbitrarily from 0–255
edges. Nested makes no upstream request-stability or admission assumption.
Its short covers show ordinary response/drain, not watchdog expiry. The long
delayed-response scenario is separately simulated by `SocNestedSpec`.

`async2sync` proves sampled reset behavior, not subcycle electrical reset
timing. Stopped-clock cancellation is separately simulated. Memory geometry is
the production 768-word array; control proof does not establish memory contents,
byte-lane integrity or retention. Those receive independent byte-array simulation.
The memory read-result cone is still present; no RAM-pruning claim is made.
Loader permission withdrawal may quarantine until reset and is not a proved
unconditional completion. Full top decode/IRQ/reset order, every independent
bridge-reset phase and CDC structural composition remain open.

## I0 local memory

Run after `dv/soc/prepare_i0.py`, in the pinned environment:

```sh
python tools/env/run.py run -- python3 hw/top/reference/formal/check_memory.py --output build/t20/formal-control-fresh
```

The output directory must be fresh. This is a focused check, not CI. The
production geometry is retained: four banks, one-edge reads. RAM data is not
observed by these control properties and can be removed by solver cone reduction.
Memory contents, byte integrity, longer latency configurations and whole-SoC
interrupt/reset composition are not proved here.

The eleven assertions comprise:

| Scope | Claim |
| --- | --- |
| Production | Instruction and data cannot both accept on one edge |
| Production | Local and remote data returns cannot collide |
| Production | Data acceptance cannot overwrite a busy slot |
| Production | MMIO acceptance cannot overwrite an offered/issued transaction |
| Public harness | Instruction and data grants are mutually exclusive |
| Public harness | Instruction response is exactly one edge after acceptance |
| Public harness | Every data response belongs to a pending client request |
| Public harness | A second data request cannot be accepted while one is pending |
| Public harness | Before epoch readiness there are no grants or responses |
| Public harness | A stalled peripheral request remains asserted |
| Public harness | Its payload remains unchanged while stalled |

Only assumption: service and client resets start asserted. Both may then
change independently at any sample edge. There are no request-stability,
response-validity or fairness assumptions. Assertions and checker state use
the same reset scope as their contract: client state is discarded on client
reset, while peripheral-held state persists until service reset or completion.
`async2sync` is sample-edge reset evidence; short asynchronous pulses are
separately simulated and are not claimed from this proof.

ABC PDR provides unbounded safety. SMTBMC/Z3 provides three cover witnesses:
fetch during MMIO, a successful data response, and a new epoch after draining
an offered request across client reset. Cover depth is 32, with the existing
120-second cap per job. The actual faulty subclass flips instruction response
validity; the checker requires its timing assertion to fail with a concrete
trace. The generated assertion identities and complete emitted/solver input
and result artifacts are bound by receipt hashes. No previous receipt is reused.

Neither eventual peripheral completion nor downstream responder correctness
is proved. Unresponsive MMIO may block a reset epoch until the fabric's existing
watchdog returns or a common service reset occurs.
