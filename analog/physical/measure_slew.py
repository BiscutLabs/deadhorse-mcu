"""Measure30/70% clock edges in an existing complete diagnostic waveform."""
import argparse
import json
from pathlib import Path
from common import Evidence, ROOT

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--case', action='append', required=True)
p.add_argument('--output', required=True)
a = p.parse_args()
out = (ROOT / a.output).resolve()
out.relative_to(ROOT / 'build')
out.mkdir(parents=True, exist_ok=False)
evidence = Evidence(out, __file__)
results = []
for name in a.case:
    directory = (ROOT / name).resolve()
    directory.relative_to(ROOT / 'build')
    evidence.add_inputs([directory / 'wave.txt', directory / 'case.spice'])
    rows = [[float(v) for v in line.split()] for line in (directory / 'wave.txt').read_text().splitlines()[1:]]
    assert rows[-1][0] >= .00755 - 1e-10
    events = []
    for first, second in zip(rows, rows[1:]):
        assert second[0] > first[0]
        for label, threshold in [('low', .3 * 3.3), ('high', .7 * 3.3)]:
            up = first[1] < threshold <= second[1]
            down = first[1] > threshold >= second[1]
            if up or down:
                time = first[0] + (second[0] - first[0]) * (threshold - first[1]) / (second[1] - first[1])
                if .0061 <= time <= .0071:
                    events.append((time, label, up))
    events.sort()
    rise, fall = [], []
    for first, second in zip(events, events[1:]):
        if first[1:] == ('low', True) and second[1:] == ('high', True):
            rise.append((second[0] - first[0]) * 1e9)
        if first[1:] == ('high', False) and second[1:] == ('low', False):
            fall.append((second[0] - first[0]) * 1e9)
    assert rise and fall
    results.append(dict(case=name, rising_ns=rise, falling_ns=fall,
                        max_rising_ns=max(rise), max_falling_ns=max(fall)))
(out / 'result.json').write_text(json.dumps(results, indent=2) + '\n')
evidence.data['scope'] = 'Measured30/70% slew at diagnostic3.3V/20fF; no new load/PVT qualification'
evidence.finish('measured')
print([(r['case'], r['max_rising_ns'], r['max_falling_ns']) for r in results])
