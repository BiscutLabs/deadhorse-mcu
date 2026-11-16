"""Port-only RVFI comparison against the immutable reference and pinned QEMU."""
import argparse
import copy
import json
import re
import sys

from common import CONFIG, ROOT, VENDOR, adapted_sources, inputs, local, output_dir, run

BASE = 0x80000080


def compile_sim(output, candidate=None, original=False):
    output = output_dir(output)
    lock = inputs()
    sources = ([str(VENDOR / p) for p in lock['sources']] if original else adapted_sources(output, lock))
    if candidate:
        if local(candidate).is_dir():
            from candidate import sources as candidate_sources
            sources = candidate_sources(candidate,lock,output)
        else:
            original_top = next(p for p in sources if p.endswith('/ibex_top.sv'))
            sources[sources.index(original_top)] = str(local(candidate))
    from candidate import parameters as candidate_parameters
    parameters = candidate_parameters(candidate)
    from candidate import manifest
    floating=bool(candidate and local(candidate).is_dir() and (manifest(candidate) or {}).get('implementation')=='rv32imfc-v1')
    run(['verilator', '--cc', '--exe', '--build', '-j', '4', '--top-module', 'ibex_top',
         *(['-CFLAGS','-DDEADHORSE_F'] if floating else []),
         '-Wno-fatal', '--Mdir', str(output / 'obj'),
         *['-D' + p for p in lock['defines']],
         *['-I' + str(VENDOR / p) for p in lock['include_dirs']],
         *[f'-G{k}={v}' for k, v in parameters.items()],
         *sources, str(ROOT / 'dv/core/sim_main.cpp')], output, 'compile')
    return output / 'obj/Vibex_top'


def build_program(output):
    elf = output / 'program.elf'
    run(['riscv64-unknown-elf-gcc', '-march=rv32imc_zicsr', '-mabi=ilp32', '-nostdlib',
         '-Wl,--no-relax', '-T', 'dv/core/link.ld', 'dv/core/program.S', '-o', str(elf)], output, 'program')
    run(['riscv64-unknown-elf-objcopy', '-O', 'binary', str(elf), str(output / 'program.bin')], output, 'binary')
    return elf


def qemu_trace(elf, output, base=BASE, image=None, entry=None, floating=False):
    pin = json.loads((ROOT / 'dv/core/iss.json').read_text())
    actual = run(['dpkg-query', '-W', '-f=${Version}', pin['package']], output, 'iss-pin').stdout.strip()
    if actual != pin['package_version']:
        raise ValueError('ISS package pin mismatch')
    loader = ['-device',f'loader,file={elf},cpu-num=0']
    entry = base if entry is None else entry
    if image is not None:
        loader = ['-device',f'loader,file={image},addr={base},force-raw=on',
                  '-device',f'loader,addr={entry},cpu-num=0']
    cpu=pin['cpu']+(',a=false,zawrs=false,d=false,h=false,s=false' if floating else '')
    run([pin['executable'], '-machine', pin['machine'], '-cpu', cpu, '-nographic',
         '-bios', 'none', *loader, '-singlestep', '-d', 'cpu,fpu' if floating else 'cpu', '-D', str(output / 'qemu.trace')],
        output, 'qemu', timeout=30)
    return read_qemu_trace(output/'qemu.trace',entry,floating)


def read_qemu_trace(path,entry=BASE,floating=False):
    records = []
    current = None
    for line in path.open():
        match = re.match(r'^\s*pc\s+([0-9a-f]+)', line)
        if match:
            if current is not None:
                records.append(current)
            current = dict(pc=int(match[1], 16), regs={})
            if floating: current['fregs']={}
        if current is not None:
            for index, value in re.findall(r'x(\d+)/\S+\s+([0-9a-f]+)', line):
                current['regs'][int(index)] = int(value, 16)
            if floating:
                for index,value in re.findall(r'f(\d+)/\S+\s+([0-9a-f]+)',line):
                    current['fregs'][int(index)]=int(value,16)&0xffffffff
                status=re.match(r'^\s*mstatus\s+([0-9a-f]+)',line)
                if status: current['mstatus']=int(status[1],16)
                privileged=re.match(r'^\s*(mcause|mepc|mtvec)\s+([0-9a-f]+)',line)
                if privileged: current[privileged[1]]=int(privileged[2],16)
    if current is not None:
        records.append(current)
    start = next((i for i, r in enumerate(records) if r['pc'] == entry), None)
    if start is None:
        raise ValueError('QEMU did not reach ELF entry')
    records = records[start:]
    if any(len(r['regs']) != 32 for r in records):
        raise ValueError('Incomplete ISS register snapshot')
    if floating and any(len(r['fregs'])!=32 or 'mstatus' not in r for r in records):
        raise ValueError('Incomplete floating ISS snapshot')
    return records


