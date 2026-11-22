"""Audit a routed USB diagnostic and retain failures; never grants signoff.

Run in the pinned main environment. No CI, synthesis or RTL mutation. Existing
reports are read once; the additional STA query measures clock insertion and
reset chains. Historical v1 absolute-arrival reports remain intact.
"""
import argparse
import csv
import json
import math
from pathlib import Path
import re
import subprocess
from collections import Counter, defaultdict
from usb_prepare import ROOT, linux, sha
from usb_graph import equivalent, reset_chains

PVTS=('ss_125C_3v00','ss_n40C_3v00','ff_125C_3v60','ff_n40C_3v60','tt_025C_3v30')
RCS=('min','nom','max')

def rows(path):
    with path.open() as stream:return list(csv.DictReader(stream,delimiter='\t'))

def number(value):
    value=float(value)
    if not math.isfinite(value):raise ValueError('Nonfinite measurement')
    return value

def corrected(row,clocks,metric='absolute-arrival-v1'):
    result={k:v for k,v in row.items() if k!='points'}
    # v1 stored absolute arrival, including propagated network insertion.
    launch=0.0
    if '/' in row['start']:
        launch=number(clocks[row['start'].rsplit('/',1)[0]+'/CLK']['max_rise_ns'])
    relative=metric in ('launch-relative-data-v2','launch-relative-data-v3-fixed-launch-enumeration')
    if metric!='absolute-arrival-v1' and not relative:raise ValueError('Unknown path metric')
    result['absolute_arrival_ns']=number(row['delay_ns'])+(launch if relative else 0)
    result['launch_clock_ns']=launch
    result['delay_ns']=result['absolute_arrival_ns']-launch
    if result['delay_ns']<0:raise ValueError('Negative data delay')
    return result

def annotation(log,module):
    match=re.search(r'Found (\d+) unannotated drivers\.\n(.*?)Found (\d+) partially unannotated drivers\.',log,re.S)
    if not match or int(match[3]):raise ValueError('Incomplete parasitic annotation')
    pins=match[2].split()
    if len(pins)!=int(match[1]):raise ValueError('Annotation count mismatch')
    loads={b for c in module['cells'].values() for p,bs in c['connections'].items() if c['port_directions'][p]=='input' for b in bs}
    loads.update(b for p in module['ports'].values() if p['direction']=='output' for b in p['bits'])
    for pin in pins:
        if '/' not in pin:
            match=re.fullmatch(r'(.*)\[(\d+)\]',pin)
            name,index=(match[1],int(match[2])) if match else (pin,0)
            if module['ports'][name]['direction']!='input' or module['ports'][name]['bits'][index] in loads:
                raise ValueError('Unannotated connected port: '+pin)
            continue
        cell,p=pin.split('/');c=module['cells'][cell]
        if (p not in c['connections'] and cell.startswith('clkload') and
            ((p=='ZN' and re.fullmatch(r'gf180mcu_fd_sc_mcu7t5v0__(?:inv|clkinv)_\d+',c['type'])) or
             (p=='Z' and re.fullmatch(r'gf180mcu_fd_sc_mcu7t5v0__(?:buf|clkbuf)_\d+',c['type'])))):
            continue  # Omitted output pin of a physical dummy clock load.
        if c['port_directions'].get(p)!='output' or any(b in loads for b in c['connections'][p]):
            raise ValueError('Unannotated connected signal: '+pin)
    return dict(unannotated_sinkless_drivers=pins,partially_unannotated=0)

def require_complete(log,marker):
    if marker not in log or re.search(r'(?im)^Error:|\[ERROR|not a valid (?:start|end) point',log):
        raise ValueError('Incomplete tool result: '+marker)

def audit_hashes(bindings):
    for name,digest in bindings.items():
        if sha(ROOT/name)!=digest:raise ValueError('Stale artifact/source: '+name)

def class_coverage(paths,baseline):
    if {r['class'] for r in paths}!={k for k,v in baseline['classes'].items() if v is not None}:
        raise ValueError('Missing or unexpected populated path class')

