#!/usr/bin/env python3
"""Aggregates simulator output into results/summary.md + summary.json, and assembles REPORT.md
from docs/REPORT_template.md (hand-written prose) + the generated tables."""
import csv, json, os, re, statistics, sys, glob
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B, R = f"{D}/build", f"{D}/results"
MODES = ["hover", "fixed-wing", "transition"]
CATS = ["mul", "div", "load", "store", "branch", "other"]
CFG = {
 "A": "fixed, rv32im, -O2", "B": "fixed, rv32im, -Os", "C": "fixed, rv32i (no M), -O2",
 "D": "float (soft-float), rv32im, -O2", "E": "fixed, rv32imc, -Os", "F": "fixed, rv32imc, -O2",
}
def pct(v, p): s = sorted(v); return s[min(len(s) - 1, int(p * len(s)))]
def load(cfg):
    rows = list(csv.DictReader(open(f"{B}/{cfg}/iters.csv")))
    out = {}
    for m in range(3):
        r = [x for x in rows if int(x["mode"]) == m]
        tot = [int(x["total"]) for x in r]
        d = dict(n=len(r), mean=statistics.mean(tot), min=min(tot), max=max(tot), p99=pct(tot, .99),
                 stack=max(int(x["stack"]) for x in r),
                 rvc=statistics.mean(int(x["rvc"]) for x in r), taken=statistics.mean(int(x["taken"]) for x in r))
        for c in CATS: d[c] = statistics.mean(int(x[c]) for x in r)
        d["cat_check"] = all(sum(int(x[c]) for c in CATS) == int(x["total"]) for x in r)
        out[m] = d
    return out
def nm_sizes(path):
    res = []
    for l in open(path):
        p = l.split()
        if len(p) == 4 and p[2] in "tT": res.append((p[3], int(p[1], 16)))
    return res
def sizeA(path):
    d = {}
    for l in open(path):
        p = l.split()
        if len(p) == 3 and p[0].startswith("."): d[p[0]] = int(p[1])
    return d
def su(path):
    r = []
    if os.path.exists(path):
        for l in open(path):
            p = l.rstrip("\n").split("\t")
            if len(p) >= 3: r.append((p[0].split(":")[-1] if ":" in p[0] else p[0], int(p[1]), p[2]))
    return r

res = {c: load(c) for c in list(CFG) + ["PA", "PD"]}
J = {"configs": {}}
md = []
w = md.append

# ---------------------------------------------------------- validation: target checksums vs native x86 builds
def chk(path): return [l.split()[2] for l in open(path) if l.startswith("CHK")]
host = {"fixed": chk(f"{R}/host_fixed.chk"), "float": chk(f"{R}/host_float.chk")}
w("### Validation: target run vs native x86 build of the same sources\n")
w("FNV-1a hash over all 9 outputs and the 4 quaternion words of every iteration (6000 iterations). Target ELF run in `rvsim` vs the same C compiled natively with hardware float / int arithmetic.\n")
w("| config | numeric | mode0 | mode1 | mode2 | identical to native |"); w("|---|---|---|---|---|---|")
for c in list(CFG) + ["PA", "PD"]:
    num_ = "float" if c in ("D", "PD") else "fixed"
    got = chk(f"{B}/{c}/sim.out")
    ok = got == host[num_]
    w(f"| {c} | {num_} | " + " | ".join(got) + f" | {'YES' if ok else 'NO'} |")
    assert ok, f"checksum mismatch in {c}"
