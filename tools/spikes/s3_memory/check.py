"""S3 representative memory measurement; run in the pinned environment."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]


def inputs():
    paths = [ROOT/'docs/plan/tasks/S-spikes.md', ROOT/'tools/env/lock.json']
    for name in ('tools/spikes/s3_memory', 'dv/memory',
                 'sw/flight/memory-measurement', 'sw/flight/loop-measurement/src'):
        directory = ROOT/name
        paths.extend(p for p in directory.rglob('*') if p.is_file() and
                     '__pycache__' not in p.parts and p.suffix != '.pyc')
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(set(paths)) if p.exists()}


def accept_child(code, detail):
    """A successful process cannot conceal an unresolved or incomplete receipt."""
    status = detail.get('status')
    if status == 'review_required' and code in (0, 1):
        return 'review_required'
    if code != 0 or status != 'pass':
        raise RuntimeError(f'Child check failed: exit {code}, status {status!r}')
    return 'pass'


def validate_allocation(memory, firmware):
    profiles=firmware['profiles']
    if set(profiles) != {'size','speed','lite-size','lite-speed'}:
        raise ValueError('All size/speed firmware profiles are required')
    queue=max(p['flight']['queue_bytes'] for p in memory['flash']['profiles'])
    staging=max(p['flight']['staging_bytes'] for p in memory['flash']['profiles'])
    reviews=[]
    for name, profile in profiles.items():
        measurement=profile['measurement']
        lite=name.startswith('lite')
        if measurement['baseline_capacity_bytes'] != (3072 if lite else 16384):
            raise ValueError('Firmware baseline capacity changed')
        if not lite:
            symbols={s['name']:s['bytes'] for s in measurement['symbols'] if s['kind'] in 'bBdD'}
            if (symbols.get('log_buffers',0) < queue or symbols.get('log_staging',0) < staging
                    or measurement['candidate_state_and_buffers_bytes'] < queue+staging):
                raise ValueError('Firmware omits modeled logging-buffer allocation')
        total=sum(measurement[key] for key in ('hot_code_bytes',
            'hot_constants_conservative_bytes','candidate_state_and_buffers_bytes',
            'stack_reserved_single_trap_bytes'))
        if total != measurement['candidate_sram_working_set_bytes']:
            raise ValueError('SRAM working-set arithmetic mismatch')
        if total > (3072 if lite else 12288):
            reviews.append(name)
    if set(reviews) != set(firmware['review_required_profiles']):
        raise ValueError('Capacity review inventory disagrees with measured allocation')
    if reviews and firmware['status'] != 'review_required':
        raise ValueError('Over-threshold allocation cannot report pass')
    return dict(logging_queue_bytes=queue, logging_staging_bytes=staging,
                review_required_profiles=reviews)


def execute_command(name, args, output, rows):
    then = time.monotonic()
    log = output/(name+'.log')
    row = dict(name=name, command=args, status='running',
               log=log.relative_to(ROOT).as_posix())
    rows.append(row)
    try:
        with log.open('w') as stream:
            process = subprocess.run(args, cwd=ROOT, stdout=stream,
                                     stderr=subprocess.STDOUT, timeout=600)
        row.update(returncode=process.returncode,
                   status='completed' if process.returncode == 0 else 'failed')
    except subprocess.TimeoutExpired as error:
        row.update(status='timeout', timeout_seconds=error.timeout)
        raise
    except Exception as error:
        row.update(status='failed', error=str(error))
        raise
    finally:
        row['seconds']=time.monotonic()-then
    return row


def run(output):
    output = Path(output).resolve()
    output.relative_to(ROOT/'build')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Use a fresh output directory; preserve prior receipts')
    output.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    before = inputs()
    receipt = dict(status='running', task='S3', source_sha256=before, commands=[],
        commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        scope='Representative firmware and executable memory/flash models; not production SRAM or flight qualification',
        ci_tier='not run by this command',
        capacity_bytes=dict(performance=16384, lite=3072, hot_review_threshold=12288))
    def command(name, args, child=None):
        row = execute_command(name, args, output, receipt['commands'])
        code = row['returncode']
        if child is not None:
            path = child/'result.json'
            detail = json.loads(path.read_text())
            row.update(receipt=path.relative_to(ROOT).as_posix(),
                       sha256=hashlib.sha256(path.read_bytes()).hexdigest(), status=detail.get('status'))
            receipt[name] = detail
            return accept_child(code, detail)
        if code:
            raise RuntimeError(f'{name} failed; see {row["log"]}')
        return 'pass'
    try:
        command('runner-tests', [sys.executable, '-m', 'unittest', 'discover', '-s',
                'tools/spikes/s3_memory', '-p', 'test_*.py', '-v'])
        command('memory-tests', [sys.executable, '-m', 'unittest', 'discover', '-s',
                'dv/memory', '-p', 'test_*.py', '-v'])
        states=[]
        for name, script in (('memory', 'memory_models.py'), ('firmware', 'firmware.py')):
            child=output/name
            states.append(command(name, [sys.executable, 'tools/spikes/s3_memory/'+script,
                                        '--output', str(child)], child))
        receipt['allocation_contract']=validate_allocation(receipt['memory'],receipt['firmware'])
        if inputs() != before:
            raise RuntimeError('Measurement inputs changed during run')
        receipt['status'] = 'review_required' if 'review_required' in states else 'pass'
    except Exception as error:
        receipt.update(status='failed', error=str(error))
    finally:
        receipt['seconds']=time.monotonic()-start
        (output/'result.json').write_text(json.dumps(receipt, indent=2)+'\n')
    print(f'{receipt["status"].upper()} S3; {receipt["seconds"]:.3f}s; {output/"result.json"}')
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args=parser.parse_args()
    return 0 if run(ROOT/args.output)['status']=='pass' else 1


if __name__=='__main__':
    sys.exit(main())
