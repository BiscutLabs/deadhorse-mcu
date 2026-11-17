"""T14 mailbox endpoint port-contract proof; compose separately with CDC FIFO."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'tools'))
from formal import prove_block


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', required=True)
    args = ap.parse_args()
    out = (ROOT / args.output).resolve()
    out.relative_to(ROOT / 'build')
    if (out / 'result.json').exists():
        raise ValueError('Retain evidence; use fresh output')
    out.mkdir(parents=True, exist_ok=True)
    sources = [Path(__file__), ROOT / 'tools/formal.py',
        ROOT / 'hw/regmap/regmap.py', ROOT / 'hw/regmap/keywords.py',
        ROOT / 'hw/ip/mailbox/formal/MailboxFormal.scala',
        ROOT / 'hw/ip/mailbox/src/main/scala/deadhorse/mailbox/Mailbox.scala',
        ROOT / 'hw/ip/mailbox/mailbox.regmap.yaml',
        ROOT / 'hw/lib/src/main/scala/deadhorse/lib/BusRegAdapter.scala',
        ROOT / 'hw/lib/src/main/scala/deadhorse/lib/RegBlock.scala',
        ROOT / 'hw/lib/src/main/scala/deadhorse/lib/LocalBus.scala',
        ROOT / 'hw/lib/src/main/scala/deadhorse/lib/RegBus.scala']
    def snapshot():
        return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    before = snapshot()
    started = time.monotonic()
    subprocess.run([sys.executable, 'hw/regmap/regmap.py',
        'hw/ip/mailbox/mailbox.regmap.yaml', '--out', str(out / 'regmap')], cwd=ROOT, check=True)
    endpoint_results = {}
    for owner in (0, 1):
        endpoint = prove_block(f'mailbox-endpoint-{owner}', 'MailboxFormal',
            'deadhorse.mailbox.EmitMailboxFormal', out / f'endpoint-{owner}', 9, 11,
            extra=(str(out / 'regmap/mailbox_regs.json'), str(owner)))
        endpoint.update(owner=owner,
            scope='Unbounded full-width single-clock MailboxEndpoint public-port contract',
            assumptions=['reset_n initially low, subsequently arbitrary',
                         'all bus and FIFO-side inputs subsequently arbitrary; no clock-progress or FIFO-status assumptions'])
        (out / f'endpoint-{owner}/result.json').write_text(json.dumps(endpoint, indent=2) + '\n')
        endpoint_results[str(owner)] = endpoint
        if endpoint['status'] != 'pass':
            break
    result = dict(status='pass' if len(endpoint_results) == 2 and all(
        r['status'] == 'pass' for r in endpoint_results.values()) else 'failed',
        endpoints=endpoint_results, source_sha256=before, commit=subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        scope='Unbounded full-width single-clock MailboxEndpoint port contract, owners=0,1; not a dual-clock top proof',
        assumptions=['reset_n initially low, subsequently arbitrary',
                     'all bus and FIFO-side inputs subsequently arbitrary; no clock-progress or FIFO-status assumptions'],
        composition=['CdcFifo(width=32, depth=2) separate ordering/data/reset/wake proof required',
                     'actual Mailbox dual-clock wiring is covered separately by integration simulation and review'],
        total_seconds=time.monotonic()-started)
    after = snapshot()
    if before != after:
        result.update(status='failed', error='Source changed during run',
                      changed_sources=[name for name in before if before[name] != after[name]])
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    return 0 if result['status'] == 'pass' else 1


if __name__ == '__main__':
    sys.exit(main())