def normalize(record):
    result = dict(record)
    if result['insn'] & 3 != 3:
        result['insn'] &= 0xffff
    if not result['rd_addr']:
        result['rd_wdata'] = 0
    # RVFI defines memory data only in enabled lanes, addresses only on access.
    for mode in ('r', 'w'):
        mask = sum(255 << (8*i) for i in range(4) if result[f'mem_{mode}mask'] & (1 << i))
        result[f'mem_{mode}data'] &= mask
    if not (result['mem_rmask'] or result['mem_wmask']):
        result['mem_addr'] = 0
    return result


def architectural_effect(insn, regs):
    """Independent RV32IMC destination and load/store decode (not RTL-derived).

    Return destination and optional (write, address, bytes, store value).
    Arithmetic results come from QEMU, not a duplicate ALU implementation.
    """
    def signed(value, width):
        return value - (1 << width) if value & (1 << (width-1)) else value
    rd, memory = 0, None
    if insn & 3 == 3:
        op, f3 = insn & 127, (insn >> 12) & 7
        if op in (0x37, 0x17, 0x6f, 0x67, 0x03, 0x13, 0x33) or (op == 0x73 and f3):
            rd = (insn >> 7) & 31
        elif op not in (0x23, 0x63, 0x0f):
            raise ValueError('Unsupported instruction in independent effect decoder')
        if op in (3, 0x23):
            write = op == 0x23
            immediate = ((insn >> 25) << 5 | ((insn >> 7) & 31)) if write else insn >> 20
            address = (regs[(insn >> 15) & 31] + signed(immediate, 12)) & 0xffffffff
            if f3 not in ((0, 1, 2) if write else (0, 1, 2, 4, 5)):
                raise ValueError('Unsupported memory width')
            memory = (write, address, 1 << (f3 & 3), regs[(insn >> 20) & 31])
    else:
        q, f3, r = insn & 3, insn >> 13, (insn >> 7) & 31
        if q == 0 and f3 == 0:
            rd = 8 + ((insn >> 2) & 7)
        elif q == 0 and f3 in (2, 6):
            rd = 8 + ((insn >> 2) & 7) if f3 == 2 else 0
            offset = ((insn >> 5) & 1) << 6 | ((insn >> 10) & 7) << 3 | ((insn >> 6) & 1) << 2
            memory = (f3 == 6, (regs[8 + ((insn >> 7) & 7)] + offset) & 0xffffffff,
                      4, regs[8 + ((insn >> 2) & 7)])
        elif q == 1:
            rd = r if f3 in (0, 2, 3) else 1 if f3 == 1 else 8 + ((insn >> 7) & 7) if f3 == 4 else 0
        elif q == 2 and f3 == 0:
            rd = r
        elif q == 2 and f3 in (2, 6):
            write = f3 == 6
            offset = (((insn >> 9) & 15) << 2 | ((insn >> 7) & 3) << 6) if write else (
                ((insn >> 12) & 1) << 5 | ((insn >> 4) & 7) << 2 | ((insn >> 2) & 3) << 6)
            rd = 0 if write else r
            memory = (write, (regs[2] + offset) & 0xffffffff, 4, regs[(insn >> 2) & 31])
        elif q == 2 and f3 == 4:
            rd = r if (insn >> 2) & 31 else (1 if insn & 0x1000 else 0)
        else:
            raise ValueError('Unsupported compressed instruction in effect decoder')
    return rd, memory


