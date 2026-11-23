"""Check the adopted DM with HartResetExtension disabled against pinned upstream.

The upstream dm_mem has two consecutive identical reset branches in one
always_ff. Regrouping their disjoint assignments makes the gold model readable
by Yosys without changing event/reset semantics. This is not CDC equivalence.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[4]


def main(output):
    out = (ROOT / output).resolve()
    out.relative_to(ROOT / 'build')
    out.mkdir(parents=True, exist_ok=False)
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    vendor = ROOT / 'hw/vendor/riscv_dbg'
    spec = importlib.util.spec_from_file_location('debug_vendor_prepare', vendor / 'prepare.py')
    prepare = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prepare)
    gate_root = prepare.prepare(out / 'applied')
    lock = json.loads((vendor / 'riscv_dbg.lock.json').read_text())
    names = [n for n in lock['rtl_files'] if 'dmi_' not in n and 'tc_clk' not in n]
    gold = [vendor / n for n in names]
    gate = [gate_root / n for n in names]
    original = next(p for p in gold if p.name == 'dm_mem.sv')
    source = original.read_text()
    before = """    if (!rst_ni) begin
      cmd_hartsel_q <= '0;
    end else begin
      cmd_hartsel_q <= cmd_hartsel_d;
    end
    if (!rst_ni) begin
      fwd_rom_q       <= 1'b0;"""
    after = """    if (!rst_ni) begin
      cmd_hartsel_q   <= '0;
      fwd_rom_q       <= 1'b0;"""
    before_else = """      word_enable32_q <= 1'b0;
    end else begin
      fwd_rom_q       <= fwd_rom_d;"""
    after_else = """      word_enable32_q <= 1'b0;
    end else begin
      cmd_hartsel_q   <= cmd_hartsel_d;
      fwd_rom_q       <= fwd_rom_d;"""
    assert source.count(before) == source.count(before_else) == 1
    normalized = out / 'dm_mem.sv'
    normalized.write_text(source.replace(before, after).replace(before_else, after_else))
    gold = [normalized if p == original else p for p in gold]
    commands = []
    for label, files in [('gold', gold), ('gate', gate)]:
        parameters = ' -GHartResetExtension=0' if label == 'gate' else ''
        commands += ['read_slang --top dm_top -GNrHarts=2 -GBusWidth=32 '
                     '-GDmBaseAddress=65536 -GMaxRegisterAccessWidth=32' + parameters + ' ' +
                     ' '.join(map(str, files)), 'hierarchy -top dm_top', 'proc', 'flatten',
                     'chformal -remove', 'memory_map', 'opt', 'async2sync']
        if label == 'gate':
            commands += ['delete -port dm_top/w:hart_reset_i dm_top/w:command_hart_o dm_top/w:command_busy_o']
        commands += ['rename dm_top ' + label, 'design -stash ' + label]
    commands += ['design -copy-from gold -as gold gold', 'design -copy-from gate -as gate gate',
                 'equiv_make gold gate equivalence', 'hierarchy -top equivalence', 'equiv_simple',
                 'equiv_induct -seq 4', 'equiv_status -assert']
    script = out / 'equiv.ys'
    script.write_text('\n'.join(commands) + '\n')
    command = ['yosys', '-Q', '-T', '-s', str(script)]
    start = time.monotonic()
    with (out / 'equiv.log').open('w') as log:
        try:
            code = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, timeout=120).returncode
        except subprocess.TimeoutExpired:
            code = 124
    receipt = dict(status='pass' if code == 0 else 'unresolved' if code == 124 else 'failed',
                   command=command, returncode=code, seconds=time.monotonic()-start,
                   commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                   qualification='Default-disabled extension versus pinned DM with disjoint reset assignments regrouped. '
                                 'Sampled async2sync equivalence; not enabled-extension or replaced-CDC proof.',
                   sha256={str(p.relative_to(ROOT)): sha(p) for p in set(gold + gate +
                       [original, script, Path(__file__), vendor/'prepare.py', vendor/'riscv_dbg.lock.json', ROOT/'tools/env/lock.json'])})
    (out / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(receipt['status'], flush=True)
    return 0 if code == 0 else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    raise SystemExit(main(parser.parse_args().output))
