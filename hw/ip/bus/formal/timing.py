"""T14 production-domain timing with unchanged T09 constraints; no CDC STA claim."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'dv/core'))
from common import output_dir, run

BLOCKS = {'fabric': 'BusFabric', 'source': 'BridgeSource', 'target': 'BridgeTarget', 'arbiter': 'DirectionArbiter',
          'mailbox0': 'MailboxEndpoint', 'mailbox1': 'MailboxEndpoint',
          **{f'{side}{width}': f'Cdc{side.title()}' for side in ('write', 'read') for width in (32, 33, 72)},
          'reset': 'ResetRelease', 'sync1': 'CdcSync', 'sync2': 'CdcSync'}


def snapshot():
    paths = [ROOT / 'build.sbt', ROOT / 'hw/ip/mailbox/mailbox.regmap.yaml', Path(__file__),
             ROOT / 'hw/ip/bus/formal/EmitBusTiming.scala']
    for directory in ('hw/lib/src/main/scala', 'hw/ip/bus/src/main/scala',
                      'hw/ip/bus_bridge/src/main/scala', 'hw/ip/mailbox/src/main/scala'):
        paths.extend(sorted((ROOT / directory).rglob('*.scala')))
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = output_dir(args.output)
    if (output / 'result.json').exists():
        raise ValueError('Use a fresh output directory; retain earlier receipts')
    started = time.monotonic()
    receipt = dict(status='running', source_sha256=snapshot(), blocks={},
                   commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                   scope='Measured single-clock production modules, mapped pre-layout, no wire delay; CDC skew and MTBF excluded')
    try:
        run([sys.executable, 'hw/regmap/regmap.py', 'hw/ip/mailbox/mailbox.regmap.yaml',
             '--out', output / 'regmap'], output, 'regmap')
        run([sys.executable, 'tools/sbt.py',
             f'hw/runMain deadhorse.bus.EmitBusTiming {output}/emit {output}/regmap/mailbox_regs.json'], output, 'emit')
        for name, top in BLOCKS.items():
            sources = sorted((output / 'emit' / name).glob('*.sv'))
            command = [sys.executable, 'tools/timing/check.py', '--top', top, '--clock', 'clk',
                       '--output', str(output / name)]
            for source in sources:
                command += ['--source', str(source)]
            result = run(command, output, name, allowed=(0, 1, 2))
            detail = json.loads((output / name / 'result.json').read_text())
            receipt['blocks'][name] = detail
            print(f'{name}: {detail["status"]}', flush=True)
            if result.returncode == 0 and detail['status'] != 'pass':
                raise ValueError(f'{name}: inconsistent timing receipt')
        # Sum measured modules, including their internal pointer synchronizers.
        # This is a component-sum estimate, not a mapped integrated top.
        counts = {'fabric': 2, 'source': 2, 'target': 2, 'mailbox0': 1, 'mailbox1': 1,
                  'write72': 2, 'read72': 2, 'write33': 2, 'read33': 2,
                  'write32': 2, 'read32': 2, 'reset': 24, 'sync1': 7, 'arbiter': 1}
        # Reset count: bridge 2*(2 local+2 transport+4 FIFO), mailbox 2 local+4 FIFO,
        # direction permit 2. Sync1 count: bridge 2*(ack+target demand), permit 3.
        receipt['component_sum'] = dict(kind='estimated from measured component areas', counts=counts,
            area_mm2=sum(receipt['blocks'][name]['area_um2'] * count for name, count in counts.items()) / 1e6,
            excluded='Reset combinational glue; integrated optimization; physical CDC constraints',
            configuration='Two identical 3-master/2-region fabrics, two one-way bridges, two-way mailbox; not the final SoC map')
        if snapshot() != receipt['source_sha256']:
            raise RuntimeError('Production inputs changed during measurement; rerun against stable sources')
        receipt['status'] = 'pass' if all(v['status'] == 'pass' for v in receipt['blocks'].values()) else 'failed'
    except Exception as exc:
        receipt['status'] = 'failed'; receipt['error'] = str(exc)
    finally:
        receipt['seconds'] = time.monotonic() - started
        (output / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(f'{receipt["status"].upper()} T14 domain timing; {receipt["seconds"]:.3f}s', flush=True)
    return 0 if receipt['status'] == 'pass' else 1


if __name__ == '__main__':
    sys.exit(main())
