"""Assemble POR prototype from checked component layouts; not acceptance."""
from pathlib import Path
import re,json,subprocess,os,time,hashlib
import pya
import argparse
from common import Evidence,spice_ports
p=argparse.ArgumentParser(description=__doc__)
for n in ('monitor','timebase','digital','output','tech'):p.add_argument('--'+n,required=True)
p.add_argument('--pdk',default='build/t43/pdk-candidate/gf180mcuD');a=p.parse_args()
root=Path(__file__).resolve().parents[2];out=(root/a.output).resolve();out.relative_to(root/'build');out.mkdir(parents=True,exist_ok=False)
pdk=(root/a.pdk).resolve();lib=pdk/'libs.ref/gf180mcu_fd_sc_mcu7t5v0'
monitor=(root/a.monitor).resolve();osc=(root/a.timebase).resolve();digital=(root/a.digital).resolve();tech=(root/a.tech).resolve()
for q in (pdk,monitor,osc,digital,tech):q.relative_to(root/'build')
evidence=Evidence(out,__file__,pdk)
evidence.add_inputs([tech,monitor/'PorMonitorAnalog.gds',monitor/'PorMonitorAnalog.mag',monitor/'reference.spice',osc/'LfRcAnalog.gds',osc/'LfRcAnalog.mag',osc/'reference.spice',digital/'gds/PorQualifierPhysical.gds',digital/'lef/PorQualifierPhysical.lef',digital/'spice/PorQualifierPhysical.spice'])
lock=json.loads((root/'analog/physical/inputs.lock.json').read_text())
assert hashlib.sha256(tech.read_bytes()).hexdigest()==lock['patched_tech_sha256']
for src,prefix,top in [(monitor/'PorMonitorAnalog.gds','pm_','PorMonitorAnalog'),(osc/'LfRcAnalog.gds','pt_','PorTimebase')]:
 lay=pya.Layout();lay.read(str(src));oldtop=lay.top_cell()
 for c in lay.each_cell():
  if c==oldtop:c.name=top
  elif not c.name.startswith('pnp_'):c.name=prefix+c.name
 lay.write(str(out/(top+'.gds')))
script=f'gds readonly true\ndrc off\nlocking disable\ncrashbackups stop\ntech load {tech}\n'
for f in ('PorMonitorAnalog.gds','PorTimebase.gds'):script+=f'gds read {out/f}\n'
script+=f'gds read {digital}/gds/PorQualifierPhysical.gds\nload PorBrownoutMacro\n'
placements=[('PorMonitorAnalog','monitor',0,0),('PorTimebase','timebase',0,200),('PorQualifierPhysical','qualifier',340,200)]
for top,inst,x,y in placements:script+=f'getcell {top} child 0 0 parent {x}um {y}um\nidentify {inst}\n'
ports=['vdd','vss','threshold[0]','threshold[1]','test','supplyReset_n','powerOn_n','brownout'];nodes={}
def rect(x0,y0,x1,y1,l):
 assert x1>=x0 and y1>=y0,(x0,y0,x1,y1,l)
 return f'box values {x0:.5f}um {y0:.5f}um {x1:.5f}um {y1:.5f}um\npaint {l}\n'
def via(x,y,lower,v,upper):
 lo=.22 if lower=='metal5' else .2;hi=.22 if upper=='metal5' else .2;r=.13 if v=='via1' else .14
 return rect(x-lo,y-lo,x+lo,y+lo,lower)+rect(x-r,y-r,x+r,y+r,v)+rect(x-hi,y-hi,x+hi,y+hi,upper)
# All analog pins are left-facing M3. Escape outside both component boxes.
idx=0
for base,top,dy,mapping in [(monitor,'PorMonitorAnalog',0,{'vdd':'vdd','vss':'vss','higher':'higher','qualified':'supplyReset_n','good':'rawGood'}),(osc,'LfRcAnalog',200,{'vdd':'vdd','vss':'vss','enable':'vdd','clock':'reference','power_n':'cold_n'})]:
 mag=(base/(top+'.mag')).read_text();m=re.search(r'^magscale (\d+) (\d+)',mag,re.M);u=.05*int(m[1])/int(m[2])
 for m in re.finditer(r'^rlabel metal3 (?:s )?(-?\d+) (-?\d+) (-?\d+) (-?\d+) \d+ (\S+)$',mag,re.M):
  x=(int(m[1])+int(m[3]))*.5*u;y=(int(m[2])+int(m[4]))*.5*u+dy;ex=-4-idx*1.;idx+=1
  script+=rect(ex,y-.2,x+.2,y+.2,'metal3')+via(ex,y,'metal3','via3','metal4')+via(ex,y,'metal4','via4','metal5')
  nodes.setdefault(mapping[m[5]],[]).append((ex,y))