def audit_queries(paths,expected,queries):
    """Every group/launch/polarity query is executed and its rows accounted."""
    ids=[str(i) for i in range(len(expected))]
    if not ids or [r['query_id'] for r in expected]!=ids or [r['query_id'] for r in queries]!=ids:
        raise ValueError('Missing, duplicate or reordered timing query')
    by_id=defaultdict(list)
    for row in paths:
        if row.get('query_id') not in ids:raise ValueError('Unknown timing query')
        by_id[row['query_id']].append(row)
    for want,got in zip(expected,queries):
        if any(want[k]!=got[k] for k in ('query_id','class','launch','polarity')):
            raise ValueError('Wrong class, launch or polarity')
        if want['polarity'] not in ('max_rise','max_fall'):raise ValueError('Wrong timing polarity')
        pins=want['capture_pins'].split(',');absent=got['no_timed_path_captures'].split(',') if got['no_timed_path_captures'] else []
        if (not pins or len(set(pins))!=len(pins) or len(set(absent))!=len(absent) or
                not set(absent)<=set(pins) or int(got['requested_captures'])!=len(pins)):
            raise ValueError('Malformed capture inventory')
        actual=by_id[want['query_id']]
        if int(got['returned_paths'])!=len(actual):raise ValueError('Missing or duplicated path row')
        for row in actual:
            if (row['class']!=want['class'] or row['start']!=want['launch'] or
                    row['polarity']!=want['polarity'] or row['end'] not in pins):
                raise ValueError('Path outside query partition')
        ends=Counter(row['end'] for row in actual)
        if set(ends)!=set(pins)-set(absent) or any(n>1 for pin,n in ends.items() if '/' in pin):
            raise ValueError('Omitted or duplicate register capture')
    pairs=Counter((r['class'],r['launch'],r['capture_pins']) for r in expected)
    if any(n!=2 for n in pairs.values()):raise ValueError('Incomplete transition pair')
    phases=defaultdict(set)
    for r in expected:phases[(r['class'],r['launch'],r['capture_pins'])].add(r['polarity'])
    if any(p!={'max_rise','max_fall'} for p in phases.values()):raise ValueError('Repeated transition polarity')
    return dict(status='pass',queries=len(expected),path_rows=len(paths),
        no_timed_path_pairs=sum(len(r['no_timed_path_captures'].split(',')) if r['no_timed_path_captures'] else 0 for r in queries),
        interpretation='Fixed register launch, both endpoint polarities; input launch arrivals retained without subtraction. No-path pairs are disconnected or excluded by unchanged constraints.')

def replacement_arguments(inputs):
    entry=inputs.get('replacements')
    if entry is None:return {}
    path=ROOT/entry['path'];path.resolve().relative_to(ROOT/'build')
    if sha(path)!=entry['sha256']:raise ValueError('Replacement manifest changed')
    audit_hashes(entry['libraries'])
    return dict(replacements=json.loads(path.read_text()),libraries=[ROOT/p for p in entry['libraries']])

