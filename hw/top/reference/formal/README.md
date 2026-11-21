# I0 local-memory control composition

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
