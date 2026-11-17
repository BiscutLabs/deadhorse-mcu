#!/usr/bin/env python3
"""Pinned S3 representative firmware measurements; no MCU timing claims."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import struct
import subprocess
import time
import urllib.request
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "sw/flight/memory-measurement"
HISTORICAL = ROOT / "sw/flight/loop-measurement"
LOCK = Path(__file__).with_name("bmi270.lock.json")
PREFIX = "riscv64-unknown-elf-"
LIMIT = 12 * 1024


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fnv(values):
    value = 2166136261
    for item in values:
        value = ((value ^ item) * 16777619) & 0xffffffff
    return value


def f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def bits(value):
    return struct.unpack("<I", struct.pack("<f", value))[0]


def relocation_edges(dump, functions):
    """Keep function ownership across objdump's local basic-block labels."""
    edges = {name: set() for name in functions}
    owner = None
    for line in dump.splitlines():
        if line.startswith("Disassembly of section "):
            owner = None
        header = re.match(r"[0-9a-f]+ <([^>]+)>:", line)
        if header and header[1] in functions:
            owner = header[1]
        relocation = re.search(r"R_RISCV_(?:CALL_PLT|CALL|JAL|BRANCH|HI20|PCREL_HI20)\s+(\S+)", line)
        if relocation and owner in edges:
            target = relocation[1].split("+")[0]
            if target in functions:
                edges[owner].add(target)
    return edges


def linked_edges(dump, symbols):
    """Final linked direct branches also cover any retained libgcc functions."""
    functions = {s["name"] for s in symbols if s["kind"] in "tT"}
    edges = {name:set() for name in functions}
    owner = None
    for line in dump.splitlines():
        header = re.match(r"[0-9a-f]+ <([^>]+)>:",line)
        if header and header[1] in functions:
            owner = header[1]
        target = re.search(r"\b(?:jal|j|beq\w*|bne\w*|blt\w*|bge\w*)\s+.*<([^>+]+)(?:\+[^>]*)?>",line)
        if owner in edges and target and target[1] in functions and target[1] != owner:
            edges[owner].add(target[1])
    return edges


def stack_frame(name, frames):
    if name in frames:
        return frames[name]
    # GCC .su omits the numeric suffix of IPA clone names while ELF retains it.
    family = re.sub(r"\.(isra|constprop|part)\.\d+",r".\1",name)
    candidates = [value for key,value in frames.items()
                  if re.sub(r"\.(isra|constprop|part)\.\d+",r".\1",key) == family]
    if not candidates:
        raise ValueError("hot function missing stack usage evidence: "+name)
    return max(candidates)


def checked_stack_pointer(value, initialized):
    if 0x80070000 <= value <= 0x80080000:
        return True
    if initialized:
        raise ValueError(f"stack pointer outside QEMU fixture allocation: {value:#x}")
    return False


def check_records(text, config_hash, lite=False):
    """Independent protocol/data oracle; never imports compiled fixture code."""
    rows = [[int(word, 16) for word in line.split()] for line in text.splitlines() if line.strip()]
    if lite:
        expected = [[0x50, frame, zlib.crc32(bytes((frame+i) & 255 for i in range(128))), frame+1]
                    for frame in range(4)]
        if rows != expected:
            raise ValueError("lite CRC/wake oracle mismatch")
        return {"frames": 4, "oracle": "Python zlib CRC32 and wake sequence"}
    if not rows or rows[0] != [0x10, 0, 8192, 128, config_hash, 0, 1]:
        raise ValueError("BMI270 configuration upload/status mismatch")
    cursor, previous = 1, [0] * 9
    velocity, position = [0.0] * 3, [0.0] * 3
    checksum = 0
    for frame in range(16):
        acc = [100+frame, -200-frame, 2048]
        gyro = [12+frame, 12-2*frame, 12+3*frame]
        for axis in range(3):
            velocity[axis] = f32(velocity[axis] + f32(acc[axis]/1024.0))
            position[axis] = f32(position[axis] + f32(velocity[axis]/1024.0))
        expected = [0x20, frame, (frame+1)*1000, 256+frame*32,
                    *(v & 0xffffffff for v in acc+gyro), *(bits(v) for v in position), frame+1]
        if cursor >= len(rows) or rows[cursor] != expected:
            raise ValueError(f"sample/timestamp/navigation/trap mismatch at frame {frame}")
        cursor += 1
        if cursor >= len(rows) or rows[cursor][:2] != [0x30, frame] or len(rows[cursor]) != 11:
            raise ValueError("missing staged actuator command record")
        staged = rows[cursor][2:]
        if any(not 48 <= value <= 2047 for value in staged[:3]) or any(not 900 <= value <= 2100 for value in staged[3:]):
            raise ValueError("actuator endpoint mismatch")
        cursor += 1
        for channel in range(9):
            if cursor >= len(rows) or rows[cursor] != [0x31, frame, channel, fnv(previous)]:
                raise ValueError(f"partial actuator publication at frame {frame}, channel {channel}")
            cursor += 1
        if cursor >= len(rows) or rows[cursor] != [0x32, frame, frame+1, fnv(staged)]:
            raise ValueError("atomic actuator commit mismatch")
        cursor += 1
        previous = staged
        checksum += ((256+frame*32) & 255) + (staged[0] & 255) + (staged[8] & 255) + (staged[7] & 255)
    if rows[cursor:] != [[0x40, checksum, 24, 1, 16]]:
        raise ValueError("DMA/buffer checksum or final trap count mismatch")
    return {"frames": 16, "sensor_components_checked": 96, "precommit_snapshots_checked": 144,
            "postcommit_snapshots_checked": 16, "trap_entries_checked": 16,
            "scope": "sensor transport, navigation fixture, publication and DMA descriptors; not independent flight-control dynamics"}