w("")
# ---------------------------------------------------------- dynamic counts
w("### Dynamic instructions per `control_step` call (entry through `ret`, call overhead excluded)\n")
w("Iterations per mode: %d. mean/min/max/p99 are over iterations; breakdown columns are per-call means (they sum to the mean). RVC share = fraction of retired instructions that were 16-bit encodings.\n" % res["A"][0]["n"])
for c in CFG:
    w(f"\n**Config {c}: {CFG[c]}**\n")
    w("| mode | mean | min | max | p99 | mul | div/rem | load | store | branch/jump | other | taken br/jmp | RVC share |")
    w("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for m in range(3):
        d = res[c][m]
        w(f"| {MODES[m]} | {d['mean']:.0f} | {d['min']} | {d['max']} | {d['p99']} | {d['mul']:.0f} | {d['div']:.1f} | {d['load']:.0f} | {d['store']:.0f} | {d['branch']:.0f} | {d['other']:.0f} | {d['taken']:.0f} | {(d['rvc']/d['mean']*100 if d['mean'] else 0):.0f}% |")
    J["configs"][c] = {MODES[m]: {k: v for k, v in res[c][m].items()} for m in range(3)}
assert all(res[c][m]["cat_check"] for c in CFG for m in range(3)), "category sums != totals"

w("\n### Ratios of mean instructions per call (vs config A)\n")
w("| config | hover | fixed-wing | transition |"); w("|---|---:|---:|---:|")
for c in CFG:
    w(f"| {c} ({CFG[c]}) | " + " | ".join(f"{res[c][m]['mean']/res['A'][m]['mean']:.2f}x" for m in range(3)) + " |")

# ---------------------------------------------------------- stages
def stages(cfg):
    n = res[cfg][0]["n"]
    S = {m: {} for m in range(3)}
    for l in open(f"{B}/{cfg}/sim.out"):
        if l.startswith("STAGE "):
            p = l.split(); m = int(p[1]); S[m][p[2]] = [int(v) / n for v in p[3:]]
    return S
ORDER = ["imu_scale", "filters", "estimator", "attitude", "rate_hover", "hover_mix", "fw", "tilt_sched", "blend", "output", "glue"]
for cfg, title in (("PA", "Config A (fixed, rv32im, -O2) with stages forced `noinline`"), ("PD", "Config D (float soft-float, rv32im, -O2) with stages forced `noinline`")):
    S = stages(cfg)
    w(f"\n### Per-stage mean instructions per call: {title}\n")
    w("Stage = instructions executed inside the stage function; libgcc helpers (soft-mul/soft-float) are charged to the calling stage. `glue` = `control_step` body itself (call setup, zero-init, branches).\n")
    w("| stage | hover | fixed-wing | transition | hover (mul) | transition (mul) |"); w("|---|---:|---:|---:|---:|---:|")
    tot = [0, 0, 0]
    for s in ORDER:
        row = []
        for m in range(3):
            v = S[m].get(s, [0] * 7)[0]; row.append(v); tot[m] += v
        w(f"| {s} | " + " | ".join(f"{v:.0f}" for v in row) + f" | {S[0].get(s,[0]*7)[1]:.0f} | {S[2].get(s,[0]*7)[1]:.0f} |")
    w(f"| **total** | " + " | ".join(f"**{v:.0f}**" for v in tot) + " | | |")
    base = "A" if cfg == "PA" else "D"
    w(f"| (non-profiled config {base} mean, stages inlined) | " + " | ".join(f"{res[base][m]['mean']:.0f}" for m in range(3)) + " | | |")
    unk = [s for s in S[0] if s not in ORDER]
    if unk: w(f"\n(unlisted stages: {unk})")
    J[f"stages_{cfg}"] = {MODES[m]: S[m] for m in range(3)}
    # sanity: stage totals must equal measured totals
    for m in range(3):
        assert abs(sum(v[0] for v in S[m].values()) - res[cfg][m]["mean"]) < 1e-6, (cfg, m)

# ---------------------------------------------------------- code size / RAM / stack
w("\n### Static size (loop + helpers only; harness, init and scenario data excluded)\n")
w("Method: link `control_step.o` alone with `-Wl,-e,control_step --gc-sections -lgcc`, so only reachable code (including libgcc helpers) is counted.\n")
w("| config | .text (bytes) | of which libgcc helpers | .rodata | undefined libgcc symbols pulled in |"); w("|---|---:|---:|---:|---|")
sizes = {}
for c in CFG:
    sz = sizeA(f"{B}/{c}/loop_only.size"); syms = nm_sizes(f"{B}/{c}/loop_only.nm")
    own = [s for s in syms if s[0] == "control_step" or s[0].startswith("stage_") or s[0].startswith("pid_") or s[0].startswith("biquad") or s[0].startswith("lut16") or s[0].startswith("control_step.")]
    own_sz = sum(s[1] for s in syms if s[0].split(".")[0] in ("control_step", "biquad", "lut16", "pid_axis") or s[0].startswith("stage_"))
    lib = [s for s in syms if s not in own and s[0].split(".")[0] not in ("control_step",)]
    lib_sz = sz[".text"] - own_sz
    sizes[c] = dict(text=sz[".text"], lib=lib_sz, rodata=sz.get(".rodata", 0), libfuncs=[s[0] for s in syms if s[0].startswith("__")])
    w(f"| {c} ({CFG[c]}) | {sz['.text']} | {lib_sz} | {sz.get('.rodata', 0)} | {', '.join(sizes[c]['libfuncs']) or '-'} |")
J["sizes"] = sizes
w("\nNote: for rv32imc builds (E, F) any libgcc helpers come from the toolchain's non-compressed `rv32im` multilib, so they are not compressed; fixed-point E/F pull in none.\n")

st = {}
for l in open(f"{B}/A/sizes.nm"):
    p = l.split()
    if len(p) == 4: st[p[3]] = int(p[1], 16)
w("### Static RAM (same for fixed and float: every field is 32-bit or smaller)\n")
w("| object | bytes |"); w("|---|---:|")
w(f"| `state_t` total (params + dynamic state) | {st['probe_state']} |")
w(f"| of which `params_t` (tunables; flash-initialised, runtime-writable) | {st['probe_params']} |")
w(f"| of which dynamic filter/estimator/PID state | {st['probe_state'] - st['probe_params']} |")
w(f"| `inputs_t` | {st['probe_inputs']} |"); w(f"| `outputs_t` | {st['probe_outputs']} |")
J["ram"] = st

w("\n### Stack\n")
w("`-fstack-usage` frame of `control_step` (callee frames of helpers that were not inlined added separately), and peak stack depth observed by the simulator during any measured call (SP at entry minus lowest SP, includes libgcc helper frames).\n")
w("| config | control_step frame (static) | other non-inlined frames in control_step.c | static upper bound (control_step + largest callee) | observed peak, hover / fw / transition |"); w("|---|---:|---|---:|---|")
for c in CFG:
    s = su(f"{B}/{c}/control_step.su")
    cs = [x for x in s if x[0] == "control_step"][0][1]
    oth = [x for x in s if x[0] != "control_step"]
    big = max([x[1] for x in oth], default=0)
    w(f"| {c} | {cs} | {', '.join(f'{x[0]}:{x[1]}' for x in oth) or '-'} | {cs + big} (+ libgcc leaf frames, see observed) | " + " / ".join(str(res[c][m]['stack']) for m in range(3)) + " |")
sp = {c: [x for x in su(f"{B}/{c}/control_step.su")] for c in ("PA",)}
w("\nFrames with stages kept separate (PA build): " + ", ".join(f"{x[0]}:{x[1]}" for x in su(f"{B}/PA/control_step.su")))

# ---------------------------------------------------------- MIPS
w("\n### Required MIPS for config A (fixed-point, rv32im, -O2)\n")
w("MIPS = instructions per iteration x loop rate / 1e6. This is *instruction* throughput; see the CPI note in the report.\n")
w("| basis | instr/iter | 500 Hz raw | 500 Hz x2 | 1 kHz raw | 1 kHz x2 |"); w("|---|---:|---:|---:|---:|---:|")
A = res["A"]
wm = max(range(3), key=lambda m: A[m]["mean"]); wx = max(range(3), key=lambda m: A[m]["max"])
rows = [(f"worst-mode mean ({MODES[wm]})", A[wm]["mean"]), (f"worst-mode p99 ({MODES[wm]})", max(A[m]["p99"] for m in range(3))), (f"absolute max single iteration ({MODES[wx]})", A[wx]["max"])]
for nm_, n in rows:
    w(f"| {nm_} | {n:.0f} | {n*500/1e6:.2f} | {n*500*2/1e6:.2f} | {n*1000/1e6:.2f} | {n*1000*2/1e6:.2f} |")
J["mips"] = {nm_: n for nm_, n in rows}
w("\nSame for the other configs, worst-mode mean and absolute max (raw, 1 kHz / 500 Hz):\n")
w("| config | worst mean | 500 Hz MIPS | 1 kHz MIPS | worst max | 500 Hz MIPS | 1 kHz MIPS |"); w("|---|---:|---:|---:|---:|---:|---:|")
for c in CFG:
    a = max(res[c][m]["mean"] for m in range(3)); b = max(res[c][m]["max"] for m in range(3))
    w(f"| {c} | {a:.0f} | {a*500/1e6:.2f} | {a*1000/1e6:.2f} | {b} | {b*500/1e6:.2f} | {b*1000/1e6:.2f} |")

# cycle sensitivity (assumption-based, NOT measured)
w("\n### Cycle sensitivity (ASSUMPTION-BASED illustration, not measured)\n")
w("The simulator counts instructions, not cycles. If the CPU is not single-cycle-per-instruction, the clock needed is higher than the MIPS above. Illustrative CPI models applied to config A's measured category counts (worst mode mean):\n")
w("| model | cycles/iter | 1 kHz MHz needed | 500 Hz MHz needed |"); w("|---|---:|---:|---:|")
MODELS = [("ideal: every instruction 1 cycle", dict(mul=1, div=1, load=1, store=1, branch=1, other=1, taken=0)),
          ("mul 3, div 34, load 2, taken branch/jump +2", dict(mul=3, div=34, load=2, store=1, branch=1, other=1, taken=2)),
          ("mul 1, div 34, load 2, taken branch/jump +2", dict(mul=1, div=34, load=2, store=1, branch=1, other=1, taken=2))]
d = A[wm]
for nm_, k in MODELS:
    cyc = sum(d[c] * k[c] for c in CATS) + d["taken"] * k["taken"]
    w(f"| {nm_} | {cyc:.0f} | {cyc*1000/1e6:.2f} | {cyc*500/1e6:.2f} |")

open(f"{R}/summary.md", "w").write("\n".join(md) + "\n")
json.dump(J, open(f"{R}/summary.json", "w"), indent=1)
tpl = f"{D}/docs/REPORT_template.md"
if os.path.exists(tpl):
    open(f"{D}/REPORT.md", "w").write(open(tpl).read().replace("{{TABLES}}", "\n".join(md)))
print("wrote results/summary.md" + (", REPORT.md" if os.path.exists(tpl) else ""))
