# UART formal scope

Run `python tools/env/run.py run -- python3 hw/ip/uart/formal/check.py
--json build/t15/regmap/uart_regs.json --output build/t15/formal-new` with a
fresh output directory. The aggregate UART check generates the map first.

| Role | Claim | Method and coverage |
| --- | --- | --- |
| phase | Every bit of the grouped-carry 17-bit sum equals unsigned addition of arbitrary 16-bit operands | Unbounded combinational equality; carry-out cover; flipped sum-bit control |
| frame | One configured TX byte has start, eight data and stop bits at eight-edge periods; response accounting, TX enable and clock hold | Bounded160 edges, FIFO2, increment8192, normal polarity, scripted configuration and arbitrary accepted byte; complete-frame/busy covers; production TX register inversion control |
| wake | Pending wake persists until clear, four settled active samples capture, request equals wake | Unbounded digital AON contract; arbitrary inputs/reset, pending-after-disarm and clear/capture covers; inverted sticky-state update control |
| denied | All denied-only accesses receive errors/zero data and preserve observable disabled state | Unbounded with owner0 and all non-owner tags1..7, arbitrary address/data/strobes; denial covers; actual authorization-bypass control |

Initial reset is low; thereafter reset is arbitrary in the digital model.
HF `reset_n` is a qualified domain reset supplied by integration. The frame
harness drives its specified transaction sequence; it does not prove arbitrary
firmware programming, RX, arbitrary baud, inversion, or FIFO8/16 behavior.
The denied harness maps raw tag0 to1 so its inputs cover all denied tags
without assuming an internal signal. Wake capture is asserted after reset
warm-up and four consecutive armed/active samples. No analog metastability,
clock-start latency, reset distribution or whole-system sleep proof is claimed.

Positive safety jobs use ABC PDR, except configured TX uses bounded BTOR.
Covers and injected faults use BTOR with concrete witness requirements.
Each job has a120-second cap and one attempt. A timeout is recorded under its
exact property-role/job ID as deferred/unproved per user instruction; it is
never called proved or bounded. Counterexamples and tool errors stop acceptance
for investigation. Unsuccessful attempts remain under their original build
directories. See the task report and ledger for actual outcomes.
