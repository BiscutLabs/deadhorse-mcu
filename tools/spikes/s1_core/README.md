# S1 core baseline measurement

Incomplete spike: the initial faithful-F measurement reached the brief's
2.5 MIPS stop threshold. See `docs/plan/tasks/reports/S1.md` for the measured
results, assumptions and outstanding work. No production RTL is changed.

Use the pinned environment and an authenticated freshly emitted faithful-F
candidate. The report gives emission/package/timing commands. Then run:

```sh
python tools/env/run.py run -- python3 -m unittest discover -s dv/core -p s1_test_performance.py -v
python tools/env/run.py run -- python3 tools/spikes/s1_core/performance.py --candidate build/s1/candidate --output build/s1/performance-new
```

The output directory must be fresh. `result.json` records input hashes,
architectural comparisons against QEMU, rejected observation corruptions,
exact loop windows and raw counts. Cycles are measured by the RTL simulator;
derived MIPS and microseconds use the approved 9 MHz trial. Both workloads
run on the F-enabled core with the existing ideal one-cycle memory responder.
This is not the S3 banked-memory integration or a full firmware deadline.

Exit 1 with `blocked_throughput_floor` is an honest stop, not a test to skip
or weaken. Exit 0 means only the baseline measurements passed; remaining S1
work would still be required. The complete `check.py` acceptance interface
does not yet exist. No formal proof or CI tier is run by this tool.
