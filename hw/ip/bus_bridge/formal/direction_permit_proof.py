"""Actual multiclock permit safety and AON round-robin/progress obligations."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[4]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    out = (ROOT / args.output).resolve()
    out.relative_to(ROOT / 'build')
    out.mkdir(parents=True, exist_ok=False)
    paths = ['hw/ip/bus_bridge/src/main/scala/deadhorse/bus_bridge/BusBridge.scala',
             'hw/ip/bus_bridge/src/main/scala/deadhorse/bus_bridge/DirectionArbiter.scala',
             'hw/lib/src/main/scala/deadhorse/lib/Cdc.scala',
             'hw/ip/bus_bridge/formal/DirectionPermitFormal.scala',
             'hw/ip/bus_bridge/formal/direction_permit_proof.py']
    started=time.monotonic()
    receipt = dict(status='running', runs=[], commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(), assumptions=['external resets asserted initially, then arbitrary'],
                   environment='four-phase requester models; arbitrary demand, completion and independent clocks',
                   progress='arbiter grant within four eligible AON edges; no repeated owner while the other request remains pending',
                   limitation='wall-time progress requires continuing clocks and completion of the current owner; no clock ratio assumed',
                   source_sha256={p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in paths})
    def run(command, label, timeout=150):
        started = time.monotonic()
        with (out / (label + '.log')).open('w') as stream:
            result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=timeout)
        record = dict(command=command, returncode=result.returncode, seconds=time.monotonic()-started, log=label+'.log')
        receipt['runs'].append(record)
        return result.returncode, record
    try:
        code, _ = run([sys.executable, 'tools/sbt.py', f'hw/runMain deadhorse.bus_bridge.EmitDirectionPermitFormal {out}/emit'], 'emit', 600)
        if code:
            raise RuntimeError('Emission failed')
        for kind in ('permit', 'arbiter'):
            for variant in ('cover', 'fault', 'correct'):
                name = kind + '_' + variant
                top = 'DirectionPermitFormal' if kind == 'permit' else 'DirectionArbiterFormal'
                sources = sorted((out / 'emit' / name).glob('*.sv'))
                cover = variant == 'cover'
                count = (3 if kind == 'permit' else 2) if cover else (3 if kind == 'permit' else 6)
                script = [f'read_slang --top {top} ' + ' '.join(p.name for p in sources),
                          f'prep -top {top} -flatten',
                          "fminit -seq an 0,'z -seq mn 0,'z" if kind == 'permit' else "fminit -seq reset_n 0,'z",
                          'clk2fflogic', 'chformal -lower',
                          f'select -assert-count {count} t:$' + ('cover' if cover else 'assert')]
                config = out / (name + '.sby')
                config.write_text('\n'.join(['[options]', 'mode ' + ('cover' if cover else 'prove'),
                                           'multiclock on', 'depth 64', 'timeout 120', '', '[engines]',
                                           'smtbmc z3' if cover else 'abc pdr', '', '[script]', *script, '', '[files]', *map(str, sources), '']))
                code, record = run(['sby', '-d', str(out/name), str(config)], name)
                status_file = out/name/'status'
                status = status_file.read_text().split()[0] if status_file.exists() else 'ERROR'
                record['status'] = status
                expected = 'FAIL' if variant == 'fault' else 'PASS'
                if status != expected or code != (2 if variant == 'fault' else 0):
                    raise RuntimeError(name + ': ' + status)
                if variant != 'correct' and not list((out/name).glob('engine_*/trace*.vcd')):
                    raise RuntimeError(name + ': witness missing')
                print('PASS direction ' + name + ': ' + status, flush=True)
        if receipt['source_sha256']!={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}:
            raise RuntimeError('Sources changed during permit proof')
        receipt['status'] = 'pass'
    except Exception as exc:
        receipt.update(status='unresolved' if 'TIMEOUT' in str(exc) or isinstance(exc, subprocess.TimeoutExpired) else 'failed', error=str(exc))
        print(str(exc), file=sys.stderr)
    finally:
        receipt['seconds']=time.monotonic()-started
        (out/'result.json').write_text(json.dumps(receipt, indent=2)+'\n')
    return 0 if receipt['status'] == 'pass' else 1


if __name__ == '__main__':
    sys.exit(main())
