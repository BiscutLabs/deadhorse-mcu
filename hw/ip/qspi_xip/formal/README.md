# Native flash scheduler safety

Run `python tools/env/run.py run -- python hw/ip/qspi_xip/formal/check.py --output build/t30/<fresh-directory>`.
The production QspiScheduler is elaborated with an interface scoreboard.
Six assertions check read/command response ownership, zero data on error,
little-endian native result, and read/command result stability except on their
own response. ABC PDR proves safety unbounded. The endian fault removes the
production byte permutation; the corresponding result assertion must fail.
Four BTOR covers witness successful nonzero/error reads and both kinds of
completion with the other producer outstanding.

The only assumption is initial reset low, imposed by fminit; reset, requests,
configuration, engine busy/done and result remain arbitrary thereafter. The
clock is the single main clock. No flash progress assumption is added. This
does not prove engine physical timing, arbitration liveness or flash data
validity. Independent pin-model and replenished-queue simulation check those
digital integration behaviors, including the real preference fault. The T29
engine and ownership proofs are rerun separately. Existing job caps remain
120 seconds; faults/covers use the existing 128-step bound.

Receipts include source/model/artifact hashes, solver identity, time, status,
cover witnesses and the exact expected failed assertion. Task results belong
in the T30 report; an unbounded safety proof is not a bounded frame-time proof.
