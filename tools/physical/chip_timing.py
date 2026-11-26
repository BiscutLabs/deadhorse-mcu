"""Measure launch-relative physical class delays using the certified query partition.

This is a diagnostic measurement, not CDC/RDC, analog or tape-out signoff.
"""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_timing(row):
    # Production mapped negative-edge flops use CLKN; SRAM and other state use
    # CLK. The independent mapped cell inventory and post-stage Liberty audit
    # preserve that polarity, rather than trusting the queried phase label.
    assert row['edge'] == ('fall' if row['query'].endswith('/CLKN') else 'rise'), row
    assert all(math.isfinite(row[k]) for k in ('delay_ns', 'slack_ns', 'launch_ns', 'arrival_ns'))
    assert row['delay_ns'] >= 0 and abs(row['delay_ns'] - (row['arrival_ns'] - row['launch_ns'])) < 0.00001, row


def validate_group_queries(summary, groups, observed, limit):
    wanted = {(g['id'], pol) for g in groups if g['launches'] and g['captures']
              for pol in ('max_rise', 'max_fall')}
    totals = {(int(r['group']), r['polarity']): int(r['paths']) for r in summary}
    assert len(totals) == len(summary) and set(totals) == wanted, 'Group query missing or duplicated'
    for (gid, polarity), total in totals.items():
        assert 0 <= total <= limit
        assert total == sum(int(r['paths']) for r in observed
                            if int(r['group']) == gid and r['polarity'] == polarity)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--audit', required=True)
    p.add_argument('--output', required=True)
    p.add_argument('--smoke', action='store_true', help='Two launches per group, RC strap only; no class acceptance')
    p.add_argument('--ranked-limit', type=int, default=0,
                   help='Diagnostic only: report this many worst-slack paths per group/polarity instead of per-launch enumeration')
    a = p.parse_args()
    assert a.ranked_limit >= 0 and not (a.smoke and a.ranked_limit)
    audit, out = [(ROOT / q).resolve() for q in (a.audit, a.output)]
    out.relative_to(ROOT / 'build')
    out.mkdir(parents=True, exist_ok=False)
    evidence = json.loads((audit / 'result.json').read_text())
    assert evidence['status'] == 'pass'
    inputs = [Path(__file__), audit / 'result.json']
    for name, digest in evidence['input_sha256'].items():
        path = ROOT / name
        assert sha(path) == digest, path
        inputs.append(path)
    for name, digest in evidence['artifact_sha256'].items():
        assert sha(audit / name) == digest, name
    parasitics = '''if {[grt::have_routes]} {
 estimate_parasitics -global_routing
 set provenance global-route-estimated-RC
} else {
 estimate_parasitics -placement
 set provenance placement-estimated-RC
}'''
    prior = ROOT / 'build/t43/new02/ss125'
    receipt = json.loads((prior / 'result.json').read_text())
    source_path = prior / 'rc/timing.tcl'
    assert sha(source_path) == receipt['constraint_sha256']['rc/timing.tcl']
    inputs += [prior / 'result.json', source_path]
    old = source_path.read_text()
    query = re.search(r'foreach q \{ (.*?) \} \{\n  lassign', old, re.S)[1]
    rows = re.findall(r'\{(CC_reset|CC|CF|FC|FF|CP|FP) \{([^{}]+)\} \{([^{}]+)\}\}', query)
    assert rows and not re.sub(r'\{(?:CC_reset|CC|CF|FC|FF|CP|FP) \{[^{}]+\} \{[^{}]+\}\}', '', query).strip()
    prefix = 'i_chip_core.soc.'
    def pin_list(pattern):
        match = re.search(pattern, old)
        assert match
        return ' '.join(prefix + q for q in match[1].split())
    usb_start = pin_list(r'set usb_start \[get_pins \{([^}]+)\}\]')
    usb_end = pin_list(r'set usb_end \[get_pins \{([^}]+)\}\]')
    gates = pin_list(r'foreach pin \[get_pins \{([^}]+)\}\] \{\n foreach check')
    resets = pin_list(r'set reset_capture \[get_pins \{([^}]+)\}\]')
    mapped = ROOT / 'build/t43/new02/map/canonical.json'
    assert sha(mapped) == receipt['mapped_sha256']
    inputs.append(mapped)
    cells = json.loads(mapped.read_text())['modules']['DeadhorseSoc']['cells']
    with (audit / 'rc/clocks.tsv').open() as f:
        clocks = {r['pin']: r['clock'] for r in csv.DictReader(f, delimiter='\t')}
    starts, ends = {}, {}
    macro_inputs, macro_outputs = [], []
    valid_starts = {}
    for pin, domain in clocks.items():
        name = pin.rsplit('/', 1)[0]
        cell = cells[name.removeprefix(prefix)]
        ports = cell['connections']
        def pins(direction, exclude=()):
            return [name + '/' + p + (f'[{i}]' if len(bits) > 1 else '')
                    for p, bits in ports.items() if p not in exclude and cell['port_directions'][p] == direction
                    for i in range(len(bits))]
        valid_starts[pin] = pins('output')
        starts.setdefault(domain, []).append(pin)
        if 'ip_sram__' in cell['type']:
            data = pins('input', ('CLK',))
            macro_inputs += data
            macro_outputs += pins('output')
        else:
            assert len(ports['D']) == 1
            data = [name + '/D']
        ends.setdefault(domain, []).extend(data)
    assert len(macro_inputs) == 556 and len(macro_outputs) == 160
    groups = []
    seen = set()
    for domain in ('main', 'aon', 'usb', 'tck'):
        source, target = set(starts[domain]), set(ends[domain])
        candidates = [('RR', source - set(usb_start.split()), target),
                      ('RR', source, target - set(usb_end.split()))]
        candidates += [(k, source & {prefix + p for p in aa.split()}, target & {prefix + p for p in bb.split()})
                       for k, aa, bb in rows]
        for kind, aa, bb in candidates:
            signature = (domain, kind, tuple(sorted(aa)), tuple(sorted(bb)))
            if signature in seen:
                continue
            seen.add(signature)
            launches = sorted(aa)
            if a.smoke and launches:
                # Include negative-edge state and real SRAM readout, when present.
                special = next((q for q in launches if q.endswith('/CLKN')), None)
                special = special or next((q for q in launches if 'ip_sram__' in cells[q.removeprefix(prefix).rsplit('/', 1)[0]]['type']), None)
                launches = sorted(set(launches[:2] + ([special] if special else [])))
            groups.append(dict(id=len(groups), domain=domain, kind=kind,
                               launches=launches, captures=sorted(bb)))
    (out / 'groups.json').write_text(json.dumps(groups, indent=2) + '\n')
    (out / 'sram-pins.json').write_text(json.dumps(dict(inputs=sorted(macro_inputs), outputs=sorted(macro_outputs)), indent=2))
    group_tcl = '\n'.join('rows $f ' + str(g['id']) + ' ' + g['domain'] + ' ' + g['kind'] +
        ' [chip_pins {' + ' '.join(g['launches']) + '}] [chip_pins {' + ' '.join(g['captures']) + '}]' for g in groups)
    ranked_tcl = ''
    if a.ranked_limit:
        sources = {source: clock for clock, ports in valid_starts.items() for source in ports}
        assert len(sources) == sum(map(len, valid_starts.values())), 'Ambiguous source clock pin'
        ranked_tcl = 'set source_clocks [dict create ' + ' '.join('{' + p + '} {' + c + '}' for p, c in sources.items()) + ']\n'
        ranked_tcl += f'''proc rows {{f group domain class from to}} {{
 global qf gf sampled source_clocks
 set launch_times [dict create]
 set falling [all_registers -fall_clock $domain -clock_pins]
 foreach pin $from {{
  set edge [expr {{$pin in $falling ? "fall" : "rise"}}]
  dict set launch_times [get_full_name $pin] [list $edge [get_property $pin arrival_max_$edge]]
 }}
 if {{![llength $from] || ![llength $to]}} {{return}}
 foreach polarity {{max_rise max_fall}} {{
  set counts [dict create]
  set new_samples [list]
  set total 0
  foreach path [find_timing_paths -from $from -to $to -path_delay $polarity -group_path_count {a.ranked_limit} -endpoint_path_count 1] {{
   set source [get_full_name [get_property $path startpoint]]
   set clock_pin [dict get $source_clocks $source]
   lassign [dict get $launch_times $clock_pin] edge launch
   set target [get_full_name [get_property $path endpoint]]
   set arrival [get_property [lindex [get_property $path points] end] arrival]
   puts $f "$group\\t$clock_pin\\t$domain\\t$class\\t$edge\\t$polarity\\t[expr {{$arrival-$launch}}]\\t$source\\t$target\\t[get_property $path slack]\\t$launch\\t$arrival"
   dict incr counts $clock_pin
   incr total
   set key "$domain/$edge"
   if {{![dict exists $sampled $key]}} {{
    dict set sampled $key 1
    lappend new_samples [list $key $clock_pin $target $launch]
   }}
  }}
  foreach sample $new_samples {{
   lassign $sample key clock_pin target launch
   puts "T38_SAMPLE_BEGIN $key $clock_pin $target $polarity cached_launch=$launch"
   report_checks -from [get_pins $clock_pin] -to [get_pins $target] -path_delay $polarity -group_path_count 1 -format full_clock_expanded -digits 6
   puts T38_SAMPLE_END
  }}
  dict for {{pin count}} $counts {{puts $qf "$group\\t$pin\\t$polarity\\t$count"}}
  puts $gf "$group\\t$polarity\\t$total"
 }}
 flush $f; flush $qf; flush $gf
}}
'''
    results = {}
    for mode in (('rc',) if a.smoke else ('rc', 'external')):
        dest = out / mode
        dest.mkdir()
        # The executed audit already loads the exact ODB, libraries and SDC.
        # The first report is the library-list output: retain the complete load
        # through read_current_sdc instead of copying any audit-output writes.
        full = (audit / mode / 'audit.tcl').read_text()
        end = full.index('read_current_sdc\n') + len('read_current_sdc\n')
        load = full[:end].replace(str(audit / mode / 'libraries.txt'), str(dest / 'libraries.txt'))
        script = dest / 'timing.tcl'
        script.write_text(load + f'''
set_global_vars
source $::env(SCRIPTS_DIR)/openroad/common/set_rc.tcl
{parasitics}
set f [open {{{dest}/paths.tsv}} w]
puts $f "group\tquery\tdomain\tclass\tedge\tpolarity\tdelay_ns\tstart\tend\tslack_ns\tlaunch_ns\tarrival_ns"
set qf [open {{{dest}/queries.tsv}} w]
puts $qf "group\tquery\tpolarity\tpaths"
set gf [open {{{dest}/group-queries.tsv}} w]
puts $gf "group\tpolarity\tpaths"
set sampled [dict create]
proc rows {{f group domain class from to}} {{
 global qf sampled
 set count 0
 set launch_times [dict create]
 set falling [all_registers -fall_clock $domain -clock_pins]
 # Resolve clock properties before obtaining path handles. Every launch is
 # enumerated separately, so clock insertion delay cannot mask data delay.
 foreach pin $from {{
  set edge [expr {{$pin in $falling ? "fall" : "rise"}}]
  dict set launch_times [get_full_name $pin] [get_property $pin arrival_max_$edge]
 }}
 if {{[llength $to]}} {{
 foreach pin $from {{
  set launch [dict get $launch_times [get_full_name $pin]]
  set edge [expr {{$pin in $falling ? "fall" : "rise"}}]
  foreach polarity {{max_rise max_fall}} {{
   set count 0
   set sample_end ""
   foreach path [find_timing_paths -from $pin -to $to -path_delay $polarity -group_path_count [expr {{2*[llength $to]}}] -endpoint_path_count 1] {{
    set arrival [get_property [lindex [get_property $path points] end] arrival]
    puts $f "$group\t[get_full_name $pin]\t$domain\t$class\t$edge\t$polarity\t[expr {{$arrival-$launch}}]\t[get_full_name [get_property $path startpoint]]\t[get_full_name [get_property $path endpoint]]\t[get_property $path slack]\t$launch\t$arrival"
    incr count
    if {{$sample_end eq ""}} {{set sample_end [get_full_name [get_property $path endpoint]]}}
   }}
   puts $qf "$group\t[get_full_name $pin]\t$polarity\t$count"
   set key "$domain/[expr {{$pin in $falling ? "fall" : "rise"}}]"
   if {{$sample_end ne "" && ![dict exists $sampled $key]}} {{
    dict set sampled $key 1
    puts "T38_SAMPLE_BEGIN $key [get_full_name $pin] $sample_end $polarity cached_launch=$launch"
    report_checks -from $pin -to [get_pins $sample_end] -path_delay $polarity -group_path_count 1 -format full_clock_expanded -digits 6
    puts T38_SAMPLE_END
   }}
  }}
 }}
 }}
 flush $f; flush $qf
}}
{ranked_tcl}
{group_tcl}
close $f; close $qf; close $gf
if {{{0 if a.smoke else 1}}} {{
set f [open {{{dest}/checks.tsv}} w]
puts $f "class\tpolarity\tstart\tend\tslack_ns"
foreach {{class targets}} [list gate [chip_pins {{{gates}}}] reset [chip_pins {{{resets}}}] hold [all_registers -data_pins] output [all_outputs]] {{
 foreach polarity {{max_rise max_fall min_rise min_fall}} {{
  foreach path [find_timing_paths -to $targets -path_delay $polarity -group_path_count [expr {{2*[llength $targets]}}] -endpoint_path_count 1] {{
   puts $f "$class\t$polarity\t[get_full_name [get_property $path startpoint]]\t[get_full_name [get_property $path endpoint]]\t[get_property $path slack]"
  }}
 }}
}}
close $f
check_setup -verbose
report_check_types -min_delay -recovery -removal -min_pulse_width -violators -digits 6
report_check_types -max_slew -max_capacitance -max_fanout -min_pulse_width -min_period -violators -digits 6
report_checks -path_delay max -group_path_count 10 -format full_clock_expanded -digits 6
report_checks -path_delay min -group_path_count 10 -format full_clock_expanded -digits 6
foreach from {{main aon usb tck}} {{
 foreach to {{main aon usb tck}} {{
  if {{$from ne $to}} {{
   puts "CROSS_DIAGNOSTIC $from->$to worst setup/hold only; not CDC qualification"
   report_checks -from [all_registers -clock $from -clock_pins] -to [all_registers -clock $to -data_pins] -path_delay min_max -group_path_count 1 -format full_clock_expanded -digits 6
  }}
 }}
}}
}}
report_parasitic_annotation -report_unannotated
puts "T38_TIMING_COMPLETE $provenance"
''')
        started = time.monotonic()
        command = ['openroad', '-exit', '-threads', '8', str(script)]
        with (dest / 'timing.log').open('w') as log:
            run = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        seconds = time.monotonic() - started
        (dest / 'process.json').write_text(json.dumps(dict(command=command, seconds=seconds,
            returncode=run.returncode, script_sha256=sha(script), collector_sha256=sha(Path(__file__))), indent=2) + '\n')
        log = (dest / 'timing.log').read_text()
        assert run.returncode == 0 and 'T38_TIMING_COMPLETE ' in log, log[-2000:]
        assert not any(s.startswith(('Error:', '[ERROR')) for s in log.splitlines())
        samples = []
        for header, body in re.findall(r'T38_SAMPLE_BEGIN ([^\n]+)\n(.*?)T38_SAMPLE_END', log, re.S):
            phase, clock_pin, capture, polarity, cached = header.split()
            cached = float(cached.removeprefix('cached_launch='))
            matched = re.findall(r'([-+0-9.]+)\s+[\^v]\s+' + re.escape(clock_pin) + r'\s+\(', body)
            assert matched and abs(float(matched[0]) - cached) <= 0.000002, (header, matched)
            # Independent report correlation must reject the other clock phase.
            period = dict(main=125, aon=31250, usb=1000 / 48, tck=10000)[phase.split('/')[0]]
            assert abs(float(matched[0]) - (cached + period / 2)) > 0.000002
            samples.append(dict(phase=phase, clock_pin=clock_pin, cached_ns=cached,
                                reported_ns=float(matched[0]), wrong_phase='rejected'))
        assert samples
        worst = {}
        controls = []
        expected_queries = {(g['id'], q, pol): set() for g in groups if g['captures']
                            for q in g['launches'] for pol in ('max_rise', 'max_fall')}
        if a.ranked_limit:
            expected_queries = {}
        with (dest / 'paths.tsv').open() as f:
            for row in csv.DictReader(f, delimiter='\t'):
                for name in ('delay_ns', 'slack_ns', 'launch_ns', 'arrival_ns'):
                    row[name] = float(row[name])
                    assert math.isfinite(row[name]), row
                gid = int(row['group'])
                key = (gid, row['query'], row['polarity'])
                group = groups[gid]
                if a.ranked_limit:
                    assert row['query'] in group['launches'] and row['polarity'] in ('max_rise', 'max_fall')
                    expected_queries.setdefault(key, set())
                assert key in expected_queries
                assert (row['domain'], row['class']) == (group['domain'], group['kind'])
                assert row['start'] in valid_starts[row['query']] and row['end'] in group['captures'], row
                assert row['end'] not in expected_queries[key], ('Duplicate capture', row)
                expected_queries[key].add(row['end'])
                validate_timing(row)
                if not controls and abs(row['launch_ns']) > 0.0001:
                    for label, fault in [('wrong-launch-edge', dict(row, edge='fall' if row['edge'] == 'rise' else 'rise')),
                                         ('double-clock-subtraction', dict(row, delay_ns=row['delay_ns'] - row['launch_ns']))]:
                        try:
                            validate_timing(fault)
                        except AssertionError:
                            controls.append(label)
                        else:
                            raise AssertionError('Timing arithmetic fault accepted')
                key = row['domain'] + '.' + row['class']
                if key not in worst or row['delay_ns'] > worst[key]['delay_ns']:
                    worst[key] = row
        assert worst and len(controls) == 2
        with (dest / 'queries.tsv').open() as f:
            observed = list(csv.DictReader(f, delimiter='\t'))
        observed_keys = [(int(r['group']), r['query'], r['polarity']) for r in observed]
        assert len(observed_keys) == len(expected_queries) and set(observed_keys) == set(expected_queries)
        if a.ranked_limit:
            with (dest / 'group-queries.tsv').open() as f:
                summary = list(csv.DictReader(f, delimiter='\t'))
            validate_group_queries(summary, groups, observed, a.ranked_limit)
            assert summary
            for label, fault in [('missing-group-query', summary[1:]),
                                 ('wrong-group-total', [dict(summary[0], paths=int(summary[0]['paths']) + 1), *summary[1:]])]:
                try:
                    validate_group_queries(fault, groups, observed, a.ranked_limit)
                except AssertionError:
                    controls.append(label)
                else:
                    raise AssertionError('Group accounting fault accepted')
        with (dest / ('ranked-observations.jsonl' if a.ranked_limit else 'coverage.jsonl')).open('w') as f:
            for row, key in zip(observed, observed_keys):
                targets = groups[key[0]]['captures']
                present = expected_queries[key]
                assert int(row['paths']) == len(present)
                mask = (1 << len(targets)) - 1
                for i, pin in enumerate(targets):
                    if pin in present:
                        mask ^= 1 << i
                f.write(json.dumps(dict(group=key[0], query=key[1], polarity=key[2], timed=len(present),
                                        **{('not_selected_bitmap_hex' if a.ranked_limit else 'no_timed_path_bitmap_hex'): hex(mask)})) + '\n')
        if not a.smoke:
            prior_classes = {k for k in receipt['modes'][mode]['classes'] if '->' not in k}
            assert prior_classes <= set(worst), ('Previously populated class disappeared', prior_classes - set(worst))
        classes = {}
        for key, row in worst.items():
            domain, kind = key.split('.')
            budget = 50 if kind == 'CC' else 37.5 if kind == 'CP' else dict(main=75, aon=18750, usb=12.5, tck=6000)[domain]
            ceiling = 15 if domain == 'usb' and kind in ('CC_reset', 'CF', 'FC', 'FF') else budget
            classes[key] = dict(worst=row, budget_ns=budget, failure_limit_ns=ceiling,
                                status='smoke_only' if a.smoke else 'observed_over_budget' if row['delay_ns'] > ceiling else 'observed_warning' if row['delay_ns'] > budget else 'no_observed_violation')
        results[mode] = dict(seconds=seconds, classes=classes, collector_controls=controls, expanded_samples=samples,
                            parasitics=log.split('T38_TIMING_COMPLETE ')[-1].strip())
    receipt = dict(status='collector_smoke' if a.smoke else 'measured_not_signoff', modes=results,
        selection=f'{a.ranked_limit} worst-slack paths per group/polarity; unselected paths unmeasured' if a.ranked_limit else 'per-launch enumeration',
        input_sha256={str(q.relative_to(ROOT)): sha(q) for q in inputs},
        artifact_sha256={str(q.relative_to(out)): sha(q) for q in out.rglob('*') if q.is_file()},
        scope='Observed fixed-clock-launch class data delays, not exhaustive launch-tag qualification or class acceptance. One reported timing path per capture/polarity is selected by slack; alternate launch-clock tags remain unqualified. The query inventory includes all556 SRAM input/control captures and20 SRAM clock launches;160 Q pins are enumerated, but per-Q readout coverage is not separately measured. Ranked mode leaves unselected paths unmeasured. No CDC/RDC waiver or analog qualification.')
    (out / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(results))


if __name__ == '__main__':
    main()
