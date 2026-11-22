"""Fresh reproduction of the existing qualified USB mapping, not a new recipe."""
import hashlib,json,subprocess,sys
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root))
from tools.timing.usb_enable_fanout import replicate,prove_pair,size_enable_buffers
from tools.timing.usb_buffer_sizing import size
from tools.timing.fanout import buffer_module
base=root/'build/plan03/production-measure04';base.mkdir(exist_ok=False)
old=root/'build/plan03/fast02/fast/usb/timing/usb'
out=base/'usb-mapping';out.mkdir()
lib=root/'build/riscay-mcu/.tools/physical/pdk/gf180mcu_fd_sc_mcu7t5v0__ss_125C_3v00.lib'
for name in ('mapping.abc','mapping.constr'):(out/name).write_bytes((old/name).read_bytes())
script=(old/'synth.ys').read_text().replace(str(old),str(out))
(out/'synth.ys').write_text(script)
def run(name,commands):
    p=out/(name+'.ys');p.write_text(commands)
    with (out/(name+'.log')).open('w') as f:subprocess.run(['yosys','-Q','-T','-s',str(p)],stdout=f,stderr=subprocess.STDOUT,check=True)
run('synth',script)
design=json.loads((out/'mapped.json').read_text());m=design['modules']['Usb']
m,replication=replicate(m,'Usb');replication['proof']=prove_pair(lib,out/'enable-replica-proof')
m,inserted=buffer_module(m,'usbClock')
m,enable_sizing=size_enable_buffers(m,lib,out/'enable-buffer-sizing')
m,sizing=size(m,lib,out/'usb-buffer-sizing')
design['modules']['Usb']=m;(out/'buffered.json').write_text(json.dumps(design))
run('export','\n'.join([f'read_json {out}/buffered.json','check -assert','scc -expect 0',f'write_json {out}/mapped.json',f'write_verilog -noattr -noexpr {out}/mapped.v'])+'\n')
# A fresh, exact match is stronger than relying on the old timing summary.
assert (out/'mapped.v').read_bytes()==(old/'mapped.v').read_bytes(),'Fresh USB mapping differs from qualified recipe'
(out/'result.json').write_text(json.dumps(dict(status='pass',fresh_mapping='byte-identical emitted mapped Verilog',
  reference=str(old/'mapped.v'),sha256=hashlib.sha256((out/'mapped.v').read_bytes()).hexdigest(),
  enable_replication=replication,fanout_buffers=len(inserted),enable_sizing=enable_sizing,sizing=sizing),indent=2)+'\n')
print('PASS fresh USB mapping reproduced; integration timing remains unmeasured',flush=True)
