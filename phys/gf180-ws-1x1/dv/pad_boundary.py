"""D110 exhaustive Boolean proof plus actual foundry four-state pad simulation."""
import argparse,hashlib,json,pathlib,subprocess,time
from pad_model import prepare
ROOT=pathlib.Path(__file__).resolve().parents[3];HERE=pathlib.Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);a=p.parse_args()
 out=(ROOT/a.output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
 source=HERE.parent/'chip_pad_feedback.sv'
 lock_path=HERE.parent/'pdk-lock.json';lock=json.loads(lock_path.read_text())
 # IO model is authenticated against the official archive via extraction receipt.
 download=ROOT/'build/t43/pdk-candidate/download.json'
 pad=ROOT/'build/t43/pdk-candidate/gf180mcuD/libs.ref/gf180mcu_fd_io/verilog/gf180mcu_fd_io.v'
 archive=ROOT/'build/t43/pdk-candidate/gf180mcu_fd_io.tar.zst'
 expected=lock['archives']['gf180mcu_fd_io.tar.zst']['sha256'];assert sha(archive)==expected
 name='gf180mcuD/libs.ref/gf180mcu_fd_io/verilog/gf180mcu_fd_io.v'
 original=subprocess.check_output(['tar','--zstd','-xOf',str(archive),name])
 assert hashlib.sha256(original).hexdigest()==sha(pad)
 receipt=dict(status='running',commands=[],scope='Combinational Boolean proof; 4-state IO-model simulation, no electrical qualification',assumptions=[],
  input_sha256={str(q.relative_to(ROOT)):sha(q) for q in (source,pathlib.Path(__file__),pad,archive,lock_path,ROOT/'tools/env/lock.json')})
 def run(cmd,label,ok=0,marker=None):
  start=time.monotonic();r=subprocess.run(list(map(str,cmd)),cwd=ROOT,capture_output=True,text=True,timeout=120)
  text=r.stdout+r.stderr;(out/(label+'.log')).write_text(text)
  receipt['commands'].append(dict(command=list(map(str,cmd)),seconds=time.monotonic()-start,returncode=r.returncode))
  assert r.returncode==ok and (not marker or marker in text),label
 cases={'correct':source.read_text(),
        'illegal_enable':source.read_text().replace('pad_ie = ~requested_drive','pad_ie = requested_drive'),
        'raw_while_driving':source.read_text().replace('(requested_drive & requested_data) | (~requested_drive & receiver)','receiver'),
        'wrong_output':source.read_text().replace('pad_data = requested_data','pad_data = ~requested_data')}
 harness='''module check(input data, drive, receiver);
 wire pd,oe,ie,rx;
 chip_pad_feedback #(.WIDTH(1)) dut(data,drive,receiver,pd,oe,ie,rx);
 always @* begin
  assert (!(oe && ie));
  if (drive) begin assert(oe && !ie); assert(pd==data); assert(rx==data); end
  else begin assert(!oe && ie); assert(rx==receiver); end
 end
 endmodule
'''
 try:
  for name,text in cases.items():
   sv=out/(name+'.sv');sv.write_text(text+'\n'+harness)
   run(['yosys','-p',f'read_verilog -formal -sv {sv}; prep -top check -flatten; chformal -lower; sat -prove-asserts -verify'],name,0 if name=='correct' else 1,
       'SUCCESS' if name=='correct' else 'proof did fail')
  bench=out/'tb.sv';bench.write_text('''`timescale 1ns/1ps
module tb;
 reg data,drive,external_data,external_enable;
 wire pd,oe,ie,rx,y;tri pad;
 assign pad=external_enable?external_data:1'bz;
 chip_pad_feedback #(.WIDTH(1)) dut(data,drive,y,pd,oe,ie,rx);
 gf180mcu_fd_io__bi_24t cell_pad(.CS(1'b0),.SL(1'b0),.IE(ie),.OE(oe),.PU(1'b0),.PD(1'b0),.A(pd),.PAD(pad),.Y(y));
 initial begin
  for(integer d=0;d<2;d=d+1) for(integer e=0;e<2;e=e+1) begin
   drive=0;data=d;external_enable=1;external_data=e;#5;
   if(rx!==e[0] || oe!==0 || ie!==1) $fatal(1,"released pad");
   drive=1;#5;
   if(rx!==d[0] || oe!==1 || ie!==0) $fatal(1,"driven feedback");
   if(d!=e && pad!==1'bx) $fatal(1,"contention model absent");
   external_enable=0;#5;if(pad!==d[0]) $fatal(1,"physical drive");
  end
  data=0;drive=1;external_enable=0;#5;if(rx!==0) $fatal(1,"open drain low");
  drive=0;external_enable=1;external_data=1;#5;if(rx!==1) $fatal(1,"open drain release");
  external_data=0;#5;if(rx!==0) $fatal(1,"external stretch");
  $display("PASS pad truth table, contention and open-drain release");$finish;
 end
endmodule
''')
  run(['iverilog','-g2012','-Dfunctional','-s','tb','-o',out/'sim',source,pad,bench],'compile')
  run(['vvp',out/'sim'],'simulation',marker='PASS pad truth table')
  patched=out/'pad_model.v';receipt['pad_model_patch']=prepare(patched)
  run(['iverilog','-g2012','-Dfunctional','-s','tb','-o',out/'sim-patched',source,patched,bench],'compile-patched')
  run(['vvp',out/'sim-patched'],'simulation-patched',marker='PASS pad truth table')
  receipt['status']='pass'
 finally:
  receipt['artifact_sha256']={str(q.relative_to(out)):sha(q) for q in out.rglob('*') if q.is_file() and q.name!='result.json'}
  (out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print('PASS D110 exhaustive Boolean proof, three caught faults and foundry pad simulation')
if __name__=='__main__':main()
