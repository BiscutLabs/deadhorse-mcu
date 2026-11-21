"""Prepare I0 test ROM and validated maps using only the pinned environment."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'hw/top/reference'))
import check_soc_map as mapping
from hw.regmap.regmap import load, emit


def prepare(output, receipt):
    model = mapping.validate(mapping.yaml.load((ROOT / 'hw/top/reference/soc.yaml').read_text(), Loader=mapping.UniqueLoader))
    mapping.check_contract(model, (ROOT / 'docs/spec/soc.md').read_text())
    mapping.emit(model, ROOT / 'build/t20/map')
    emit(load(ROOT / 'hw/ip/uart/uart.regmap.yaml'), output)
    regions = {r['name']: r for r in model['regions']}
    rom = regions['boot_rom']; ram = regions['performance_sram']
    linker = output / 'boot.ld'
    linker.write_text(f'''ENTRY(_start)
SECTIONS {{
 . = 0x{rom['base'] + 0x80:x};
 .text : {{ KEEP(*(.start)) *(.text*) *(.rodata*) }}
 .data : {{ *(.data*) }}
 .bss : {{ *(.bss*) *(COMMON) }}
 __stack_top = 0x{ram['base'] + ram['size']:x};
}}
''')
    elf = output / 'boot.elf'; binary = output / 'boot.bin'
    commands = [
        ['riscv64-unknown-elf-gcc', '-march=rv32imfc_zicsr', '-mabi=ilp32f', '-O2',
         '-ffreestanding', '-fno-builtin', '-nostdlib', '-msmall-data-limit=0', '-Wl,--no-relax',
         '-Wl,-T,' + str(linker), '-I' + str(ROOT / 'build/t20/map'), '-I' + str(output),
         str(ROOT / 'sw/boot/t20-i0/start.S'), str(ROOT / 'sw/boot/t20-i0/main.c'), '-o', str(elf)],
        ['riscv64-unknown-elf-objcopy', '-O', 'binary', str(elf), str(binary)],
    ]
    receipt['commands'] = commands
    for index, command in enumerate(commands):
        result = subprocess.run(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        (output / f'command-{index}.log').write_text(result.stdout)
        result.check_returncode()
    image = bytes(0x80) + binary.read_bytes()
    if len(image) > rom['size']: raise ValueError('Boot image exceeds ROM')
    image += bytes(rom['size'] - len(image))
    (output / 'boot.hex').write_text(''.join(f'{int.from_bytes(image[i:i+4], "little"):08x}\n' for i in range(0, len(image), 4)))
    receipt['rom_sha256'] = hashlib.sha256((output / 'boot.hex').read_bytes()).hexdigest()


def main():
    output = ROOT / 'build/t20/i0-firmware'
    output.mkdir(parents=True, exist_ok=True)
    receipt = dict(status='running')
    receipt_file = output / 'result.json'
    receipt_file.write_text(json.dumps(receipt)+'\n')
    sources = [ROOT / name for name in (
        'sw/boot/t20-i0/start.S', 'sw/boot/t20-i0/main.c', 'dv/soc/prepare_i0.py',
        'hw/top/reference/soc.yaml', 'hw/top/reference/check_soc_map.py', 'docs/spec/soc.md',
        'hw/ip/uart/uart.regmap.yaml', 'hw/regmap/regmap.py', 'tools/env/lock.json')]
    snapshot = lambda: {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    try:
        receipt.update(commit=subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT,text=True).strip(),
                       source_sha256=snapshot())
        prepare(output,receipt)
        if snapshot()!=receipt['source_sha256']: raise RuntimeError('Preparation sources changed')
        receipt['artifact_sha256'] = {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for directory in (output, ROOT/'build/t20/map') for p in sorted(directory.iterdir())
            if p.is_file() and p != receipt_file}
        receipt['status'] = 'prepared_not_executed'
        print('PASS prepared I0 ROM; firmware has not executed')
    except Exception as error:
        receipt.update(status='failed',error=str(error))
        raise
    finally:
        receipt_file.write_text(json.dumps(receipt,indent=2)+'\n')


if __name__ == '__main__': main()
