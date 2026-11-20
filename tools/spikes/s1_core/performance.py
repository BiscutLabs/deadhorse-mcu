#!/usr/bin/env python3
"""S1 faithful-F baseline measurement; stop on the unchanged 2.5 MIPS floor.

RTL retirement cycles, not QEMU instruction timing. The first stage deliberately
uses the existing ideal one-cycle responder before any memory latency sweep.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CORE = ROOT / "dv/core"
sys.path.insert(0,str(CORE))
from common import output_dir, local, run
from candidate import manifest, parameters
from lockstep import compile_sim, compare, qemu_trace
from float_compare import compare as compare_float
from float_suites import flight as float_flight
from suites import flight_program, flight_reentry

_spec = importlib.util.spec_from_file_location("historical_performance", CORE / "performance.py")
historical = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(historical)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def iteration_metrics(rows, cycles, bounds, frequency_mhz):
    """Every instruction from loop start through its backedge counts once."""
    timing = historical.loop_samples(rows,cycles,bounds)
    counts, start = [], None
    for index,row in enumerate(rows):
        if row["pc_rdata"] == bounds["start"]:
            if start is not None:
                raise ValueError("overlapping instruction-count window")
            start = index
        if row["pc_rdata"] == bounds["end"]:
            if start is None:
                raise ValueError("missing instruction-count start")
            counts.append(index-start+1)
            start = None
    if start is not None or len(counts) != len(timing):
        raise ValueError("incomplete instruction-count windows")
    samples = [dict(**sample,retired_instructions=count,cpi=sample["cycles"]/count,
                    mips=frequency_mhz*count/sample["cycles"])
               for count,sample in zip(counts,timing)]
    total_cycles = sum(item["cycles"] for item in samples)
    total_instructions = sum(counts)
    worst_cycles = max(item["cycles"] for item in samples)
    return dict(samples=samples,iterations=len(samples),total_loop_cycles=total_cycles,
                total_loop_retired_instructions=total_instructions,
                mean_cycles=statistics.mean(item["cycles"] for item in samples),worst_cycles=worst_cycles,
                aggregate_cpi=total_cycles/total_instructions,
                aggregate_mips=frequency_mhz*total_instructions/total_cycles,
                minimum_iteration_mips=min(item["mips"] for item in samples),
                frequency_mhz_assumed=frequency_mhz,
                mean_loop_us=statistics.mean(item["cycles"] for item in samples)/frequency_mhz,
                worst_loop_us=worst_cycles/frequency_mhz,
                margin_1khz_cycles=int(frequency_mhz*1000)-worst_cycles,
                margin_500hz_cycles=int(frequency_mhz*2000)-worst_cycles,
                throughput_denominator="sum of exact full-loop retirement-cycle windows; numerator is all retired instructions in those same 120 windows, including input staging, checksum and loop housekeeping",
                classification="cycles/instruction counts measured in RTL; CPI/MIPS/time/margins derived, frequency assumed pending separate timing qualification")


def compare_workload(rows, iss, binary, base, floating):
    if floating:
        return compare_float(rows,iss,binary,base)
    cleaned = historical.integer_rows(rows)
    count = compare(cleaned,cleaned,iss,binary,base)
    return dict(retirements=count,reference="independent pinned QEMU architectural state; no separate Ibex trace in this measurement")


def faults(rows,iss,binary,base,floating):
    """Actual observation corruptions, checked against QEMU, not a pre-set fail."""
    result = []
    index = next(i for i,row in enumerate(rows) if row["frd_wen"]) if floating else next(i for i,row in enumerate(rows) if row["rd_addr"])
    field = "frd_wdata" if floating else "rd_wdata"
    bad = list(rows)
    bad[index] = dict(rows[index])
    bad[index][field] ^= 1
    for name,trace in (("retired-result-bit",bad),("dropped-retirement",rows[:index]+rows[index+1:])):
        try:
            compare_workload(trace,iss,binary,base,floating)
        except ValueError as error:
            if name=="retired-result-bit" and not ("result" in str(error) or "state" in str(error)):
                raise ValueError("wrong result-fault detection: "+str(error)) from error
            if name=="dropped-retirement" and "count" not in str(error).lower():
                raise ValueError("wrong dropped-retirement detection: "+str(error)) from error
            result.append(dict(fault=name,status="rejected",reason=str(error),scope="corrupted RTL observation checked against unchanged QEMU"))
        else:
            raise ValueError("escaped negative control: "+name)
    return result


def measure(candidate, output, frequency_mhz=9.0):
    candidate = local(candidate)
    output = local(output)
    if output.exists():
        raise ValueError("measurement output must be fresh")
    output = output_dir(output)
    receipt = dict(status="running",stage="ideal-one-cycle-baseline",workloads={},
                   commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
                   frequency_mhz_assumed=frequency_mhz,throughput_floor_mips=2.5,target_mips=5.0,
                   memory="unchanged existing responder: independent instruction/data acceptance, ideal one-cycle responses, 4MiB historical fixture address space; not 16KiB placement or a macro latency",
                   exclusions=["actual sensor/driver/navigation work","DMA/bus/XIP/logging interference","interrupt entry during flight workload","physical SRAM behavior","full firmware deadline"],
                   remaining_measurements=["shared word-wide byte-enabled/banked memory, assumed 1/2/5-edge responses","interrupt arrival during FPU stall","complete integrated system loop"])
    protected = {}
    for pattern in ("dv/core/*.py","dv/core/*.cpp","dv/core/*.json","tools/env/*.json",
                    "tools/spikes/s1_core/*.py","sw/flight/loop-measurement/src/*","sw/flight/loop-measurement/scenario/*.py"):
        for path in ROOT.glob(pattern):
            if path.is_file():
                protected[str(path)] = digest(path)
    for path in candidate.rglob("*"):
        if path.is_file():
            protected[str(path)] = digest(path)
    receipt["input_sha256"] = protected
    started = time.monotonic()
    def save():
        receipt["wall_seconds"] = time.monotonic()-started
        (output / "result.json").write_text(json.dumps(receipt,indent=2)+"\n")
    save()
    try:
        parameters(candidate)
        if manifest(candidate)["implementation"] != "rv32imfc-faithful-v1":
            raise ValueError("S1 requires the authenticated faithful-F candidate")
        sim = compile_sim(output / "sim",candidate)
        for name, floating in (("fixed",False),("hard-float",True)):
            program = next(float_flight(output / name)) if floating else next(flight_program(output / name))
            directory,elf,binary,base,flags = program[:5]
            iss = qemu_trace(elf,directory,base,binary,0x80010080,floating)
            iss,duplicates = flight_reentry(iss,binary.read_bytes(),base,allow_compressed=floating)
            (directory / "iss-reentry.json").write_text(json.dumps(duplicates,indent=2)+"\n")
            disassembly = run(["riscv64-unknown-elf-objdump","-d","--disassemble=main",elf],directory,"main-disassembly").stdout
            bounds = historical.loop_boundaries(disassembly)
            cycle_file = directory / "cycles.txt"
            simulation = run(["env",f"DEADHORSE_CYCLE_TRACE={cycle_file}",sim,binary,*flags],directory,"simulate")
            rows = [json.loads(line) for line in simulation.stdout.splitlines() if line.startswith("{")]
            cycles = historical.timed_rows(rows,cycle_file.read_text())
            correctness = compare_workload(rows,iss,binary.read_bytes(),base,floating)
            controls = faults(rows,iss,binary.read_bytes(),base,floating)
            measurements = iteration_metrics(rows,cycles,bounds,frequency_mhz)
            receipt["workloads"][name] = dict(status="measured; independent architectural comparison passed",
                boundaries=bounds,correctness=correctness,negative_controls=controls,
                loop=measurements,arithmetic=historical.arithmetic(rows,cycles),
                arithmetic_scope="retirement spacing, including pipeline/fetch effects; not isolated execution-unit latency",
                elf_sha256=digest(elf),binary_sha256=digest(binary),simulation_sha256=digest(directory / "simulate.log"),
                cycles_sha256=digest(cycle_file),qemu_trace_sha256=digest(directory / "qemu.trace"))
            print(name+": "+json.dumps({key:measurements[key] for key in ("mean_cycles","worst_cycles","aggregate_cpi","aggregate_mips","worst_loop_us")}),flush=True)
            save()
            if measurements["aggregate_mips"] < receipt["throughput_floor_mips"]:
                receipt["status"] = "blocked_throughput_floor"
                receipt["stop_reason"] = f"{name}: {measurements['aggregate_mips']:.6f} MIPS < unchanged 2.5 MIPS floor at assumed {frequency_mhz:g} MHz; no latency sweep or optimization started"
                break
        else:
            receipt["status"] = "baseline_pass_remaining_measurements_unrun"
        for name,value in protected.items():
            if digest(Path(name)) != value:
                raise ValueError("measurement input changed: "+name)
    except Exception as error:
        receipt.update(status="failed",error=f"{type(error).__name__}: {error}")
    save()
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate",required=True)
    parser.add_argument("--output",required=True)
    arguments = parser.parse_args()
    result = measure(arguments.candidate,arguments.output)
    print(json.dumps({key:result[key] for key in ("status","stop_reason","error","wall_seconds") if key in result}))
    raise SystemExit(0 if result["status"]=="baseline_pass_remaining_measurements_unrun" else 1)
