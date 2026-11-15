"""Pinned RV32IMC architectural tests and the existing T02 flight binary."""
import hashlib
import json
from pathlib import Path

from common import ROOT, output_dir, run
from lockstep import BASE, compile_sim, compare, qemu_trace, architectural_effect


def flight_reentry(records,binary,base):
    """Validate QEMU's repeated post-MMIO load prestate; never drop a retirement.

    Only identical consecutive snapshots at a RAM load immediately after a
    T02 marker store qualify. A retired load advances PC, so this duplicate
    cannot be a second architectural execution. Other repeats stay visible.
    """
    result,duplicates = [],[]
    for index,record in enumerate(records):
        if len(result)>=2 and record == result[-1]:
            before = result[-2]
            def instruction(row):
                offset = row['pc']-base
                if not 0 <= offset <= len(binary)-4:
                    return 0
                return int.from_bytes(binary[offset:offset+4],'little')
            store,load = instruction(before),instruction(record)
            if store & 0x707f == 0x2023 and load & 0x7f == 3 and record['pc']==before['pc']+4:
                _,access = architectural_effect(store,before['regs'])
                _,loaded = architectural_effect(load,record['regs'])
                if (access and access[0] and access[1] in (0x10000000,0x10000004)
                        and before['regs']==record['regs'] and loaded and not loaded[0]
                        and base <= loaded[1] < base+4*1024*1024):
                    duplicates.append(dict(raw_index=index,store_pc=before['pc'],load_pc=record['pc'],
                                           marker_address=access[1],marker_value=access[3]))
                    continue
        result.append(record)
    return result,duplicates


def arch_programs(output):
    root = ROOT/'dv/core/arch'
    lock = json.loads((root/'lock.json').read_text())
    for name,digest in lock['files'].items():
        if hashlib.sha256((root/'upstream'/name).read_bytes()).hexdigest() != digest:
            raise ValueError(f'Architectural test hash mismatch: {name}')
    for group in ('rv32ui','rv32um','rv32uc'):
        for source in sorted((root/'upstream/isa'/group).glob('*.S')):
            directory = output_dir(output/f'{group}-{source.stem}')
            elf,binary = directory/'program.elf',directory/'program.bin'
            run(['riscv64-unknown-elf-gcc','-march=rv32imc_zicsr_zifencei','-mabi=ilp32',
                 '-nostdlib','-Wl,--no-relax','-T','dv/core/arch/link.ld',
                 '-I'+str(root),'-I'+str(root/'upstream/isa/macros/scalar'),source,'-o',elf],directory,'compile')
            run(['riscv64-unknown-elf-objcopy','-O','binary',elf,binary],directory,'binary')
            yield directory,elf,binary,BASE,[]


def flight_program(output):
    # Reuse the exact ELF built and checked by T02's existing QEMU crosscheck,
    # config A: fixed-point RV32IM, 40 scenario iterations per flight mode.
    elf = ROOT/'sw/flight/loop-measurement/build/q/A/prog.elf'
    if not elf.exists():
        raise ValueError('Run the required T02 check.sh first to build its workload binary')
    directory = output_dir(output/'T02-A')
    raw = directory/'workload.bin'
    run(['riscv64-unknown-elf-objcopy','-O','binary',elf,raw],directory,'binary')
    base,entry,bootstrap = 0x80000000,0x80000000,0x80010080
    displacement = entry-bootstrap
    jump = (((displacement>>20)&1)<<31 | ((displacement>>1)&1023)<<21 |
            ((displacement>>11)&1)<<20 | ((displacement>>12)&255)<<12 | 0x6f)
    workload = raw.read_bytes()
    if len(workload) > bootstrap-base:
        raise ValueError('T02 workload overlaps bootstrap reservation')
    image = bytearray(bootstrap-base+4)
    image[:len(workload)] = workload
    image[-4:] = jump.to_bytes(4,'little')
    binary = directory/'program.bin'
    binary.write_bytes(image)
    (directory/'image.json').write_text(json.dumps(dict(
        elf=str(elf.relative_to(ROOT)),sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),
        workload_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),
        entry=entry,bootstrap=bootstrap,bootstrap_instruction=jump,
        notes='Original T02 ELF/loaded bytes unchanged; one JAL enters its aligned entry from Ibex reset vector'),indent=2)+'\n')
    yield directory,elf,binary,base,['flight']


def run_suites(candidate, selected, output):
    names = selected.split(',')
    if not names or len(set(names)) != len(names) or set(names)-{'arch','flight'}:
        raise ValueError('Suites must be arch, flight, or arch,flight')
    sims = [compile_sim(output/'reference',original=True),compile_sim(output/'candidate',candidate)]
    results = {}
    for suite in names:
        count = 0
        programs = []
        generator = arch_programs(output/'arch') if suite=='arch' else flight_program(output/'flight')
        for directory,elf,binary,base,flags in generator:
            traces = []
            for label,sim in zip(('reference','candidate'),sims):
                result = run([sim,binary,*flags],directory,label+'-run')
                traces.append([json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')])
            iss = qemu_trace(elf,directory,base,binary if flags else None,0x80010080 if flags else None)
            if flags:
                iss,duplicates = flight_reentry(iss,binary.read_bytes(),base)
                (directory/'iss-reentry.json').write_text(json.dumps(duplicates,indent=2)+'\n')
            retired = compare(*traces,iss,binary.read_bytes(),base)
            count += retired
            programs.append(dict(name=directory.name,retirements=retired))
            (directory/'result.json').write_text(json.dumps(dict(status='pass',retirements=retired),indent=2)+'\n')
            print(f'PASS {suite}/{directory.name}: {retired} retirements agree',flush=True)
        if not programs:
            raise ValueError(f'Empty suite: {suite}')
        results[suite] = dict(status='pass',retirements=count,programs=programs)
        (output/'result.json').write_text(json.dumps(dict(status='running',suites=results),indent=2)+'\n')
    (output/'result.json').write_text(json.dumps(dict(status='pass',suites=results),indent=2)+'\n')
    print('PASS lockstep suites: '+', '.join(f'{n}={r["retirements"]}' for n,r in results.items()),flush=True)
    return 0
