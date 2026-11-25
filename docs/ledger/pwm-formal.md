# PWM formal evidence

T22, 2026-11-21. Measured on dirty main based on
`72bcfacc0916b6c00d54f5c4518ab16aa46c5a47`; exact source/model/artifact hashes
are in `build/t22/formal-frozen/result.json`. Command:
`python tools/env/run.py run -- python3 hw/ip/pwm/formal/check.py --output build/t22/formal-frozen`.

| Job | Assertions | Kind | Engine | Measured positive wall time | Cover/fault |
| --- | --- | --- | --- | --- | --- |
| channel | 12 | proved, full-width safety/update | ABC PDR / Yices induction / suprove portfolio; suprove returned PASS | 1.017 s | PASS / intended output fault rejected |
| dma | 5 | proved | ABC PDR | 0.265 s | PASS / intended request fault rejected |
| denied | 7 | proved | ABC PDR | 1.467 s | PASS / intended owner fault rejected |

Assumptions and precise scope are in the historical
`hw/ip/pwm/formal/README.md` at the source revision above. PLAN05 D97 retires
this block; the [general timer formal contract](../../hw/ip/timers/formal/README.md)
records replacement claims and the preserved DMA/ownership helpers.
No waveform-progress, whole-SoC, physical-reset or DMA-controller proof is implied.

## Channel timeout triage

Initial command used `--output build/t22/formal-first`, with PDR alone for the
channel. Its positive job timed out at the unchanged 120-second cap; covers
and the output-fault witness passed. Evidence remains intact. No unchanged
timed-out job was rerun.

| Step-0 item | Measured result |
| --- | --- |
| Prepared model | 312 sequential bits, 260 cells, no RAM, including proof monitors; `yosys -Q -T -p 'read_rtlil build/t22/formal-first/channel/correct/model/design.il; write_json build/t22/triage/model.json'`, sum Q widths of flip-flop cells in JSON |
| Requested depth / engine progress | Depth 24 configuration; PDR stalled on output 4 at frame 3 after proving other outputs; PDR is unbounded rather than a depth-24 BMC result |
| Quarter / half diagnostic | Same model, BMC depths 6 / 12: PASS in 0.315 / 0.515 s; diagnostic only, not replacements for positive proof |
| Covers | All reached; emitted witness traces contain at most six time steps in the original depth-24 cover run |
| Model contents | Only one production channel plus temporal safety monitors; no bus/other channels/RAM |

Rung one: `sby -d build/t22/triage/portfolio build/t22/triage/portfolio.sby`
on the identical emitted model with `abc pdr`, `smtbmc yices`, `aiger suprove`:
PASS in measured 1.016 s. Yices completed induction; suprove completed the
unbounded proof. Diagnostic recipes/results are in `build/t22/triage/`.
The frozen runner retains this portfolio. No further rung was needed.
