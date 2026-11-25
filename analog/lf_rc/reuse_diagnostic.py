"""One scoped schematic feasibility diagnostic, not a production macro."""
import argparse,hashlib,json,math,pathlib,re,shutil,subprocess,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--simulator',required=True);p.add_argument('--models',required=True);p.add_argument('--environment',default='build/t43/analog-env01');p.add_argument('--verify-only',action='store_true');p.add_argument('--variant',choices=('scan','tuned','startup'),default='scan');a=p.parse_args()
out=(ROOT/a.output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
source=ROOT/'build/riscay-mcu/analog/gf180-lf-osc'
revision='4671317186003740ceb61360ba08c59bbdf10136'
for name in ('design.py','characterize.py'):
 assert (source/name).read_bytes()==subprocess.check_output(['git','-C',str(ROOT/'build/riscay-mcu'),'show',revision+':analog/gf180-lf-osc/'+name])
sys.path.insert(0,str(source))
from design import Design,netlist
from characterize import check_window
lock=json.loads((ROOT/'phys/gf180-ws-1x1/pdk-lock.json').read_text())
archive=ROOT/'build/t43/pdk-candidate/common.tar.zst'
assert sha(archive)==lock['archives']['common.tar.zst']['sha256']
modelbase=(ROOT/a.models).resolve();models=modelbase/'gf180mcuD/libs.tech/ngspice'
model_receipt=json.loads((modelbase/'result.json').read_text())
assert model_receipt['archive_sha256']==sha(archive)
assert model_receipt['helper_sha256']==sha(ROOT/'analog/prepare_models.py')
assert model_receipt['lock_sha256']==sha(ROOT/'phys/gf180-ws-1x1/pdk-lock.json')
inputs={str(source/n):sha(source/n) for n in ('design.py','characterize.py')}
for q in models.iterdir():
 if q.is_file():
  assert sha(q)==model_receipt['files'][str(q.relative_to(modelbase))],q
  inputs[str(q)]=sha(q)
result=dict(status='running',scope='Nominal schematic tuning feasibility only; external POR stimulus retained; no autonomous startup, PVT, physical views or production acceptance',inputs=inputs,commands=[],cases=[])
environment=(ROOT/a.environment).resolve();environment.relative_to(ROOT/'build')
inputs.update({str(q):sha(q) for q in (modelbase/'result.json',ROOT/'analog/prepare_models.py',ROOT/'phys/gf180-ws-1x1/pdk-lock.json',archive,environment/'flake.lock',environment/'flake.nix',ROOT/'phys/gf180-ws-1x1/template.lock.json')})
executable=pathlib.Path(a.simulator).resolve()
deriver=subprocess.check_output(['nix-store','--query','--deriver',str(executable.parent.parent)],text=True).strip()
result['simulator_binding']=dict(executable=str(executable),sha256=sha(executable),deriver=deriver,deriver_sha256=sha(pathlib.Path(deriver)))
tool_lock=ROOT/'analog/tools.lock.json';tools=json.loads(tool_lock.read_text());inputs[str(tool_lock)]=sha(tool_lock)
assert sha(environment/'flake.lock')==tools['flake_lock_sha256']
assert sha(environment/'flake.nix')==json.loads((ROOT/tools['template_lock']).read_text())['files']['flake.nix']
assert result['simulator_binding']['sha256']==tools['ngspice']['executable_sha256']
assert deriver==tools['ngspice']['deriver']
assert result['simulator_binding']['deriver_sha256']==tools['ngspice']['deriver_sha256']
if a.variant=='startup':result['scope']='Nominal diagnostic with continuous weak bias-start branch and no external POR stimulus; no startup/PVT/physical qualification'
result['simulator_version']=subprocess.check_output([str(executable),'--version'],text=True)
if a.verify_only:
 result['status']='verified_inputs_only';result['script_sha256']=sha(pathlib.Path(__file__))
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print('PASS pinned source, models, simulator and derivation; no simulation run');sys.exit(0)
def run(folder,name):
 start=time.monotonic()
 try:
  with (folder/(name+'.log')).open('w') as log:r=subprocess.run([str(executable),'-b',name+'.spice'],cwd=folder,stdout=log,stderr=subprocess.STDOUT,timeout=120)
  result['commands'].append(dict(case=folder.name,command=[str(executable),'-b',name+'.spice'],seconds=time.monotonic()-start,exit=r.returncode))
  assert r.returncode==0,folder/name
 except subprocess.TimeoutExpired:
  result['commands'].append(dict(case=folder.name,status='timeout',seconds=time.monotonic()-start));raise
def stage(folder):
 folder.mkdir()
 for q in models.iterdir():
  if q.is_file():shutil.copyfile(q,folder/q.name)
header='.include "design.ngspice"\n.lib "sm141064.ngspice" typical\n.lib "sm141064.ngspice" res_typical\n.param sw_stat_global=0 sw_stat_mismatch=0\n.temp 25\n'
try:
 folder=out/'resistor';stage(folder)
 (folder/'dc.spice').write_text('Independent nominal 1k-poly model check\n'+header+'VTEST test 0 1\nXR test 0 0 ppolyf_u_1k r_width=1u r_length=95.436u\n.control\nset numdgt=12\nop\nprint i(vtest)\nquit\n.endc\n.end\n')
 run(folder,'dc')
 text=(folder/'dc.log').read_text();m=re.search(r'i\(vtest\)\s*=\s*([-+\deE.]+)',text);assert m,text
 observed=-float(m[1]);expected=1/((1000*(95.436e-6-2*3.85e-11)+2*85.45*1e-6)/(1e-6-2*.0148e-6))
 result['resistor_dc']=dict(expected_a=expected,observed_a=observed)
 assert abs(observed/expected-1)<1e-5,'Resistor model does not match independent DC equation'
 cases={'scan':((1,.28),(3,.28),(1,1.0)),'tuned':((1,.6),),'startup':((1,2.0),)}[a.variant]
 for resistance,cap_length in cases:
  folder=out/f'r{resistance}-c{cap_length}';stage(folder)
  circuit=netlist(Design(resistor_megohm=resistance,buffer_stack=2,stages=3,timing_gate_length_um=cap_length))
  circuit=circuit.replace('nmos_3p3','nfet_03v3').replace('pmos_3p3','pfet_03v3').replace('ppolyf_u_3k','ppolyf_u_1k')
  circuit=re.sub(r'r_length=([0-9.]+)u',lambda m:f'r_length={float(m[1])*3:g}u',circuit)
  if a.variant=='startup':
   startup='* Diagnostic only: continuous nominal 20 MOhm bias-start branch.\n'
   for k in range(20):
    hi='pbias' if k==0 else f'start{k}';lo='vss' if k==19 else f'start{k+1}'
    startup+=f'XSTART{k} {hi} {lo} vss ppolyf_u_1k r_width=1u r_length=970.4u\n'
   circuit=circuit.replace('.ends riscay_lf_osc_gf180',startup+'.ends riscay_lf_osc_gf180')
  (folder/'oscillator.spice').write_text(circuit)
  deck='RISCay topology nominal retargeting diagnostic\n'+header+'''.options reltol=1e-4 abstol=1e-15 vntol=1e-7 gmin=1e-15 method=gear maxord=2
.include "oscillator.spice"
VDD vdd 0 pwl(0 0 100u 3.3)
VRESET rst_n 0 pwl(0 0 5.1m 0 5.1001m 3.3)
XDUT vdd 0 rst_n clk riscay_lf_osc_gf180
CLOAD clk 0 20f
.control
set wr_singlescale
set wr_vecnames
set numdgt=12
set num_threads=1
save v(clk) i(vdd)
tran 100n 7.1m 0 100n
wrdata wave.txt v(clk) i(vdd)
quit
.endc
.end
'''
  if a.variant=='startup':deck=deck.replace('VRESET rst_n 0 pwl(0 0 5.1m 0 5.1001m 3.3)\n','').replace('XDUT vdd 0 rst_n clk','XDUT vdd 0 vdd clk')
  (folder/'case.spice').write_text(deck)
  run(folder,'case')
  rows=[[float(x) for x in line.split()] for line in (folder/'wave.txt').read_text().splitlines()[1:]]
  assert rows and all(all(math.isfinite(x) for x in r) for r in rows)
  assert all(b[0]>a[0] for a,b in zip(rows,rows[1:]))
  assert rows[0][0]<=1e-8 and rows[-1][0]>=.0071-1e-10,'Incomplete waveform'
  try:measurement=check_window(rows,.0061,.0071,3.3)
  except ValueError as exc:measurement=dict(status='rejected',reason=str(exc))
  result['cases'].append(dict(parameters=dict(resistor_megohm=resistance,timing_gate_length_um=cap_length,stages=3,buffer_stack=2),measurement=measurement))
 result['status']='diagnostic_completed_not_qualified'
except BaseException as exc:
 result['status']='failed';result['error']=type(exc).__name__+': '+str(exc);raise
finally:
 assert sha(executable)==result['simulator_binding']['sha256']
 result['script_sha256']=sha(pathlib.Path(__file__))
 result['artifacts']={str(q.relative_to(out)):sha(q) for q in out.rglob('*') if q.is_file()}
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items() if k in ('status','resistor_dc','cases')},indent=2))