def completion_window(iss, binary, base=BASE, allow_compressed_store=False):
    """Delimit by the ISS's own finisher store; validate every shutdown-tail row.

    QEMU shutdown is asynchronous. Its trace can contain multiple iterations
    of the specified final `j .` after the store. Only that exact, inert tail
    is allowed, and its first state checks the store's architectural poststate.
    """
    for index, state in enumerate(iss):
        offset = state['pc'] - base
        if offset < 0 or offset + 4 > len(binary):
            continue
        insn = int.from_bytes(binary[offset:offset+4], 'little')
        size=4
        if insn & 0x707f == 0x2023:
            _,access=architectural_effect(insn,state['regs'])
        elif allow_compressed_store and insn&3==0 and (insn&0xffff)>>13==6:
            size=2
            _,access=architectural_effect(insn&0xffff,state['regs'])
        else: continue
        if not access or access[:3]!=(True,0x100000,4) or access[3]!=0x5555:
            continue
        tail = iss[index+1:]
        if not tail:
            raise ValueError('Missing ISS completion-store poststate')
        pc = state['pc'] + size
        offset = pc - base
        instruction = int.from_bytes(binary[offset:offset+4], 'little')
        if not (instruction == 0x0000006f or instruction & 0xffff == 0xa001):
            raise ValueError('Completion tail is not the required inert self-jump')
        if any(row['pc'] != pc or row['regs'] != state['regs'] for row in tail):
            raise ValueError('Unexpected instruction/state in ISS shutdown tail')
        if 'fregs' in state and any(row['fregs']!=state['fregs'] or
                (row['mstatus']&0x6000)!=(state['mstatus']&0x6000) for row in tail):
            raise ValueError('Unexpected floating state in ISS shutdown tail')
        return iss[:index+2]
    raise ValueError('ISS did not execute the completion store')