class Runner:
    def __init__(self, output):
        self.output = output
        self.commands = []

    def command(self, command, directory, name, allowed=(0,), timeout=60):
        started = time.monotonic()
        entry = {"command": [str(x) for x in command], "timeout_seconds": timeout,
                 "log": str(directory / name)}
        self.commands.append(entry)
        try:
            process = subprocess.run([str(x) for x in command], cwd=ROOT, text=True,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        except subprocess.TimeoutExpired as error:
            for suffix, contents in (("stdout",error.stdout),("stderr",error.stderr)):
                (directory / (name+"."+suffix)).write_bytes(contents.encode() if isinstance(contents,str) else contents or b"")
            entry.update(status="timeout", wall_seconds=time.monotonic()-started)
            raise
        (directory / (name+".stdout")).write_text(process.stdout)
        (directory / (name+".stderr")).write_text(process.stderr)
        entry.update(returncode=process.returncode, wall_seconds=time.monotonic()-started)
        if process.returncode not in allowed:
            raise RuntimeError(f"{name} exited {process.returncode}: {process.stderr[-2000:]}")
        return process.stdout

    def upstream(self):
        lock = json.loads(LOCK.read_text(encoding="utf-8-sig"))
        destination = self.output / "upstream"
        destination.mkdir()
        for name, entry in lock["files"].items():
            target = destination / name
            cached = ROOT / "build/s3-prep/upstream" / name
            if cached.exists() and sha(cached) == entry["sha256"]:
                shutil.copyfile(cached, target)
            else:
                with urllib.request.urlopen(entry["url"], timeout=30) as response:
                    target.write_bytes(response.read())
            if sha(target) != entry["sha256"] or target.stat().st_size != entry["bytes"]:
                raise ValueError(f"upstream pin mismatch: {name}")
        # Reading immutable vendor data is not an oracle made from our firmware.
        text = (destination / "bmi270.c").read_text()
        match = re.search(r"const uint8_t bmi270_config_file\[\]\s*=\s*\{(.*?)\};", text, re.S)
        if not match:
            raise ValueError("pinned BMI270 configuration initializer missing")
        blob = bytes(int(token, 16) for token in re.findall(r"0x([0-9a-fA-F]{2})", match[1]))
        if len(blob) != 8192:
            raise ValueError("pinned configuration length mismatch")
        return destination, {"bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest(), "fnv1a": fnv(blob)}

    def build(self, name, opt, upstream, config, fault=None, lite=False):
        directory = self.output / name
        directory.mkdir()
        self.command(["python3", HISTORICAL / "scenario/gen_params.py", directory / "params_gen.inc"], directory, "params")
        architecture, abi = ("rv32e_zicsr", "ilp32e") if lite else ("rv32imfc_zicsr", "ilp32f")
        flags = ["-march="+architecture, "-mabi="+abi, opt, "-ffreestanding", "-nostdlib", "-fno-builtin",
                 "-ffunction-sections", "-fdata-sections", "-fstack-usage", "-fno-common", "-msmall-data-limit=0",
                 "-ffp-contract=off", "-Wall", "-Wextra", "-Werror", "-I"+str(SOURCE / "compat"),
                 "-I"+str(upstream), "-I"+str(HISTORICAL / "src"), "-I"+str(directory),
                 "-DNUM_FLOAT", "-DEXPECT_CONFIG_FNV="+str(config["fnv1a"])+"u"]
        if fault:
            flags += ["-D"+fault]
        files = [SOURCE / ("lite_start.S" if lite else "start.S"), SOURCE / "runtime.c", SOURCE / ("lite.c" if lite else "main.c")]
        if not lite:
            files += [upstream / "bmi2.c", upstream / "bmi270.c", HISTORICAL / "src/control_step.c", HISTORICAL / "src/control_init.c"]
        objects = []
        for file in files:
            obj = directory / (file.stem+".o")
            self.command([PREFIX+"gcc", *flags, "-c", file, "-o", obj], directory, "compile-"+file.stem)
            objects.append(obj)
        elf = directory / "firmware.elf"
        self.command([PREFIX+"gcc", *flags, "-T", SOURCE / "link.ld", "-Wl,--gc-sections",
                      "-Wl,-Map="+str(directory / "firmware.map"), *objects, "-lgcc", "-o", elf], directory, "link")
        return directory, elf, objects

    def execute(self, directory, elf, config, lite=False, trace=True, fault=None):
        args = ["qemu-system-riscv32", "-machine", "virt", "-cpu", "rv32", "-nographic", "-bios", "none",
                "-device", f"loader,file={elf},cpu-num=0"]
        if trace:
            args += ["-singlestep", "-d", "cpu", "-D", str(directory / "qemu.trace")]
        stdout = self.command(args, directory, "qemu", allowed=(0, 2) if fault == "BAD_CONFIG" else (0,), timeout=60)
        if fault:
            expected = {"BAD_CONFIG": "configuration", "BAD_SAMPLE": "sample/", "BAD_PUBLISH": "partial actuator", "BAD_LITE_CRC":"lite CRC"}[fault]
            try:
                check_records(stdout, config["fnv1a"],lite)
            except ValueError as error:
                if expected not in str(error):
                    raise ValueError(f"negative control failed for wrong reason: {error}") from error
                return {"status": "detected", "fault": fault, "reason": str(error)}
            raise ValueError(f"negative control escaped: {fault}")
        return check_records(stdout, config["fnv1a"], lite)

    def measure(self, directory, elf, objects, lite=False):
        nm = self.command([PREFIX+"nm", "-S", "--defined-only", elf], directory, "symbols")
        symbols = []
        for line in nm.splitlines():
            match = re.match(r"([0-9a-f]+) ([0-9a-f]+) ([A-Za-z]) (\S+)$", line)
            if match:
                symbols.append({"address": int(match[1],16), "bytes": int(match[2],16), "kind": match[3], "name": match[4]})
        functions = {s["name"] for s in symbols if s["kind"] in "tT"}
        final_dump = self.command([PREFIX+"objdump", "-d", elf], directory, "disassembly")
        edges = linked_edges(final_dump,symbols)
        for obj in objects:
            dump = self.command([PREFIX+"objdump", "-dr", obj], directory, "relocations-"+obj.stem)
            for name, targets in relocation_edges(dump,functions).items():
                edges[name].update(targets)
        if not lite:
            edges["bmi2_get_regs"].update(("sensor_read","sensor_delay"))
        roots = ["lite_hot_loop"] if lite else ["run_hot_loop", "trap_entry"]
        closure, work = set(), roots[:]
        while work:
            name = work.pop()
            if name in closure:
                continue
            if name not in functions:
                raise ValueError("missing hot root/callee: "+name)
            closure.add(name)
            work += sorted(edges[name]-closure)
        required = {"lite_iteration","hex","line"} if lite else {"flight_iteration","control_step","publish","hex","line","sensor_read","sensor_delay"}
        if not required <= closure:
            raise ValueError("incomplete hot closure: "+str(sorted(required-closure)))
        # Parent main frame remains live across the hot loop; entry/diagnostic
        # text stays cold. GCC static stack records supplement observed SP.
        areas = self.command([PREFIX+"size", "-A", elf], directory, "sections")
        sections = {match[1]: int(match[2]) for line in areas.splitlines()
                    if (match := re.match(r"(\.\S+)\s+(\d+)\s+\d+", line))}
        hot = sum(s["bytes"] for s in symbols if s["name"] in closure and s["kind"] in "tT")
        state = sections.get(".data",0)+sections.get(".bss",0)
        model_state = sum(s["bytes"] for s in symbols if s["name"] == "sensor")
        cold_blob = sum(s["bytes"] for s in symbols if s["name"] == "bmi270_config_file")
        constants = sections.get(".rodata",0)-cold_blob
        low, snapshots, hot_low, in_hot = 0x80080000, 0, 0x80080000, False
        start_hot = next(s["address"] for s in symbols if s["name"] == roots[0])
        with (directory / "qemu.trace").open() as trace:
            for line in trace:
                pc = re.match(r"\s*pc\s+([0-9a-f]+)", line)
                if pc and int(pc[1],16) == start_hot:
                    in_hot = True
                sp = re.search(r"x2/sp\s+([0-9a-f]+)", line)
                if sp:
                    value = int(sp[1],16)
                    if checked_stack_pointer(value, snapshots > 0):
                        low = min(low,value); snapshots += 1
                        if in_hot:
                            hot_low = min(hot_low,value)
        if not snapshots or not in_hot:
            raise ValueError("stack trace did not reach hot workload")
        stack = 0x80080000-low
        static_frames = {}
        for path in directory.glob("*.su"):
            for row in path.read_text().splitlines():
                location, amount, qualification = row.split("\t")
                if qualification != "static":
                    raise ValueError("static stack bound unavailable: "+row)
                name = location.rsplit(":",1)[-1]
                static_frames[name] = max(static_frames.get(name,0),int(amount))
        if not lite:
            static_frames["trap_entry"] = 256
        def chain(name, visited=frozenset()):
            if name in visited:
                raise ValueError("recursive hot call graph requires explicit stack review: "+name)
            return stack_frame(name,static_frames) + max((chain(child,visited|{name}) for child in edges[name] if child != name),default=0)
        normal_chain = chain(roots[0])
        interrupt_chain = 0 if lite else chain("trap_entry")
        reserved_stack = max(stack, static_frames["main"]+normal_chain+interrupt_chain)
        working = hot+constants+state-model_state+reserved_stack
        result = {"classification": "measured ELF sizes and observed QEMU stack pointer; estimated sum for SRAM allocation",
                  "text_bytes": sections.get(".text",0), "hot_code_bytes": hot,
                  "cold_code_bytes": sections.get(".text",0)-hot, "cold_config_bytes": cold_blob,
                  "hot_constants_conservative_bytes": constants, "state_and_buffers_bytes": state,
                  "sensor_model_only_state_bytes": model_state, "candidate_state_and_buffers_bytes": state-model_state,
                  "stack_observed_peak_bytes": stack, "stack_observed_after_first_iteration_bytes": 0x80080000-hot_low,
                  "stack_reserved_single_trap_bytes":reserved_stack,
                  "stack_ordinary_call_chain_bytes":normal_chain, "stack_trap_call_chain_bytes":interrupt_chain,
                  "stack_snapshots": snapshots, "candidate_sram_working_set_bytes": working,
                  "including_sensor_model_sram_bytes": working+model_state,
                  "baseline_capacity_bytes": 3072 if lite else 16384,
                  "review_threshold_bytes": None if lite else LIMIT,
                  "hot_roots": roots, "hot_functions": sorted(closure),
                  "hot_call_edges":{name:sorted(edges[name]) for name in sorted(closure)},
                  "indirect_callbacks_explicitly_included": [] if lite else ["sensor_read", "sensor_delay"],
                  "symbols": symbols,
                  "static_stack_records": {p.name:p.read_text() for p in directory.glob("*.su")},
                  "stack_limitations": "Observed peaks are exercised paths only. Allocation also reserves conservative GCC static hot-call chain plus one 256-byte full GPR/F trap and handler on its deepest point, with main live. No nested traps; reviewed indirect read/delay callbacks only. Cold init stack is observed, not a whole-program bound; unexercised errors may need more.",
                  "allocation_limitations": "All retained non-config constants counted hot, including init template. UART observation/model code is included in hot closure. Actual SPI MMIO callbacks, complete navigation, scheduler, drivers and lite loader remain unimplemented."}
        (directory / "measurement.json").write_text(json.dumps(result, indent=2)+"\n")
        return result


def run(output):
    output = Path(output).resolve()
    if not output.is_relative_to(ROOT / "build"):
        raise ValueError("output must be under repository build/")
    output.mkdir(parents=True, exist_ok=False)
    runner = Runner(output)
    result = {"status":"running", "commit": subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
              "commands":runner.commands, "profiles":{}, "negative_controls":[], "scope":"representative S3 memory fixture, not flight-qualified firmware or MCU timing"}
    owned = [p for p in SOURCE.rglob("*") if p.is_file()] + [Path(__file__),LOCK,Path(__file__).with_name("test_firmware.py")]
    historical = [HISTORICAL / "src" / name for name in ("control_step.c","control_init.c","control.h","num_float.h")]
    historical += [HISTORICAL / "scenario/gen_params.py", ROOT / "tools/env/lock.json", ROOT / "dv/core/iss.json"]
    result["source_sha256"] = {str(p.relative_to(ROOT)):sha(p) for p in owned+historical}
    started = time.monotonic()
    try:
        pin = json.loads((ROOT / "dv/core/iss.json").read_text())
        actual = runner.command(["dpkg-query","-W","-f=${Version}",pin["package"]], output, "qemu-pin").strip()
        if actual != pin["package_version"]:
            raise ValueError("QEMU package differs from pinned environment")
        result["compiler"] = runner.command([PREFIX+"gcc","--version"],output,"compiler").splitlines()[0]
        upstream, config = runner.upstream()
        result["config"] = config
        result["upstream"] = {"lock":json.loads(LOCK.read_text(encoding="utf-8-sig")),
                              "actual_sha256":{p.name:sha(p) for p in upstream.iterdir()}}
        for name, opt, lite in (("size","-Os",False),("speed","-O2",False),("lite-size","-Os",True),("lite-speed","-O2",True)):
            directory, elf, objects = runner.build(name,opt,upstream,config,lite=lite)
            behavior = runner.execute(directory,elf,config,lite=lite)
            measurement = runner.measure(directory,elf,objects,lite=lite)
            result["profiles"][name] = {"flags":opt,"elf_sha256":sha(elf),"behavior":behavior,"measurement":measurement}
            print(name, "hot",measurement["hot_code_bytes"],"working",measurement["candidate_sram_working_set_bytes"],flush=True)
        for fault in ("BAD_SAMPLE","BAD_PUBLISH","BAD_CONFIG"):
            directory, elf, _ = runner.build(fault.lower(),"-Os",upstream,config,fault=fault)
            result["negative_controls"].append(runner.execute(directory,elf,config,trace=False,fault=fault))
        directory,elf,_ = runner.build("bad_lite_crc","-Os",upstream,config,fault="BAD_LITE_CRC",lite=True)
        result["negative_controls"].append(runner.execute(directory,elf,config,lite=True,trace=False,fault="BAD_LITE_CRC"))
        result["review_required_profiles"] = [name for name, profile in result["profiles"].items()
            if (profile["measurement"]["candidate_sram_working_set_bytes"] > (3072 if name.startswith("lite") else LIMIT)
                or (not name.startswith("lite") and profile["measurement"]["hot_code_bytes"] > LIMIT))]
        result["status"] = "review_required" if result["review_required_profiles"] else "pass"
        result["upstream_unchanged"] = all(sha(upstream/name)==entry["sha256"] for name,entry in json.loads(LOCK.read_text(encoding="utf-8-sig"))["files"].items())
        if not result["upstream_unchanged"]:
            raise ValueError("upstream sources changed while executing")
        if any(sha(ROOT/name)!=digest for name,digest in result["source_sha256"].items()):
            raise ValueError("measurement sources changed while executing")
    except Exception as error:
        result["status"] = "failed"
        result["error"] = f"{type(error).__name__}: {error}"
    result["wall_seconds"] = time.monotonic()-started
    (output / "result.json").write_text(json.dumps(result,indent=2)+"\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    arguments = parser.parse_args()
    receipt = run(arguments.output)
    print(json.dumps({key:receipt[key] for key in ("status","wall_seconds","error","review_required_profiles") if key in receipt}))
    raise SystemExit(0 if receipt["status"] == "pass" else 1)