# Escape digital pins along their legal boundary layer; route in empty perimeter.
lef=(digital/'lef/PorQualifierPhysical.lef').read_text();dx=340;dy=200
mapping={'VDD':'vdd','VSS':'vss',**{n:n for n in ['brownout','cold_n','higher','powerOn_n','rawGood','reference','supplyReset_n','threshold[0]','threshold[1]']}}
for i,(pin,body) in enumerate(re.findall(r'  PIN (\S+)\n(.*?)  END \1\n',lef,re.S)):
 net=mapping[pin]
 shape=re.search(r'LAYER (Metal\d) ;\s*RECT ([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+)',body);assert shape,pin
 layer=shape[1].lower();x0,y0,x1,y1=map(float,shape.groups()[1:]);x=(x0+x1)/2+dx;y=(y0+y1)/2+dy
 if pin in ('VDD','VSS'):
  # Take M4 power strap out through the north boundary, away from all M5 straps.
  ey=dy+105+i*1.;ex=455+i*1.
  script+=rect(x-.2,y,x+.2,ey,'metal4')+via(x,ey,'metal4','via4','metal5')
  script+=rect(x,ey-.22,ex+.22,ey+.22,'metal5')
 elif layer=='metal2':
  ey=dy-4-i*1.;ex=455+i*1.
  script+=rect(x-.2,ey,x+.2,y+.2,'metal2')+via(x,ey,'metal2','via2','metal3')
  script+=rect(x,ey-.2,ex,ey+.2,'metal3')+via(ex,ey,'metal3','via3','metal4')+via(ex,ey,'metal4','via4','metal5')
 else:
  # Left ports go left only into the inter-macro gap; vertical M5 reaches
  # a track below both upper blocks, then heads to the outer right corridor.
  if x0<1:
   ex0=dx-4-i*.9;ey=dy+110+i*1.;ex=455+i*1.
   script+=rect(ex0,y-.2,x+.2,y+.2,'metal3')+via(ex0,y,'metal3','via3','metal4')+via(ex0,y,'metal4','via4','metal5')
   script+=rect(ex0-.22,min(ey,y),ex0+.22,max(ey,y),'metal5')+via(ex0,ey,'metal4','via4','metal5')
   script+=rect(ex0,ey-.2,ex,ey+.2,'metal4')+via(ex,ey,'metal4','via4','metal5')
  else:
   ex=455+i*1.;ey=y
   script+=rect(x-.2,y-.2,ex,y+.2,'metal3')+via(ex,y,'metal3','via3','metal4')+via(ex,y,'metal4','via4','metal5')
 nodes.setdefault(net,[]).append((ex,ey))
for i,(net,pins) in enumerate(nodes.items()):
 y=-5-i*1.;left=min(x for x,py in pins)-.22;right=max(x for x,py in pins)+.22
 script+=rect(left,y-.2,right,y+.2,'metal4')
 for x,py in pins:script+=rect(x-.22,y,x+.22,py,'metal5')+via(x,y,'metal4','via4','metal5')
 if net in ports:
  script+=f'box values {left:.5f}um {y-.2:.5f}um {left+1:.5f}um {y+.2:.5f}um\nlabel {{{net}}} c metal4\nport make {ports.index(net)+1}\n'
 # Internal named nodes are retained for characterization.
 else:script+=f'box values {left:.5f}um {y-.2:.5f}um {left+.4:.5f}um {y+.2:.5f}um\nlabel {{{net}}} c metal4\n'
script+=rect(-15,-25,-14,-24.6,'metal4')+'label test c metal4\nport make 5\n'
script+='save PorBrownoutMacro\ngds write PorBrownoutMacro.gds\nlef write PorBrownoutMacro.lef\nflatten -dotoplabels PorBrownoutFlat\nload PorBrownoutFlat\nsave PorBrownoutFlat\nextract all\next2spice lvs\next2spice -o extracted.spice\nquit -noprompt\n'
(out/'assemble.tcl').write_text(script)
start=time.monotonic()
with (out/'assemble.log').open('w') as f:r=subprocess.run([str(evidence.magic),'-dnull','-noconsole','-rcfile',str(pdk/'libs.tech/magic/gf180mcuD.magicrc'),'assemble.tcl'],cwd=out,env={**os.environ,'PDK_ROOT':str(pdk.parent)},stdout=f,stderr=subprocess.STDOUT,timeout=120)
assert r.returncode==0
ref=(monitor/'reference.spice').read_text()+'\n'+(osc/'reference.spice').read_text().replace('LfRcAnalog','PorTimebase')+'\n'+(lib/'spice/gf180mcu_fd_sc_mcu7t5v0.spice').read_text()+'\n'
dsp=(digital/'spice/PorQualifierPhysical.spice').read_text();dsp=dsp[dsp.index('.subckt PorQualifierPhysical'):];expected_ports=['VDD','VSS','brownout','cold_n','higher','powerOn_n','rawGood','reference','supplyReset_n','threshold[0]','threshold[1]'];actual_ports=spice_ports(dsp,'PorQualifierPhysical',expected_ports);assert actual_ports==expected_ports,'Qualifier pin order changed';dsp,n=re.subn(r'^(X\S+) VDD VSS gf180mcu_fd_sc_mcu7t5v0__endcap$',r'\1 VDD VDD VSS VSS gf180mcu_fd_sc_mcu7t5v0__endcap',dsp,flags=re.M);assert n==44;ref+=dsp+'\n.subckt PorBrownoutMacro '+' '.join(ports)+'\nXmonitor vdd vss higher supplyReset_n rawGood PorMonitorAnalog\nXtimebase vdd vss vdd reference cold_n PorTimebase\nXqualifier vdd vss brownout cold_n higher powerOn_n rawGood reference supplyReset_n threshold[0] threshold[1] PorQualifierPhysical\n.ends PorBrownoutMacro\n'
(out/'reference.spice').write_text(ref)
print('Assembled POR prototype',time.monotonic()-start)

evidence.finish()