def measure(out,snapshot,destination):
    destination.mkdir(parents=True,exist_ok=False)
    inputs=json.loads((out/'inputs.json').read_text())
    audit_hashes(inputs['source_sha256'])
    for filename in ('mapped.json','result.json'):
        expected=[h for n,h in inputs['input_sha256'].items() if n.endswith('/timing/usb/'+filename)]
        if len(expected)!=1 or sha(snapshot/'timing/usb'/filename)!=expected[0]:raise ValueError('Unbound selected baseline')
    extraction=json.loads((out/'extraction-inputs.json').read_text())
    for name,key in (('routed.odb','routed_db_sha256'),('routed.v','routed_netlist_sha256')):
        if sha(out/name)!=extraction[key]:raise ValueError('Changed extraction input')
    if sha(out/'physical-analyze.tcl')!=extraction['analysis_sha256']:raise ValueError('Changed timing analysis')
    metric=extraction.get('path_metric')
    if metric is None:
        # Legacy v1 is accepted only with its bound, known source-latency
        # expression. Modern reports explicitly declare their metric.
        text=(out/'physical-analyze.tcl').read_text()
        if 'set delay [expr {[get_property $last arrival] - [sta::time_sta_ui [$path source_clk_latency]]}]' not in text:
            raise ValueError('Unqualified legacy timing metric')
        metric='absolute-arrival-v1'
    # Physical flow files have evolved only for reporting. Check original
    # physical run against its frozen flow copy; never rewrite old provenance.
    for name,digest in inputs['input_sha256'].items():
        p=out/'flow'/Path(name).name if name.startswith('tools/physical/') else ROOT/name
        if sha(p)!=digest:raise ValueError('Changed physical input: '+name)
    require_complete((out/'run.log').read_text(encoding='utf-8-sig'),'USB_DETAIL_ROUTE_COMPLETE')
    before=json.loads((snapshot/'timing/usb/mapped.json').read_text())['modules']['Usb']
    after=json.loads((out/'routed.json').read_text())['modules']['Usb']
    graph=dict(connectivity=equivalent(before,after,**replacement_arguments(inputs)),rdc=reset_chains(before))
    # Unique, direct, rising launch clock is required for pin-arrival correction.
    clock_bits={tuple(before['ports'][p]['bits']) for p in ('appClock','usbClock','aonClock')}
    for cell in before['cells'].values():
        if 'CLK' in cell['connections'] and tuple(cell['connections']['CLK']) not in clock_bits:
            raise ValueError('Non-tree/gated launch requires path-specific clock analysis')
    baseline=json.loads((snapshot/'timing/usb/result.json').read_text())
    # Reuse the bound baseline class budgets, not a new set of limits.
    corners=[];worst={};all_safety=[];all_rdc=[]
    expected={p+'-'+r for p in PVTS for r in RCS}
    if {p.name for p in (out/'timing').iterdir() if p.is_dir()}!=expected:raise ValueError('Incomplete corner inventory')
    for name in sorted(expected):
        source=out/'timing'/name;target=destination/name;target.mkdir()
        log=(source/'run.log').read_text(encoding='utf-8-sig');require_complete(log,'USB_PHYSICAL_TIMING_COMPLETE')
        annotated=annotation(log,after)
        settings=(source/'run.tcl').read_text().split('source {')[0]
        # write_sdc uses -add_delay; loading two boundary sets would retain
        # the SS envelope at fast corners. Retain all exceptions, remove the
        # old boundary values, then load exactly the corner-specific contract.
        base='\n'.join(line for line in (out/'full.sdc').read_text().splitlines() if not line.startswith(('set_input_delay','set_output_delay','set_input_transition','set_load')))+'\n'
        (target/'base.sdc').write_text(base)
        script=settings+f'\nset full_sdc {{{linux(target/"base.sdc")}}}\nset boundary_sdc {{{linux(source/"boundary.sdc")}}}\nset diagnostic_dir {{{linux(target)}}}\n'
        script+='set reset_chains {'+' '.join('{'+r['first']+' '+r['second']+'}' for r in graph['rdc']['chains'])+'}\n'
        script+='source /work/tools/physical/usb_diagnostics.tcl\n'
        (target/'run.tcl').write_text(script)
        with (target/'run.log').open('w') as stream:
            subprocess.run(['sta','-no_init','-exit',str(target/'run.tcl')],stdout=stream,stderr=subprocess.STDOUT,check=True,timeout=120)
        require_complete((target/'run.log').read_text(),'USB_DIAGNOSTICS_COMPLETE')
        clocks={r['pin']:r for r in rows(target/'clocks.tsv')}
        raw_paths=rows(source/'paths.tsv')
        query_audit=(audit_queries(raw_paths,rows(source/'paths.tsv.expected.tsv'),rows(source/'paths.tsv.queries.tsv'))
                     if metric=='launch-relative-data-v3-fixed-launch-enumeration' else None)
        paths=[corrected(r,clocks,metric) for r in raw_paths]
        class_coverage(paths,baseline)
        for r in paths:
            r['corner']=name
            r['target_ns']=baseline['class_budgets_ns'][r['class']]
            r['limit_ns']=baseline['class_failure_limits_ns'][r['class']]
            r['status']='fail' if r['delay_ns']>r['limit_ns'] else 'warning' if r['delay_ns']>r['target_ns'] else 'pass'
            if r['class'] not in worst or r['delay_ns']>worst[r['class']]['delay_ns']:worst[r['class']]=r
        (target/'corrected-paths.json').write_text(json.dumps(paths,indent=2)+'\n')
        safety=[dict(r,slack_ns=number(r['slack_ns']),corner=name) for r in rows(source/'short_reset_checks.tsv')]
        rdc=[dict(r,slack_ns=number(r['slack_ns']),corner=name) for r in rows(target/'rdc.tsv')]
        all_safety+=safety;all_rdc+=rdc
        electrical=log.split('ELECTRICAL_BEGIN')[1].split('ELECTRICAL_END')[0]
        corners.append(dict(corner=name,annotation=annotated,query_audit=query_audit,setup_class_failures=sum(r['status']=='fail' for r in paths),
            negative_safety_rows=[r for r in safety if r['slack_ns']<0],electrical_report=electrical,
            output_violations=[r for r in rows(source/'output_checks.tsv') if number(r['slack_ns'])<0]))
        print('AUDITED '+name,flush=True)
    result=dict(status='failed-validation',ci='not run',commit=inputs['commit'],scope=inputs['scope'],graph=graph,
        worst_by_class=worst,corners=corners,
        internal_hold_reset_violations=[r for r in all_safety if r['slack_ns']<0 and '/' in r['start']],
        worst_safety={kind:min((r for r in all_safety if r['check'].startswith(kind)),key=lambda r:r['slack_ns']) for kind in ('hold/','reset/min','reset/max')},
        reset_chains={r['second']:{kind:min((x for x in all_rdc if x['kind']==kind and x['start'].split('/')[0]==r['first' if kind=='interstage' else 'second'] and x['check'].startswith(mode)),key=lambda x:x['slack_ns']) for kind,mode in (('interstage','max'),('downstream','max'))} for r in graph['rdc']['chains']},
        rdc=all_rdc,
        limitations=['No whole-chip floorplan, pads/board/upstream implementation qualification','No PDN, pad ring, foundry DRC/LVS or analog metastability characterization','LEF58_ENCLOSURE without CUTCLASS warnings retained','Asynchronous input phase not guaranteed; no new false paths or timing waivers'])
    # Always records a diagnostic; never returns a signoff PASS, even when no
    # measured violation remains. Model qualification is a separate obligation.
    (destination/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('RECORDED failed-validation; no signoff or CI claim')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for flag in ('physical','snapshot','output'):p.add_argument('--'+flag,type=Path,required=True)
    a=p.parse_args()
    for path in (a.physical,a.snapshot,a.output):path.resolve().relative_to(ROOT/'build')
    measure(a.physical.resolve(),a.snapshot.resolve(),a.output.resolve())
