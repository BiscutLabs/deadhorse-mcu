"""Elaborate the physical socket around authenticated production RTL; no P&R."""
import argparse,collections,hashlib,json,pathlib,subprocess,sys,time
ROOT=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.pdk import liberty
from dv.soc.analog.binding import interfaces,audit
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser()
 for name in ('chip','emit','reference','output'):p.add_argument('--'+name,required=True)
 a=p.parse_args();chip,emit,ref,out=[(ROOT/getattr(a,n)).resolve() for n in ('chip','emit','reference','output')]
 for q in (chip,emit,ref,out):q.relative_to(ROOT/'build')
 out.mkdir(parents=True,exist_ok=False)
 prepared=json.loads((chip/'chip-receipt.json').read_text());assert not prepared['simulation']
 for n,h in prepared['input_sha256'].items():assert sha(ROOT/n)==h
 for n,h in prepared['artifact_sha256'].items():assert sha(chip/n)==h
 prior=json.loads((ref/'result.json').read_text());assert prior['status']=='mapped'
 files=[]
 for n,h in prior['emitted_sha256'].items():
  # Exact same production module bytes as the reviewed mapping, fresh emission.
  relative=pathlib.Path(n).relative_to(ref.parent/'emit') if pathlib.Path(n).is_absolute() else pathlib.Path(n).relative_to((ref.parent/'emit').relative_to(ROOT))
  q=emit/relative;assert sha(q)==h,relative;files.append(q)
 corelib=liberty();assert sha(corelib)==prior['liberty_sha256']
 libs=[]
 # Exact SRAM Liberty identities recorded by the qualified production map.
 for name,expected in prior['sram_liberties'].items():
  q=ROOT/name;assert sha(q)==expected;libs.append(q)
 archive=ROOT/'build/t43/pdk-candidate/gf180mcu_fd_io.tar.zst'
 lock=ROOT/'phys/gf180-ws-1x1/pdk-lock.json'
 assert sha(archive)==json.loads(lock.read_text())['archives'][archive.name]['sha256']
 name='gf180mcuD/libs.ref/gf180mcu_fd_io/verilog/gf180mcu_fd_io__blackbox_pp.v'
 pad=out/'pads.v';pad.write_bytes(subprocess.check_output(['tar','--zstd','-xOf',str(archive),name]))
 analog=out/'analog.json';analog.write_text(json.dumps(interfaces()))
 ip=sorted((chip/'ip').glob('*/vh/*.v'));assert len(ip)==5
 sources=[*files,chip/'src/chip_top.sv',chip/'src/chip_core.sv',chip/'src/chip_pad_feedback.sv']
 deps=[*sources,*ip,pad,analog,corelib,*libs,archive,lock,ref/'result.json',chip/'chip-receipt.json',pathlib.Path(__file__),ROOT/'dv/soc/analog/binding.py',ROOT/'tools/pdk.py',ROOT/'tools/env/lock.json']
 inputs={q.relative_to(ROOT).as_posix():sha(q) for q in deps}
 script=out/'import.ys'
 script.write_text('\n'.join([f'read_liberty -lib {corelib}',*[f'read_liberty -lib {q}' for q in libs],f'read_json {analog}',f'read_verilog -lib {pad} '+ ' '.join(map(str,ip)),
  'read_slang --keep-hierarchy -DSYNTHESIS -DUSE_POWER_PINS -DENABLE_INITIAL_MEM_ -I '+str(chip/'src')+' --top chip_top '+' '.join(map(str,sources)),
  'hierarchy -check -top chip_top','proc','memory_collect','check -assert',f'write_json {out}/design.json'])+'\n')
 start=time.monotonic();command=['yosys','-Q','-T','-s',str(script)]
 with (out/'import.log').open('w') as log:r=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=600)
 assert r.returncode==0,'production chip elaboration'
 design=json.loads((out/'design.json').read_text())
 top=design['modules']['chip_top'];socket=design['modules'][top['cells']['i_chip_core']['type']]
 soc=design['modules'][socket['cells']['soc']['type']]
 # Slang specializes module names per instance; audit the actual core object.
 rows=audit({'modules':{**design['modules'],'DeadhorseSoc':soc}})
 counts=collections.Counter()
 def walk(name):
  for c in design['modules'][name]['cells'].values():
   counts[c['type']]+=1
   if c['type'] in design['modules'] and not design['modules'][c['type']].get('attributes',{}).get('blackbox'):walk(c['type'])
 walk('chip_top')
 for kind,count in {'gf180mcu_fd_io__bi_24t':40,'gf180mcu_fd_io__in_c':13,'gf180mcu_fd_io__in_s':1,'gf180mcu_fd_io__asig_5p0':2,
  'LfRcMacro':1,'PorBrownoutMacro':1,'gf180mcu_ocd_ip_sram__sram1024x8m8wm1':16,'gf180mcu_ocd_ip_sram__sram512x8m8wm1':4}.items():assert counts[kind]==count,(kind,counts[kind])
 top=design['modules']['chip_top'];socket=design['modules'][top['cells']['i_chip_core']['type']]
 status={n:v for n,v in socket['netnames'].items() if n.startswith('status_')}
 assert len(status)==8 and all(int(v['attributes']['keep'],2)==1 for v in status.values())
 aliases={c['connections']['Y'][0]:c['connections']['A'][0] for c in top['cells'].values()
          if c['type']=='$buf' and len(c['connections']['Y'])==len(c['connections']['A'])==1}
 def root(bit):
  seen=set()
  while bit in aliases:
   assert bit not in seen;seen.add(bit);bit=aliases[bit]
  return bit
 for core,pad_supply in (('VDD','DVDD'),('VSS','DVSS')):
  assert root(top['ports'][core]['bits'][0])==root(top['ports'][pad_supply]['bits'][0])
 assert all(sha(ROOT/n)==h for n,h in inputs.items())
 result=dict(status='elaborated_not_physical',command=command,seconds=time.monotonic()-start,input_sha256=inputs,
  checked_counts={k:v for k,v in counts.items() if k.startswith('gf180mcu') or k in ('LfRcMacro','PorBrownoutMacro')},analog_binding=rows,
  kept_status_ports=sorted(status),scope='Production logical hierarchy only; analogs are pin-only blackboxes, not physical abstracts')
 result['artifact_sha256']={q.relative_to(out).as_posix():sha(q) for q in out.iterdir() if q.is_file()}
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS production chip hierarchy, pad/SRAM inventory, status preservation and analog binding; no physical fit claim')
if __name__=='__main__':main()
