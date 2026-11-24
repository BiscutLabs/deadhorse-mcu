"""PLAN04 generated-clock digital screen, both static AON strap modes.

No asynchronous crossing is waived. Same-domain classes are acceptance screens;
cross-domain, boundary and reset diagnostics are retained for separate CDC/RDC
qualification. Analog and SRAM socket arcs remain excluded, explicitly.
"""
import argparse
import csv
import hashlib
import json
import math
import re
import shutil
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from tools.timing.check import clock_gate_inputs,electrical_checks
from tools.timing.usb_qualification import audit_exceptions

def class_limit(domain,kind,budget):
    return 15 if domain=='usb' and kind in ('CC_reset','CF','FC','FF') else budget


def physical_diagnostics(log):
    if log.count('HOLD_RESET_BEGIN')!=1 or log.count('HOLD_RESET_END')!=1:
        raise ValueError('Missing/ambiguous physical timing diagnostic')
    section=log.split('HOLD_RESET_BEGIN',1)[1].split('HOLD_RESET_END',1)[0]
    violations=[line.strip() for line in section.splitlines() if '(VIOLATED)' in line]
    return dict(status='unqualified',reported_violation_count=len(violations),
        violations=violations,
        scope='Raw hold/recovery/removal/pulse checks; unbuffered pre-CTS clock loads, no IO delay contract. Not physical acceptance.')


def clock_manifest(mod):
    def net(name):
        bits=mod['netnames'][name]['bits']
        if len(bits)!=1:raise ValueError('Non-scalar clock anchor '+name)
        return bits[0]
    roots={mod['ports']['oscIn']['bits'][0]:'usb',
        mod['ports']['pins_inactive_jtagTck']['bits'][0]:'tck',
        net('clocks._divider_divided'):'main',net('digital.subsystem.usb.aonClock'):'aon'}
    drivers={}
    for name,c in mod['cells'].items():
        for pin,bs in c['connections'].items():
            if c['port_directions'][pin]=='output':
                for bit in bs:
                    if bit in drivers:raise ValueError('Multiple clock/data driver')
                    drivers[bit]=(name,c)
    def lineage(bit,seen=None):
        if bit in roots:return roots[bit]
        seen=set() if seen is None else seen
        if bit in seen or bit not in drivers:raise ValueError('Unknown/cyclic clock lineage')
        seen.add(bit);_,c=drivers[bit]
        if c['type']=='gf180mcu_fd_sc_mcu7t5v0__icgtp_1':parent=c['connections']['CLK']
        elif re.fullmatch(r'gf180mcu_fd_sc_mcu7t5v0__buf_[1248]',c['type']):parent=c['connections']['I']
        else:raise ValueError('Unapproved clock-producing logic '+c['type'])
        if len(parent)!=1:raise ValueError('Non-scalar clock parent')
        return lineage(parent[0],seen)
    main={'Dma','DmaEngine','MainTimers','Pwm','PwmBreak','PwmChannel','PwmDmaRequests',
        'Pinmux','PinmuxPad','Qspi','QspiEngine','QspiScheduler','SpiHost','I2cHost','Gpio',
        'GpioWake','SocLocalMemory','DebugMemory','DebugSba','Fpu','FloatExecution'}
    aon={'AonTimers','BootRelease','LiteCore','LiteBusAdapter','OscCtrl','OscSequencer',
        'OscClockReset','ResetBootstrap','ResetCauses','PowerReset','BrownoutSelect','WatchdogChannel','UartWake',
        'GpioWakeState','RecoveryLoader','LoaderControl','ClockedI2cTarget','SocRetainedMemory'}
    result={}
    for name,c in mod['cells'].items():
        clock_pins=[p for p in ('CLK','CLKN') if p in c['connections']]
        if not clock_pins or 'D' not in c['connections']:continue
        if len(clock_pins)!=1:raise ValueError('Ambiguous register clock')
        clock_pin=clock_pins[0]
        if len(c['connections'][clock_pin])!=1:raise ValueError('Wide register clock')
        domain=lineage(c['connections'][clock_pin][0])
        source=c.get('attributes',{}).get('src','').split(':')[0].split('/')[-1].removesuffix('.sv')
        intent='main' if source in main or source.startswith(('ibex_','Uart_','DivSqrt','MulAdd','RoundAny','RecFN')) or source=='Uart' else \
            'aon' if source in aon else 'usb' if source in ('OscDivider','OscStability') else \
            'main' if source=='OscMainGate' else 'tck' if source in ('DebugTransport','dmi_jtag','dmi_jtag_tap') else None
        if intent and domain!=intent:raise ValueError('Wrong functional clock domain '+name+': '+source)
        result[name+'/'+clock_pin]=domain
    if set(result.values())!={'main','aon','usb','tck'}:raise ValueError('Missing production domain')
    return result


