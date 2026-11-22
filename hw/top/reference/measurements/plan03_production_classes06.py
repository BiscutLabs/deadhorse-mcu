"""Classify integrated sample-clock paths from the fresh actual-pin certificate."""
import csv,hashlib,json,math,subprocess,sys
from pathlib import Path
root=Path.cwd();base=root/'build/plan03/production-measure06'
mhz=int(sys.argv[1]);out=base/f'classes-{mhz}';out.mkdir(exist_ok=False)
certificate=base/f'certificate09-{mhz}/proof/result.json'
composition=json.loads((base/f'certificate09-{mhz}/composition.json').read_text());assert composition['status']=='pass'
assert hashlib.sha256(certificate.read_bytes()).hexdigest()==composition['certificate_sha256']
assert hashlib.sha256((base/f'map-{mhz}/canonical.json').read_bytes()).hexdigest()==composition['mapped_sha256']
assert hashlib.sha256(Path(composition['context_receipt']).read_bytes()).hexdigest()==composition['context_sha256']
cert=json.loads(certificate.read_text());assert cert['status']=='pass'
m=json.loads((base/f'map-{mhz}/canonical.json').read_text())['modules']['DeadhorseSoc']
clock=m['ports']['i1_usbClock']['bits']
regs={n:c for n,c in m['cells'].items() if c['connections'].get('CLK')==clock and '/Q' not in n}
c=set(cert['certified']);p=set(cert['pre_enable']['capture_pins']);f=set(regs)-c-p
assert c<=set(regs) and p<=set(regs) and not c&p and c|p|f==set(regs)
rg=cert['reset_aware']['groups'];pairs={tuple(v) for v in cert['reset_aware']['allowed_pairs']}
assert set(n for ns in rg.values() for n in ns)==c
prelaunch={n for g in cert['pre_enable']['allowed_launch_groups'] for n in rg[g]}
def pins(names,pin):return '{'+' '.join(n+'/'+pin for n in sorted(names))+'}'
groups=[];constraints=[]
for a,an in rg.items():
    for b,bn in rg.items():
        if not an or not bn:continue
        kind='CC' if (a,b) in pairs else 'CC_reset'
        groups.append((kind,an,bn))
        if kind=='CC':
            constraints += [f'set_multicycle_path 4 -setup -from [get_pins {pins(an,"CLK")}] -to [get_pins {pins(bn,"D")}]',
                            f'set_multicycle_path 3 -hold -from [get_pins {pins(an,"CLK")}] -to [get_pins {pins(bn,"D")}]']
groups += [('CF',c,f),('FC',f|p,c),('FF',f|p,f),('CP',prelaunch,p),('FP',set(regs)-prelaunch,p)]
constraints += [f'set_multicycle_path 3 -setup -from [get_pins {pins(prelaunch,"CLK")}] -to [get_pins {pins(p,"D")}]',
                f'set_multicycle_path 2 -hold -from [get_pins {pins(prelaunch,"CLK")}] -to [get_pins {pins(p,"D")}]']
original=(base/f'sta-{mhz}/timing.tcl').read_text();prefix=original.split('set f [open')[0]
lines=[prefix,*constraints,f'set f [open {out}/paths.tsv w]',
 'puts $f "class\tpolarity\tdelay_ns\tstart\tend\tslack_ns"']
for kind,launch,capture in groups:
    if not launch or not capture:continue
    lines += [f'set from [get_pins {pins(launch,"Q")}]',f'set to [get_pins {pins(capture,"D")}]',
     'foreach mode {max_rise max_fall min_rise min_fall} {',
     ' foreach path [find_timing_paths -from $from -to $to -path_delay $mode -group_path_count [expr {2*[llength $to]}] -endpoint_path_count 1] {',
     '  set last [lindex [get_property $path points] end]',
     f'  puts $f "{kind}\t$mode\t[get_property $last arrival]\t[get_full_name [get_property $path startpoint]]\t[get_full_name [get_property $path endpoint]]\t[get_property $path slack]"',
     ' }','}']
lines += ['close $f',f'write_sdc {out}/applied.sdc','puts CLASS_SCREEN_COMPLETE']
script=out/'classes.tcl';script.write_text('\n'.join(lines)+'\n')
run=subprocess.run(['sta','-no_init','-exit',str(script)],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
(out/'sta.log').write_text(run.stdout)
assert run.returncode==0 and 'CLASS_SCREEN_COMPLETE' in run.stdout and not any(s.startswith('Error') for s in run.stdout.splitlines()),run.stdout[-2000:]
with (out/'paths.tsv').open() as stream:rows=list(csv.DictReader(stream,delimiter='\t'))
result={}
for kind in sorted({r['class'] for r in rows}):
    group=[dict(r,delay_ns=float(r['delay_ns']),slack_ns=float(r['slack_ns'])) for r in rows if r['class']==kind]
    assert all(math.isfinite(r['delay_ns']) and math.isfinite(r['slack_ns']) for r in group)
    worst=max((r for r in group if r['polarity'].startswith('max')),key=lambda r:r['delay_ns'])
    target={'CC':50,'CP':37.5}.get(kind,12.5)
    ceiling=target if kind in ('CC','CP','FP') else 15
    result[kind]=dict(worst=worst,target_ns=target,ceiling_ns=ceiling,
      status='fail' if worst['delay_ns']>ceiling else 'warning' if worst['delay_ns']>target else 'pass',
      worst_hold_slack_ns=min(r['slack_ns'] for r in group if r['polarity'].startswith('min')))
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(mhz,json.dumps(result),flush=True)
