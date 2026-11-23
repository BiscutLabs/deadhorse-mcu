"""Rebind the unchanged USB-island certificate and screen its integrated paths.

This is an internal-register screen, not a pad/CDC boundary or CTS signoff.
"""
from pathlib import Path
import copy,csv,hashlib,json,subprocess,sys
ROOT=Path.cwd();sys.path.insert(0,str(ROOT))
from tools.timing.usb_qualification import audit_exceptions
base=ROOT/'build/t32/area07/mapped'
ref=ROOT/'build/plan03/fast02/fast/usb/timing/usb'
out=base/'usb-class-screen02';out.mkdir(exist_ok=False)
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
original=json.loads((ref/'certificate/result.json').read_text())
assert original['status']=='pass' and digest(ref/'mapped.json')==original['mapped_sha256']
for name,value in original['proof_source_sha256'].items():
    p=ROOT/name.removeprefix('/work/')
    assert digest(p)==value,('Changed USB proof source',name)
island=json.loads((base/'map-8/island-preservation.json').read_text())
assert island['status']=='pass'
mod=json.loads((base/'map-8/canonical.json').read_text())['modules']['DeadhorseSoc']
def rename(name):
    target='subsystem.usb.'+name
    if name.startswith('usb_enable_replica_'):target=name
    assert target in mod['cells'],target
    return target
for name,cell in json.loads((ref/'mapped.json').read_text())['modules']['Usb']['cells'].items():
    d=mod['cells'][rename(name)]
    assert cell['type']==d['type'] and cell['parameters']==d['parameters']
cert=copy.deepcopy(original)
cert['reset_aware']['groups']={g:[rename(n) for n in names] for g,names in original['reset_aware']['groups'].items()}
cert['pre_enable']['capture_pins']={rename(n):rename(n)+'/D' for n in original['pre_enable']['capture_pins']}
cert['top']='DeadhorseSoc'
group=cert['reset_aware']['groups'];allowed=cert['reset_aware']['allowed_pairs']
cc=set(n for names in group.values() for n in names)
pre=set(cert['pre_enable']['capture_pins'])
allregs={rename(n) for n,c in json.loads((ref/'mapped.json').read_text())['modules']['Usb']['cells'].items() if 'CLK' in c['connections'] and 'D' in c['connections']}
full=allregs-cc;prelaunch={n for g in cert['pre_enable']['allowed_launch_groups'] for n in group[g]}
constraints=[]
def exception(a,b,setup,hold):
    for mode,value in [('setup',setup),('hold',hold)]:
        constraints.append(f'set_multicycle_path {value} -{mode} -from [get_pins {{{" ".join(n+"/CLK" for n in sorted(a))}}}] -to [get_pins {{{" ".join(n+"/D" for n in sorted(b))}}}]')
for a,b in allowed:exception(group[a],group[b],4,3)
exception(prelaunch,pre,3,2)
prefix=(base/'sta-screen-8/timing.tcl').read_text().split('set f [open')[0]
queries=[]
for a,aa in group.items():
    for b,bb in group.items():queries.append(('CC' if [a,b] in allowed else 'CC_reset',aa,bb))
queries += [('CF',cc,full-pre),('FC',full,cc),('FF',full,full-pre),('CP',prelaunch,pre),('FP',allregs-prelaunch,pre)]
rows=[]
for label,a,b in queries:
    if a and b:rows.append('{'+label+' {'+' '.join(n+'/CLK' for n in sorted(a))+'} {'+' '.join(n+'/D' for n in sorted(b))+'}}')
tcl=out/'timing.tcl'
tcl.write_text(prefix+'\n'+'\n'.join(constraints)+f'''
write_sdc {out}/applied.sdc
set f [open {out}/paths.tsv w]
puts $f "class\\tmode\\tdelay_ns\\tstart\\tend\\tslack_ns"
foreach q {{ {' '.join(rows)} }} {{
 lassign $q class starts ends
 foreach domain {{main aon usb tck}} {{
  set allstarts [all_registers -clock $domain -clock_pins]
  set allends [all_registers -clock $domain -data_pins]
  set from {{}};set to {{}}
  foreach pin [get_pins $starts] {{if {{$pin in $allstarts}} {{lappend from $pin}}}}
  foreach pin [get_pins $ends] {{if {{$pin in $allends}} {{lappend to $pin}}}}
  if {{![llength $from] || ![llength $to]}} {{continue}}
 foreach mode {{max_rise max_fall min_rise min_fall}} {{
  foreach path [find_timing_paths -from $from -to $to -path_delay $mode -group_path_count [expr {{2*[llength $to]}}] -endpoint_path_count 1] {{
   set points [get_property $path points]
   set last [lindex $points end]
   puts $f "$domain.$class\\t$mode\\t[get_property $last arrival]\\t[get_full_name [get_property $path startpoint]]\\t[get_full_name [get_property $path endpoint]]\\t[get_property $path slack]"
  }}
 }}
 }}
}}
close $f
puts USB_CLASS_SCREEN_COMPLETE
''')
p=subprocess.run(['sta','-no_init','-exit',str(tcl)],text=True,capture_output=True)
(out/'sta.log').write_text(p.stdout+p.stderr)
assert p.returncode==0 and 'USB_CLASS_SCREEN_COMPLETE' in p.stdout and not any(s.startswith('Error') for s in p.stdout.splitlines())
counts=audit_exceptions((out/'applied.sdc').read_text(),cert)
with(out/'paths.tsv').open() as f:paths=list(csv.DictReader(f,delimiter='\t'))
summary={}
for kind in sorted({r['class'] for r in paths}):
    data=[dict(r,delay_ns=float(r['delay_ns']),slack_ns=float(r['slack_ns'])) for r in paths if r['class']==kind]
    worst=max((r for r in data if r['mode'].startswith('max')),key=lambda r:r['delay_ns'])
    domain,typ=kind.split('.')
    budget=.6*{'main':125,'aon':1000,'usb':1000/48,'tck':10000}[domain]*{'CC':4,'CP':3}.get(typ,1)
    classification='warning' if domain=='usb' and typ not in ('CC','CP') and budget<worst['delay_ns']<=15 else 'fail' if worst['delay_ns']>budget else 'pass'
    summary[kind]=dict(worst=worst,budget_ns=budget,minimum_slack_ns=min(r['slack_ns'] for r in data),
                       classification=classification,scope='Same-domain integrated unchanged USB island; USB single-cycle warning ceiling 15 ns per D59, mandatory post-placement recheck')
receipt=dict(status='measured_screen',classes=summary,exception_counts=counts,
    assumptions='Existing certificate rebound through exact preserved island identity and reset-tree audit. Raw ideal clocks; no pad or asynchronous boundary signoff.',
    source_certificate_sha256=digest(ref/'certificate/result.json'),mapped_sha256=digest(base/'map-8/canonical.json'))
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
