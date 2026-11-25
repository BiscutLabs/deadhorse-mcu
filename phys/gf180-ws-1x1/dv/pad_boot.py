"""Production pad path to real ROM UART recovery, existing analog-model fixture."""
import argparse,hashlib,json,pathlib,subprocess,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[3];HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'dv/soc/boot'))
from wire_protocol import request,replies
from pad_model import prepare
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--chip',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 chip=(ROOT/a.chip).resolve();out=(ROOT/a.output).resolve();emit=out/'emit'
 for q in (chip,emit,out):q.relative_to(ROOT/'build')
 out.mkdir(parents=True,exist_ok=False)
 prepared=json.loads((chip/'chip-receipt.json').read_text());assert prepared['simulation']
 for n,h in prepared['input_sha256'].items():assert sha(ROOT/n)==h
 for n,h in prepared['artifact_sha256'].items():assert sha(chip/n)==h
 pad=out/'pad_model.v';model_patch=prepare(pad)
 receipt=dict(status='running',commands=[],cases={},scope='Finite pin-only UART recovery boot/reset smoke; existing analog-model substitution, not analog or memory-macro signoff')
 receipt['pad_model_patch']=model_patch
 def run(cmd,label):
  start=time.monotonic()
  with (out/(label+'.log')).open('w') as log:r=subprocess.run(list(map(str,cmd)),cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=600)
  receipt['commands'].append(dict(command=list(map(str,cmd)),seconds=time.monotonic()-start,returncode=r.returncode))
  assert r.returncode==0,label
 rom_dir=ROOT/'build/t36/rom';rom_receipt=json.loads((rom_dir/'result.json').read_text())
 assert rom_receipt['status']=='built' and rom_receipt['negative_control'] is None
 for n,h in rom_receipt['source_sha256'].items():assert sha(pathlib.Path(n))==h,n
 for n,h in rom_receipt['artifact_sha256'].items():assert sha(rom_dir/n)==h,n
 tracked=subprocess.check_output(['git','ls-files','-c','-o','--exclude-standard','-z'],cwd=ROOT,text=True).split('\0')
 sources_before={n:sha(ROOT/n) for n in set(tracked) if n and (n.endswith('.scala') or n in ('build.sbt','tools/sbt.py','tools/env/lock.json'))}
 for directory in ('build/t20/map','build/t20/i1','build/t21/gpio','build/t21/timers','build/t21/aon_timer','build/t23/dma','build/t24/pinmux','build/t26/watchdog','build/t28/boot_control','build/t30/qspi','build/plan05/aon_spi','build/plan05/aon_gpio'):
  for q in (ROOT/directory).rglob('*.json'):sources_before[q.relative_to(ROOT).as_posix()]=sha(q)
 receipt['emission_source_sha256']=sources_before
 run([sys.executable,'tools/sbt.py',f'hw/Test/runMain deadhorse.top.EmitPadModel {emit.relative_to(ROOT).as_posix()}'],'emit')
 wrapper=out/'PadBootTest.sv';wrapper.write_text('''`timescale 1ns/1ps
module PadBootTest(input clk,reset_n,model_lfClock,model_porReference,
 input [11:0] model_supplyMv,inputs,
 input [39:0] external_data,external_enable,output [39:0] observed,
 output [39:0] drive,output [6:0] status);
 wire clock_pad=clk;wire reset_pad=reset_n;wire [11:0] inputs_pad=inputs;
 tri [39:0] pads;tri [1:0] analog;
 for(genvar i=0;i<40;i=i+1) begin assign pads[i]=external_enable[i]?external_data[i]:1'bz;end
 assign observed=pads;
 assign drive=dut.bidir_CORE2PAD_OE;
 assign status={dut.i_chip_core.status_coreSleeping,dut.i_chip_core.status_coreReady,
  dut.i_chip_core.status_fault,dut.i_chip_core.status_sourceStable,
  dut.i_chip_core.status_mainLevel,dut.i_chip_core.status_servicesReleased,dut.i_chip_core.status_aonReleased};
 chip_top dut(.clk_PAD(clock_pad),.rst_n_PAD(reset_pad),.input_PAD(inputs_pad),
  .bidir_PAD(pads),.analog_PAD(analog),.model_lfClock(model_lfClock),
  .model_porReference(model_porReference),.model_supplyMv(model_supplyMv));
 always @* begin
  assert(dut.input_CORE2PAD_PU==0 && dut.input_CORE2PAD_PD==0);
  assert(dut.bidir_CORE2PAD_PU==0 && dut.bidir_CORE2PAD_PD==0);
  assert((dut.bidir_CORE2PAD_IE & dut.bidir_CORE2PAD_OE)==0);
 end
 always @(negedge clk) if(!reset_n) begin
  #5; // Settle the foundry model's 1 ns reset-pad propagation first.
  assert(dut.bidir_CORE2PAD_OE==40'h1000000001);
  assert(dut.bidir_CORE2PAD[0] && !dut.bidir_CORE2PAD[36]);
 end
endmodule
''')
 sources=sorted(emit.glob('*.sv'))+sorted(emit.glob('*.v'));package=emit/'dm_pkg.sv';sources.remove(package);sources.insert(0,package)
 sources += [chip/'src/chip_top.sv',chip/'src/chip_core.sv',chip/'src/chip_pad_feedback.sv',pad,wrapper]
 sources += sorted((chip/'ip').glob('*/vh/*.v'))
 sources += [ROOT/'hw/vendor/ibex_ref/vendor/lowrisc_ip/ip/prim_generic/rtl/prim_generic_clock_gating.sv']
 control=out/'warnings.vlt';control.write_text('`verilator_config\n'+f'lint_off -rule CMPCONST -file "{emit}/dm_csrs.sv" -match "Comparison is constant due to limited range*"\n'+f'lint_off -rule SPECIFYIGN -file "{pad}"\n')
 with control.open('a') as f:
  for pin in ('DVDD','DVSS','VDD','VSS'):
   f.write(f'lint_off -rule PINMISSING -file "{chip}/src/chip_top.sv" -match "Instance has missing pin: \'{pin}\'"\n')
 inputs=[*sources,control,HERE/'pad_boot.cpp',HERE/'pad_model.py',pathlib.Path(__file__),ROOT/'dv/soc/boot/nor.hpp',ROOT/'dv/soc/boot/wire_protocol.py',chip/'chip-receipt.json',ROOT/'tools/env/lock.json',rom_dir/'rom.hex',rom_dir/'result.json']
 receipt['input_sha256']={str(q.relative_to(ROOT)):sha(q) for q in inputs}
 try:
  run(['verilator','--cc','--exe','--build','--assert','--timing','--timescale','1ns/1ps','-Dfunctional',
   '-DENABLE_INITIAL_MEM_','-DENABLE_INITIAL_REG_','-I'+str(chip/'src'),'-j','4','--top-module','PadBootTest',
   '-CFLAGS','-I'+str(ROOT/'dv/soc/boot'),'--Mdir',out/'obj',control,*sources,HERE/'pad_boot.cpp'],'compile')
  host=out/'request.bin';host.write_bytes(request(5,1))
  for selection,bypass in ((0,0),(1,1)):
   label=f'aon{selection}-bypass{bypass}';response=out/(label+'.reply')
   run([out/'obj/VPadBootTest',host,response,str(selection),str(bypass)],label)
   expected=[dict(op=5,seq=1,address=0,payload=b'\0\1'+(0x35304844).to_bytes(4,'little')+(0x117).to_bytes(4,'little'))]
   for epoch in (0,1):assert replies(pathlib.Path(str(response)+str(epoch)).read_bytes())==expected
   receipt['cases'][label]='two exact gateway-v1 replies: initial boot and cold reset'
  assert all(sha(ROOT/n)==h for n,h in receipt['input_sha256'].items())
  assert all(sha(ROOT/n)==h for n,h in sources_before.items())
  receipt['status']='pass'
 except Exception as e:
  receipt.update(status='failed',error=str(e));raise
 finally:
  receipt['artifact_sha256']={str(q.relative_to(out)):sha(q) for q in out.rglob('*') if q.is_file() and q.name!='result.json'}
  (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print('PASS four pad-level ROM boots and exact UART gateway replies; no CI')
if __name__=='__main__':main()
