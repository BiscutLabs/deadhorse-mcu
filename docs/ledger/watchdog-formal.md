# Watchdog formal evidence

T26, main HEAD `72bcfacc0916b6c00d54f5c4518ab16aa46c5a47` plus local source
hashes in each receipt. None of this runs CI or closes physical reset signoff.

## Channel: unresolved

Measured commands (pinned environment):

```
python tools/env/run.py run -- python hw/ip/watchdog/formal/check.py --output build/t26/formal01
python tools/env/run.py run -- python scratch/t26_step0.py
python tools/env/run.py run -- python hw/ip/watchdog/formal/check.py --output build/t26/formal02 --cases channel break pad
```

Formal01 is preserved evidence for the initial window implementation. Review
found an elapsed-edge off-by-one in both RTL and its initial oracle; the
correction uses the independent oracle's absolute earliest-feed timestamp.
Formal02 covers the corrected window and tightens fault-to-property bindings.
Its channel source still matches the later production channel; subsequent
changes to the PWM upstream-epoch guard require fresh break qualification.

| Step-0 measurement | Measured result |
| --- | --- |
| Prepared original model | 266 cells, 455 sequential bits including `$anyinit`, no memory |
| Requested/reached | Depth 20; basecase reached step 13 before the unchanged 120-second cap; induction did not close |
| Quarter-depth diagnostic | Depth 5 bounded PASS, 0.416 s wall time |
| Half-depth diagnostic | Depth 10 bounded PASS, 9.874 s wall time |
| Covers | All five original and corrected cover jobs PASS; original minimum bounds 4,4,4,9,10; receipts contain witnesses |
| Unnecessary logic | No RAM or unrelated datapath; proof model includes countdown, captured settings, retained count and checker history |

The portfolio on the corrected full-width channel also timed out. Induction
witnesses are arbitrary-state failures, not reachable design counterexamples.
No bounds, caps or assumptions changed; no assertion was removed. Further
long sweeps are not justified. A prospective next step is a reviewed helper
relating the checker's captured settings to the active production registers,
and separate reset-hold/count properties. This is not an assumed lemma or an
accepted proof; helper work has not been authorized or run.

## Output disable

Formal02 proved the initial local break and split pad checks with ABC PDR and
qualified covers/faults. Review then identified that upstream retained STOP
also needs epoch-drain qualification. Fresh results for that final binding
belong to the frozen T26 receipt; initial break proof is not sufficient for
the revised production binding. Every environment assumption is listed in
[the block's formal contract](../../hw/ip/watchdog/formal/README.md).

Final output-disable evidence: measured command
`python tools/env/run.py run -- python dv/soc/check_watchdog.py --output build/t26/frozen01`
produced `build/t26/frozen01/output-formal/result.json`: break (3) and pad (2) assertions
unbounded PASS with ABC PDR, measured 0.265 s each; all 2/3 covers and actual
faults qualified. Its 43 source/219 artifact hashes bind the final production
output-disable RTL. The global receipt assumption text describes the channel;
the output jobs' actual SBY models contain only initial normal reset, with
unconstrained watchdog reset/epoch/idle/data thereafter, as listed in README.

The follow-up command
`python tools/env/run.py run -- python dv/soc/check_watchdog_review.py --output build/t26/review02`
keeps production unchanged, verifies all archived hashes, and passes four
affected epoch-suite tests, including the explicit missing-epoch-binding fault.
That is functional composition evidence, not a whole-SoC unbounded proof.
Channel positive acceptance remains unresolved; no helper attempt ran.