def audit_clock_envelope(text,divider,strap,frozen,select):
    # OpenSTA's canonical SDC: allow precisely this one generated clock and
    # these two static operating-mode cases. Everything else is still audited
    # by the existing strict exception checker.
    generated=[];cases=[];remaining=[]
    for line in re.sub(r'\\\r?\n\s*',' ',text).splitlines():
        value=line.strip()
        if value.startswith('create_generated_clock '):generated.append(value)
        elif value.startswith('set_case_analysis '):cases.append(value)
        else:remaining.append(line)
    expected=f'create_generated_clock -name main -source [get_ports {{oscIn}}] -divide_by 6 [get_pins {{{divider}}}]'
    if generated!=[expected]:raise ValueError('Unexpected generated-clock envelope: '+str(generated))
    expected_cases={f'set_case_analysis 1 [get_pins {{{frozen}}}]',f'set_case_analysis {select} [get_pins {{{strap}}}]'}
    if len(cases)!=2 or set(cases)!=expected_cases:raise ValueError('Unexpected static-clock cases')
    return '\n'.join(remaining)


def main(base,reference,screen_name='screen'):
    base=(ROOT/base).resolve();base.relative_to(ROOT/'build')
    ref=(ROOT/reference).resolve();ref.relative_to(ROOT/'build')
    if not re.fullmatch(r'[a-zA-Z0-9_-]+',screen_name):raise ValueError('Invalid screen name')
    mapped=base/'map';out=base/screen_name;out.mkdir(exist_ok=False)
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    sta_executable=Path(shutil.which('sta'))
    sta_sha256=digest(sta_executable)
    mapping=json.loads((mapped/'result.json').read_text())
    assert mapping['status']=='mapped' and digest(mapped/'canonical.json')==mapping['mapped_sha256']
    assert digest(mapped/'mapped.v')==mapping['verilog_sha256'],'Timed Verilog differs from mapped receipt'
    consumed=[mapped/p for p in ('result.json','canonical.json','mapped.v','analog-sockets.json','island-preservation.json')]
    consumed += [Path(__file__),ROOT/'tools/timing/check.py',ROOT/'tools/timing/usb_qualification.py',
        ref/'certificate/result.json',ref/'mapped.json',ROOT/'phys/gf180-ws-1x1/block-timing.json']
    def seal():return {p.relative_to(ROOT).as_posix():digest(p) for p in consumed}
    mod=json.loads((mapped/'canonical.json').read_text())['modules']['DeadhorseSoc']
    cfg=json.loads((ROOT/'phys/gf180-ws-1x1/block-timing.json').read_text())
    lib=ROOT/f'build/riscay-mcu/.tools/physical/pdk/{cfg["library"]}__{cfg["corner"]}.lib'
    assert digest(lib)==cfg['sha256']
    consumed.append(lib)
    input_hashes=seal()
    def flop_driver(net):
        bits=mod['netnames'][net]['bits'];assert len(bits)==1
        found=[name+'/Q' for name,c in mod['cells'].items() if c['connections'].get('Q')==bits and 'CLK' in c['connections']]
        assert len(found)==1,(net,found)
        return found[0]
    divider=flop_driver('clocks._divider_divided')
    strap=flop_driver('clocks.bootstrap.clockStrap')
    frozen=flop_driver('clocks.bootstrap.frozen')
    expected_clocks=clock_manifest(mod)
    (out/'expected-clocks.json').write_text(json.dumps(expected_clocks,indent=2)+'\n')
    analog=json.loads((mapped/'analog-sockets.json').read_text())
    rc=next(i['ports']['clock'] for i in analog if i['module']=='LfRcMacro')
    threshold=mapping.get('threshold_socket')
    threshold_tcl=''
    if threshold:
        threshold_tcl=f'''set tf [open $threshold_metrics w]
puts $tf "polarity\\tdelay_ns\\tstart\\tend\\tarrival_ns\\tlaunch_edge_ns"
foreach polarity {{max_rise max_fall min_rise min_fall}} {{
 set paths [find_timing_paths -unconstrained -from [get_pins {{{threshold['register']}/CLK}}] -to [get_ports {{{threshold['port']}[0]}}] -path_delay $polarity -group_path_count 1]
 if {{[llength $paths]!=1}} {{error "Missing live threshold endpoint $polarity"}}
 set path [lindex $paths 0]
 set points [get_property $path points]
 # Audited positive-edge AON dffrnq, phase zero, ideal clock/no source latency.
 # Subtract the explicit launch edge, never the first data point (possibly Q),
 # so the reported delay includes clock-to-Q even for this direct output.
 set arrival [get_property [lindex $points end] arrival]
 set launch 0.0
 set delay [expr {{$arrival-$launch}}]
 puts $tf "$polarity\\t$delay\\t[get_full_name [get_property $path startpoint]]\\t[get_full_name [get_property $path endpoint]]\\t$arrival\\t$launch"
}}
close $tf
'''
    gates,static_gates=clock_gate_inputs(mod)
    reset_pins=sorted(name+'/'+pin for name,c in mod['cells'].items()
        for pin in ('RN','SETN') if pin in c['connections'])
    assert reset_pins,'Missing production asynchronous reset endpoints'
    original=json.loads((ref/'certificate/result.json').read_text())
    assert original['status']=='pass' and digest(ref/'mapped.json')==original['mapped_sha256']
    for name,value in original['proof_source_sha256'].items():assert digest(ROOT/name.removeprefix('/work/'))==value,name
    island=json.loads((mapped/'island-preservation.json').read_text())
    assert island['status']=='pass' and island['reference_sha256']==digest(ref/'mapped.json')
    assert island['certificate_sha256']==digest(ref/'certificate/result.json')
    def rename(name):
        candidate=mapping['replica_renames'].get('digital.subsystem.usb.'+name,'digital.subsystem.usb.'+name)
        assert candidate in mod['cells'];return candidate
    cert=json.loads(json.dumps(original))
    cert['top']='DeadhorseSoc'
    cert['reset_aware']['groups']={g:[rename(n) for n in ns] for g,ns in original['reset_aware']['groups'].items()}
    cert['pre_enable']['capture_pins']={rename(n):rename(n)+'/D' for n in original['pre_enable']['capture_pins']}
    groups=cert['reset_aware']['groups'];allowed=cert['reset_aware']['allowed_pairs']
    cc={n for ns in groups.values() for n in ns};pre=set(cert['pre_enable']['capture_pins'])
    allusb={rename(n) for n,c in json.loads((ref/'mapped.json').read_text())['modules']['Usb']['cells'].items()
        if 'CLK' in c['connections'] and 'D' in c['connections']}
    full=allusb-cc;prelaunch={n for g in cert['pre_enable']['allowed_launch_groups'] for n in groups[g]}
    constraints=[]
    def pins(ns,suffix):return ' '.join(n+'/'+suffix for n in sorted(ns))
    def exception(a,b,setup,hold):
        for kind,value in [('setup',setup),('hold',hold)]:
            constraints.append(f'set_multicycle_path {value} -{kind} -from [get_pins {{{pins(a,"CLK")}}}] -to [get_pins {{{pins(b,"D")}}}]')
    for a,b in allowed:exception(groups[a],groups[b],4,3)
    exception(prelaunch,pre,3,2)
    queries=[]
    for a,aa in groups.items():
        for b,bb in groups.items():queries.append(('CC' if [a,b] in allowed else 'CC_reset',aa,bb))
    queries += [('CF',cc,full-pre),('FC',full,cc),('FF',full,full-pre),('CP',prelaunch,pre),('FP',allusb-prelaunch,pre)]
    query_text=' '.join('{'+kind+' {'+pins(a,'CLK')+'} {'+pins(b,'D')+'}}' for kind,a,b in queries if a and b)
    summary={}
    for mode,select in [('rc',0),('external',1)]:
        dest=out/mode;dest.mkdir()
        tcl=dest/'timing.tcl'
        tcl.write_text(f'''read_liberty {lib}
read_verilog {mapped}/mapped.v
link_design DeadhorseSoc
set_units -time ns -capacitance pF
set_case_analysis 1 [get_pins {{{frozen}}}]
set_case_analysis {select} [get_pins {{{strap}}}]
create_clock -name usb -period [expr {{1000.0/48}}] [get_ports oscIn]
create_generated_clock -name main -source [get_ports oscIn] -divide_by 6 [get_pins {{{divider}}}]
create_clock -name aon -period 31250 [get_ports {rc if select==0 else 'aonClockIn'}]
create_clock -name tck -period 10000 [get_ports pins_inactive_jtagTck]
set inputs [get_ports -filter "direction == input" *]
foreach n {{oscIn aonClockIn {rc} pins_inactive_jtagTck}} {{set inputs [lsearch -all -inline -not -exact $inputs [get_ports $n]]}}
set_input_transition {cfg['input_transition_ns']} $inputs
set_load {cfg['output_load_pf']} [get_ports -filter "direction == output" *]
{'\n'.join(constraints)}
set threshold_metrics {{{dest}/threshold.tsv}}
{threshold_tcl}
write_sdc {dest}/applied.sdc
set inventory [open {dest}/clocks.tsv w]
puts $inventory "pin\tclock"
foreach pin [all_registers -clock_pins] {{
 set clocks [get_property $pin clocks]
 if {{[llength $clocks]!=1}} {{error "Unclocked/ambiguous register [get_full_name $pin]"}}
 puts $inventory "[get_full_name $pin]\t[get_full_name [lindex $clocks 0]]"
}}
close $inventory
set f [open {dest}/paths.tsv w]
puts $f "domain\tclass\tpolarity\tdelay_ns\tstart\tend\tslack_ns\tlaunch_edge_ns\tarrival_ns\trequired_ns"
set qf [open {dest}/queries.tsv w]
puts $qf "domain\tclass\tstarts\tends\tpaths"
proc rows {{f domain class from to}} {{
 global qf
 set count 0
 if {{![llength $from] || ![llength $to]}} {{puts $qf "$domain\t$class\t[llength $from]\t[llength $to]\t0";return}}
 set source [lindex [split $domain ->] 0]
 foreach edge {{rise fall}} {{
 set candidates [all_registers -${{edge}}_clock $source -clock_pins]
 set starts {{}};foreach pin $from {{if {{$pin in $candidates}} {{lappend starts $pin}}}}
 if {{![llength $starts]}} {{continue}}
 set launch [expr {{$edge eq "rise" ? 0.0 : [get_property [get_clocks $source] period]/2.0}}]
 foreach polarity {{max_rise max_fall min_rise min_fall}} {{
  foreach path [find_timing_paths -from $starts -to $to -path_delay $polarity -group_path_count [expr {{2*[llength $to]}}] -endpoint_path_count 1] {{
   set last [lindex [get_property $path points] end]
   set arrival [get_property $last arrival]
   incr count
   set slack [get_property $path slack]
   set required [expr {{[string match max* $polarity] ? $arrival+$slack : $arrival-$slack}}]
   puts $f "$domain\t$class\t$polarity\t[expr {{$arrival-$launch}}]\t[get_full_name [get_property $path startpoint]]\t[get_full_name [get_property $path endpoint]]\t$slack\t$launch\t$arrival\t$required"
  }}
 }}
 }}
 puts $qf "$domain\t$class\t[llength $from]\t[llength $to]\t$count"
}}
set usb_start [get_pins {{{pins(allusb,'CLK')}}}]
set usb_end [get_pins {{{pins(allusb,'D')}}}]
foreach domain {{main aon usb tck}} {{
 set from [all_registers -clock $domain -clock_pins]
 set to [all_registers -clock $domain -data_pins]
 if {{![llength $from] || ![llength $to]}} {{error "Empty clock domain $domain"}}
 # All paths with either end outside the certified island retain one cycle.
 set outside_from {{}};set outside_to {{}}
 foreach p $from {{if {{$p ni $usb_start}} {{lappend outside_from $p}}}}
 foreach p $to {{if {{$p ni $usb_end}} {{lappend outside_to $p}}}}
 rows $f $domain RR $outside_from $to
 rows $f $domain RR $from $outside_to
 foreach q {{ {query_text} }} {{
  lassign $q class starts ends
  set a {{}};set b {{}}
  foreach p [get_pins $starts] {{if {{$p in $from}} {{lappend a $p}}}}
  foreach p [get_pins $ends] {{if {{$p in $to}} {{lappend b $p}}}}
  rows $f $domain $class $a $b
 }}
 foreach other {{main aon usb tck}} {{
  if {{$other ne $domain}} {{rows $f "$domain->$other" CROSS $from [all_registers -clock $other -data_pins]}}
 }}
}}
close $f
close $qf
set g [open {dest}/gates.tsv w]
puts $g "pin\tcheck\tslack_ns"
foreach pin [get_pins {{{' '.join(gates)}}}] {{
 foreach check {{max_rise max_fall min_rise min_fall}} {{
  set paths [find_timing_paths -to $pin -path_delay $check -group_path_count 1]
  if {{[llength $paths]!=1}} {{error "Missing dynamic gate path [get_full_name $pin] $check"}}
  puts $g "[get_full_name $pin]\t$check\t[get_property [lindex $paths 0] slack]"
 }}
}}
close $g
set rf [open {dest}/reset-endpoints.tsv w]
puts $rf "polarity\tstart\tend\tslack_ns"
set reset_capture [get_pins {{{' '.join(reset_pins)}}}]
foreach polarity {{max_rise max_fall min_rise min_fall}} {{
 foreach path [find_timing_paths -to $reset_capture -path_delay $polarity -group_path_count [expr {{2*[llength $reset_capture]}}] -endpoint_path_count 1] {{
  puts $rf "$polarity\t[get_full_name [get_property $path startpoint]]\t[get_full_name [get_property $path endpoint]]\t[get_property $path slack]"
 }}
}}
close $rf
puts ELECTRICAL_BEGIN
report_check_types -max_slew -max_capacitance -violators -digits 6
puts ELECTRICAL_END
puts HOLD_RESET_BEGIN
report_check_types -min_delay -recovery -removal -min_pulse_width -violators -digits 6
puts HOLD_RESET_END
puts PULSE_PERIOD_BEGIN
report_check_types -min_pulse_width -min_period -verbose -digits 6
puts PULSE_PERIOD_END
report_checks -path_delay min -group_path_count 10 -format full_clock_expanded -digits 6
report_checks -path_delay max -group_path_count 10 -format full_clock_expanded -digits 6
check_setup -verbose
puts PLAN04_SCREEN_COMPLETE
''')
        run=subprocess.run(['sta','-no_init','-exit',str(tcl)],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (dest/'sta.log').write_text(run.stdout)
        assert run.returncode==0 and 'PLAN04_SCREEN_COMPLETE' in run.stdout and not any(l.startswith('Error') for l in run.stdout.splitlines()),run.stdout[-2000:]
        audit=audit_exceptions(audit_clock_envelope((dest/'applied.sdc').read_text(),divider,strap,frozen,select),cert)
        with (dest/'clocks.tsv').open() as stream:clock_rows=list(csv.DictReader(stream,delimiter='\t'))
        actual_clocks={r['pin']:r['clock'] for r in clock_rows}
        assert len(actual_clocks)==len(clock_rows) and actual_clocks==expected_clocks,'STA clock assignment differs from audited mapped lineage'
        with (dest/'paths.tsv').open() as stream:raw=list(csv.DictReader(stream,delimiter='\t'))
        rows=[dict(r,delay_ns=float(r['delay_ns']),slack_ns=float(r['slack_ns'])) for r in raw]
        assert rows and all(math.isfinite(r['delay_ns']) and math.isfinite(r['slack_ns']) for r in rows)
        classes={}
        for domain,kind in sorted({(r['domain'],r['class']) for r in rows}):
            group=[r for r in rows if r['domain']==domain and r['class']==kind]
            worst=max((r for r in group if r['polarity'].startswith('max')),key=lambda r:r['delay_ns'])
            budget=None if kind=='CROSS' else .6*dict(main=125,aon=31250,usb=1000/48,tck=10000)[domain]*dict(CC=4,CP=3).get(kind,1)
            # USB warning decisions never extend to new oscillator logic.
            ceiling=class_limit(domain,kind,budget)
            status='diagnostic' if budget is None else 'fail' if worst['delay_ns']>ceiling else 'warning' if worst['delay_ns']>budget else 'pass'
            classes[domain+'.'+kind]=dict(worst=worst,budget_ns=budget,failure_limit_ns=ceiling,status=status,
                min_slack_ns=min(r['slack_ns'] for r in group if r['polarity'].startswith('min')))
        with (dest/'gates.tsv').open() as stream:gate_rows=list(csv.DictReader(stream,delimiter='\t'))
        with (dest/'queries.tsv').open() as stream:query_rows=list(csv.DictReader(stream,delimiter='\t'))
        with (dest/'reset-endpoints.tsv').open() as stream:reset_rows=list(csv.DictReader(stream,delimiter='\t'))
        assert reset_rows and all(r['end'] in reset_pins and math.isfinite(float(r['slack_ns'])) for r in reset_rows)
        reset_report=dict(status='measured_unqualified',requested_endpoints=len(reset_pins),
            reported_endpoints=len({r['end'] for r in reset_rows}),
            missing_endpoints=sorted(set(reset_pins)-{r['end'] for r in reset_rows}),
            minimum_slack_ns=min(float(r['slack_ns']) for r in reset_rows),
            negative_rows=sum(float(r['slack_ns'])<0 for r in reset_rows),
            scope='Endpoint recovery/removal diagnostics at the actual generated/domain clocks. Raw asynchronous boundary phase and pre-CTS trees remain unqualified; absent paths are listed, never passed.')
        assert run.stdout.count('PULSE_PERIOD_BEGIN')==1 and run.stdout.count('PULSE_PERIOD_END')==1
        assert len(gate_rows)==4*len(gates) and {(r['pin'],r['check']) for r in gate_rows}=={(p,c) for p in gates for c in ('max_rise','max_fall','min_rise','min_fall')}
        assert all(math.isfinite(float(r['slack_ns'])) for r in gate_rows)
        threshold_report=None
        if threshold:
            with (dest/'threshold.tsv').open() as stream:threshold_rows=list(csv.DictReader(stream,delimiter='\t'))
            assert len(threshold_rows)==4 and {r['polarity'] for r in threshold_rows}=={'max_rise','max_fall','min_rise','min_fall'}
            assert all(math.isfinite(float(r['delay_ns'])) and float(r['delay_ns'])>0 and
                float(r['launch_edge_ns'])==0 and float(r['delay_ns'])==float(r['arrival_ns']) for r in threshold_rows)
            threshold_report=dict(status='measured_digital_endpoint',paths=threshold_rows,
                assumed_load_pf=cfg['output_load_pf'],load_basis='Existing block-timing output-load assumption; replace with characterized T34 macro pin capacitance',
                scope='Clock-to-output cell delay, ideal pre-CTS clock, no wires; analog setup/hold and switching unqualified')
        summary[mode]=dict(classes=classes,electrical=electrical_checks(run.stdout),gate_checks=gate_rows,
            threshold_endpoint=threshold_report,
            gate_violations=[r for r in gate_rows if float(r['slack_ns'])<0],clock_pin_count=len(actual_clocks),
            queries=query_rows,physical_diagnostics=physical_diagnostics(run.stdout),reset_endpoints=reset_report,
            gate_static_inputs=static_gates,exception_counts=audit,
            boundary='Unconstrained IO/reset diagnostics retained in sta.log; macro, CDC/RDC and physical timing unqualified')
        (dest/'result.json').write_text(json.dumps(summary[mode],indent=2)+'\n')
        print(mode,json.dumps({k:(v['status'],v['worst']['delay_ns']) for k,v in classes.items() if v['budget_ns'] is not None}),flush=True)
    assert seal()==input_hashes,'Screen inputs changed during run'
    assert digest(sta_executable)==sta_sha256,'OpenSTA changed during screen'
    (out/'result.json').write_text(json.dumps(dict(status='measured_screen',modes=summary,input_sha256=input_hashes,
        tools_sha256={'sta':sta_sha256},
        constraint_sha256={p.relative_to(out).as_posix():digest(p) for p in out.rglob('*') if p.name in ('timing.tcl','applied.sdc')},
        mapped_sha256=digest(mapped/'canonical.json'),generated_clock_pin=divider,
        strap_modes='D84 frozen strap state; startup/reset transitions excluded from static modes and separately proved',
        assumptions='Nominal 48MHz/32kHz/100kHz TCK, ideal pre-CTS clocks, no wires; generated phase is not a CDC waiver'),indent=2)+'\n')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',required=True);parser.add_argument('--usb-reference',required=True)
    parser.add_argument('--screen-name',default='screen')
    args=parser.parse_args();main(args.base,args.usb_reference,args.screen_name)