def compare(reference, candidate, iss, binary, base=BASE):
    iss = completion_window(iss, binary, base)
    if not reference or len(reference) != len(candidate) or len(reference) + 1 != len(iss):
        raise ValueError(f'Retirement count mismatch: reference={len(reference)} candidate={len(candidate)} ISS={len(iss)}')
    memory = {base + i: byte for i, byte in enumerate(binary)}
    for n, (gold, got, cpu) in enumerate(zip(reference, candidate, iss)):
        gold, got = normalize(gold), normalize(got)
        if gold != got:
            raise ValueError(f'RVFI mismatch at retirement {n}: ' + str({k: (gold[k], got[k]) for k in gold if gold[k] != got[k]}))
        # This pinned Ibex increments the reset-zero counter before reporting
        # its first retirement, so the first published order is one.
        if got['order'] != n + 1 or got['trap'] or got['halt'] or got['intr'] or got['mode'] != 3 or got['ixl'] != 1:
            raise ValueError(f'Unexpected retirement control at {n}')
        pc = cpu['pc']
        offset = pc - base
        if offset < 0 or offset + 2 > len(binary):
            raise ValueError('ISS left loaded program')
        size = 4 if memory[pc] & 3 == 3 else 2
        insn = sum(memory.get(pc+i,0) << (8*i) for i in range(size))
        if got['pc_rdata'] != pc or got['insn'] != insn:
            raise ValueError(f'ISS instruction/PC mismatch at {n}')
        destination, access = architectural_effect(insn, cpu['regs'])
        if got['rd_addr'] != destination:
            raise ValueError(f'ISS architectural destination mismatch at {n}')
        if access:
            write, address, width, value = access
            mask = (1 << width) - 1
            if got['mem_addr'] != address or got['mem_wmask' if write else 'mem_rmask'] != mask:
                raise ValueError(f'ISS memory address/mask mismatch at {n}')
            data_mask = (1 << (width * 8)) - 1
            if write:
                if got['mem_wdata'] & data_mask != value & data_mask:
                    raise ValueError(f'ISS store data mismatch at {n}')
                for lane in range(width):
                    memory[(address + lane) & 0xffffffff] = (value >> (8 * lane)) & 255
            else:
                value = sum(memory.get((address + lane) & 0xffffffff, 0) << (8 * lane) for lane in range(width))
                if got['mem_rdata'] & data_mask != value:
                    raise ValueError(f'ISS load data mismatch at {n}')
        if (not access or not access[0]) and got['mem_wmask']:
            raise ValueError(f'Unexpected store at {n}')
        for rs in ('rs1', 'rs2'):
            if got[rs + '_rdata'] != cpu['regs'][got[rs + '_addr']]:
                raise ValueError(f'ISS {rs} operand mismatch at {n}')
        if n + 1 < len(iss):
            if got['pc_wdata'] != iss[n+1]['pc']:
                raise ValueError(f'ISS next-PC mismatch at {n}')
            rd = got['rd_addr']
            if rd and got['rd_wdata'] != iss[n+1]['regs'][rd]:
                raise ValueError(f'ISS instruction result mismatch at {n}')
            after = dict(cpu['regs'])
            if rd:
                after[rd] = got['rd_wdata']
            if after != iss[n+1]['regs']:
                raise ValueError(f'ISS register state mismatch at {n}')
        if n == len(reference) - 1 and not (got['mem_addr'] == 0x100000 and got['mem_wmask'] == 15 and got['mem_wdata'] == 0x5555 and
                  insn & 0x7f == 0x23 and got['pc_wdata'] == pc + 4 and not got['rd_addr']):
            raise ValueError('Missing valid final completion store')
    return len(reference)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--self-check', action='store_true')
    parser.add_argument('--candidate')
    parser.add_argument('--isa',choices=['rv32imc','rv32imfc'],default='rv32imc')
    parser.add_argument('--suite',default='smoke')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    if args.self_check and args.suite != 'smoke':
        parser.error('--self-check applies to smoke; suites use the faulted-candidate gate')
    output = output_dir(args.output)
    (output / 'result.json').write_text('{"status":"blocked"}\n')
    run([sys.executable, 'tools/env/check.py'], output, 'environment')
    if args.isa=='rv32imfc':
        from float_suites import run_suites
        return run_suites(args.candidate,args.suite,output)
    if args.suite != 'smoke':
        from suites import run_suites
        return run_suites(args.candidate,args.suite,output)
    elf = build_program(output)
    sims = [compile_sim(output / 'reference', original=True),
            compile_sim(output / 'candidate', args.candidate)]
    traces = []
    for label, sim in zip(('reference', 'candidate'), sims):
        result = run([sim, output / 'program.bin'], output, label + '-run')
        traces.append([json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')])
    iss = qemu_trace(elf, output)
    (output / 'iss.json').write_text(json.dumps(iss))
    count = compare(*traces, iss, (output / 'program.bin').read_bytes())
    if args.self_check:
        failures = {}
        for name in ('result', 'shared-destination', 'shared-store', 'shared-load-address', 'missing-retirement', 'order'):
            gold, fault = copy.deepcopy(traces)
            index = next(i for i, r in enumerate(fault) if r['rd_addr'] and i > 32)
            if name == 'result':
                fault[index]['rd_wdata'] ^= 1
            elif name == 'shared-destination':
                for trace in (gold, fault):
                    trace[index]['rd_addr'] = trace[index]['rd_wdata'] = 0
            elif name == 'shared-store':
                index = next(i for i, r in enumerate(fault) if r['mem_wmask'])
                for trace in (gold, fault):
                    trace[index]['mem_wdata'] ^= 1
            elif name == 'shared-load-address':
                index = next(i for i, r in enumerate(fault) if r['insn'] & 127 == 3)
                for trace in (gold, fault):
                    trace[index]['mem_addr'] ^= 4
            elif name == 'missing-retirement':
                fault.pop(index)
            else:
                fault[index]['order'] += 1
            try:
                compare(gold, fault, iss, (output / 'program.bin').read_bytes())
            except ValueError as exc:
                failures[name] = str(exc)
            else:
                raise ValueError(f'{name} fault escaped checker')
        (output / 'negative-controls.json').write_text(json.dumps(failures, indent=2) + '\n')
    (output / 'result.json').write_text(json.dumps(dict(status='pass', retirements=count,
        comparisons=['unmodified reference', 'candidate', 'pinned QEMU'],
        negative_control=args.self_check, configuration=CONFIG), indent=2) + '\n')
    print(f'PASS lockstep: {count} retirements agree with reference and QEMU; fault rejected={args.self_check}', flush=True)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'FAIL lockstep: {exc}', file=sys.stderr)
        sys.exit(1)
