"""T35 pin-set method, paired PDKs and D109's exact mixed SRAM inventory."""
import argparse,concurrent.futures,csv,hashlib,json,math,pathlib,re,shutil,subprocess,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.pdk import liberty
from tools.timing.pdk_rebind import equal_content
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
CORNERS=('ss_125C_3v00','ss_n40C_3v00','tt_025C_3v30','ff_125C_3v60','ff_n40C_3v60')


def main():
 p=argparse.ArgumentParser()
 for n in ('old','new','output'):p.add_argument('--'+n,required=True)
 a=p.parse_args();out=(ROOT/a.output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
 macro_path=ROOT/'hw/vendor/gf180_sram/gf180_sram.lock.json';lock=json.loads(macro_path.read_text())
 old_lock_path=ROOT/'build/riscay-mcu/physical/gf180/pdk-lock.json';old_lock=json.loads(old_lock_path.read_text())
 inputs={str(p.relative_to(ROOT)):sha(p) for p in (pathlib.Path(__file__),macro_path,old_lock_path,ROOT/'tools/pdk.py',ROOT/'tools/timing/pdk_rebind.py',ROOT/'phys/gf180-ws-1x1/pdk-lock.json')}
 def bind(path):inputs[str(path.relative_to(ROOT))]=sha(path)
 def constraints(text):return '\n'.join(line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith('#'))
 for path in (ROOT/'phys/gf180-ws-1x1/compare_pdk.py',ROOT/'tools/timing/usb_boundary.py'):bind(path)
 contexts={}
 for label,base in [('old',(ROOT/a.old).resolve()),('new',(ROOT/a.new).resolve())]:
  base.relative_to(ROOT/'build');mapping=base/'map';receipt=json.loads((mapping/'result.json').read_text());screen=base/'ss125/result.json'
  parent=json.loads(screen.read_text());assert receipt['status']=='mapped' and parent['status']=='measured_screen'
  for name,expected in parent['input_sha256'].items():
   path=ROOT/name
   if sha(path)!=expected and label=='old':path=ROOT/'build/t43/baseline/source'/name
   assert sha(path)==expected,('Stale parent screen input',name)
   bind(path)
  assert sha(mapping/'canonical.json')==receipt['mapped_sha256']==parent['mapped_sha256']
  assert sha(mapping/'mapped.v')==receipt['verilog_sha256']
  cells=json.loads((mapping/'canonical.json').read_text())['modules']['DeadhorseSoc']['cells']
  selected={n:c for n,c in cells.items() if c['type'] in {lock['macro'],lock['retained_macro']}}
  assert {t:sum(c['type']==t for c in selected.values()) for t in (lock['macro'],lock['retained_macro'])}=={lock['macro']:16,lock['retained_macro']:4}
  pins={d:[n+'/'+pin+(f'[{i}]' if len(bits)>1 else '') for n,c in selected.items() for pin,bits in c['connections'].items() if pin!='CLK' and c['port_directions'][pin]==d for i in range(len(bits))] for d in ('input','output')}
  assert len(pins['input'])==556 and len(pins['output'])==160
  for path in (mapping/'result.json',mapping/'canonical.json',mapping/'mapped.v',screen):bind(path)
  contexts[label]={}
  for mode in ('rc','external'):
   source=base/'ss125'/mode/'timing.tcl';assert sha(source)==parent['constraint_sha256'][mode+'/timing.tcl'];bind(source)
   applied=base/'ss125'/mode/'applied.sdc';assert sha(applied)==parent['constraint_sha256'][mode+'/applied.sdc'];bind(applied)
   text=source.read_text();marker='\nset threshold_metrics ';assert text.count(marker)==1
   prefix=text.split(marker)[0]+'\n';libs=re.findall(r'^read_liberty (.+)$',prefix,re.M);assert len(libs)==3
   contexts[label][mode]=(prefix,libs,pins,constraints(applied.read_text()))
 for corner in CORNERS:
  oldlib=ROOT/'build/riscay-mcu/.tools/physical/pdk'/('gf180mcu_fd_sc_mcu7t5v0__'+corner+'.lib')
  assert sha(oldlib)==old_lock['files'][oldlib.name];bind(oldlib);newlib=liberty(corner);bind(newlib)
  assert equal_content(oldlib.read_text(),newlib.read_text())>0
  for macro in (lock['macro'],lock['retained_macro']):
   relative=f'cells/{macro}/{macro}__{corner}.lib';view=ROOT/'build/vendor/gf180_sram'/relative
   assert sha(view)==lock['files'][relative];bind(view)
 def run(label,corner,mode):
  start=time.monotonic();dest=out/label/corner/mode;dest.mkdir(parents=True)
  code,libs,pins,expected_sdc=contexts[label][mode]
  core=liberty(corner) if label=='new' else ROOT/'build/riscay-mcu/.tools/physical/pdk'/('gf180mcu_fd_sc_mcu7t5v0__'+corner+'.lib')
  for original in libs:
   original_path=pathlib.Path(original)
   replacement=core if 'gf180mcu_fd_sc' in original else original_path.with_name(original_path.name.replace('ss_125C_3v00',corner))
   code=code.replace('read_liberty '+original,'read_liberty '+str(replacement))
  for d in ('input','output'):code+='set '+d+'s [get_pins {'+' '.join(pins[d])+'}]\n'
  code+='if {[llength $inputs] != 556 || [llength $outputs] != 160} {error "Missing SRAM pin"}\n'
  code+=f'write_sdc {dest}/applied.sdc\nset f [open {dest}/paths.tsv w]\nputs $f "direction\\tpolarity\\tstart\\tend\\tarrival_ns\\tslack_ns"\n'
  code+='''foreach dir {into outof} {
 foreach pol {max_rise max_fall min_rise min_fall} {
  if {$dir eq "into"} {set paths [find_timing_paths -to $inputs -path_delay $pol -group_path_count 1120 -endpoint_path_count 1]} else {set paths [find_timing_paths -from $outputs -path_delay $pol -group_path_count 1120 -endpoint_path_count 1]}
  if {[llength $paths] == 0} {error "No SRAM timing path"}
  foreach p $paths {puts $f "$dir\\t$pol\\t[get_full_name [get_property $p startpoint]]\\t[get_full_name [get_property $p endpoint]]\\t[get_property [lindex [get_property $p points] end] arrival]\\t[get_property $p slack]"}
 }
}
close $f
puts T43_MACRO_PATHS_COMPLETE
'''
  script=dest/'timing.tcl';script.write_text(code);command=['sta','-no_init','-exit',str(script)]
  process=subprocess.run(command,capture_output=True,text=True);log=process.stdout+process.stderr;(dest/'sta.log').write_text(log)
  assert process.returncode==0 and 'T43_MACRO_PATHS_COMPLETE' in log and not re.search(r'^Error',log,re.M)
  assert constraints((dest/'applied.sdc').read_text())==expected_sdc,'Original constraints changed'
  rows=list(csv.DictReader((dest/'paths.tsv').open(),delimiter='\t'))
  assert rows and all(math.isfinite(float(row[k])) for row in rows for k in ('arrival_ns','slack_ns'))
  summary={d+'_'+kind:min((row for row in rows if row['direction']==d and row['polarity'].startswith(kind)),key=lambda row:float(row['slack_ns'])) for d in ('into','outof') for kind in ('max','min')}
  return dict(label=label,corner=corner,mode=mode,command=command,seconds=time.monotonic()-start,worst_slack=summary,queried_input_pins=556,queried_output_pins=160,
              unreported_inputs=sorted(set(pins['input'])-{row['end'] for row in rows if row['direction']=='into'}),
              unreported_outputs=sorted(set(pins['output'])-{row['start'] for row in rows if row['direction']=='outof'}))
 jobs=[(label,corner,mode) for corner in CORNERS for mode in ('rc','external') for label in ('old','new')]
 start=time.monotonic()
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:runs=list(pool.map(lambda job:run(*job),jobs))
 for old,new in zip(runs[::2],runs[1::2]):
  assert old['corner']==new['corner'] and old['mode']==new['mode']
  for key,row in old['worst_slack'].items():
   assert float(row['slack_ns'])==float(new['worst_slack'][key]['slack_ns']), 'Changed SRAM slack; stop before repair'
  for direction in ('inputs','outputs'):assert old['unreported_'+direction]==new['unreported_'+direction],'Changed SRAM coverage'
 assert all(sha(ROOT/n)==h for n,h in inputs.items())
 result=dict(status='matched_macro_sta_no_regression',seconds=time.monotonic()-start,input_sha256=inputs,tool_sha256=sha(pathlib.Path(shutil.which('sta'))),runs=runs,
             scope='T35 complete pin-set queries, D109 mixed inventory, five unchanged paired corners and both AON straps. Ideal pre-CTS clocks; unreported pins retained, no physical signoff.')
 result['artifact_sha256']={p.relative_to(out).as_posix():sha(p) for p in out.rglob('*') if p.is_file()}
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS twenty SRAM pin-set screens; old/new worst setup and hold identical')

if __name__=='__main__':main()
