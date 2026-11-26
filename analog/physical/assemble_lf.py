"""Assemble actual analog geometry with mapped Chisel readiness cells."""
import pathlib,re,json,shutil,subprocess,os,time,hashlib
import argparse
from common import Evidence,lf_port_bindings
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--analog',required=True);p.add_argument('--mapping',required=True);p.add_argument('--output',required=True);p.add_argument('--pdk',default='build/t43/pdk-candidate/gf180mcuD');a=p.parse_args()
root=pathlib.Path(__file__).resolve().parents[2]
out=(root/a.output).resolve();out.relative_to(root/'build');out.mkdir(parents=True,exist_ok=False)
analog=(root/a.analog).resolve();analog.relative_to(root/'build');pdk=(root/a.pdk).resolve();pdk.relative_to(root/'build')
lib=pdk/'libs.ref/gf180mcu_fd_sc_mcu7t5v0';mapping=(root/a.mapping).resolve();mapping.relative_to(root/'build')
evidence=Evidence(out,__file__,pdk)
evidence.add_inputs([mapping,analog/'reference.spice',*analog.glob('*.mag')])
mapped=json.loads(mapping.read_text())['modules']['LfReadyPhysical']
for path in analog.glob('*.mag'):shutil.copyfile(path,out/path.name)
lock=json.loads((root/'analog/physical/inputs.lock.json').read_text());magic=lock['magic_store_path']+'/bin/magic'
assert hashlib.sha256(pathlib.Path(magic).read_bytes()).hexdigest()==lock['magic_executable_sha256']
ports=['vdd','vss','enable',*[f'trim[{i}]' for i in range(6)],'test','clock','ready']
bitnet=lf_port_bindings(mapped)
net=lambda b:bitnet.get(b,f'digital{b}')
cdl=(lib/'spice/gf180mcu_fd_sc_mcu7t5v0.spice').read_text()
pinorders={m[1]:m[2].split() for m in re.finditer(r'^\.SUBCKT (\S+) (.+)$',cdl,re.M)}
reference=(analog/'reference.spice').read_text()+'\n'+cdl+'\n.subckt LfRcMacro '+' '.join(ports)+'\nXanalog vdd vss enable clock init_n LfRcAnalog\n'
script=f'drc off\nlocking disable\ncrashbackups stop\ngds readonly true\ngds read {lib}/gds/gf180mcu_fd_sc_mcu7t5v0.gds\n'
for typename in sorted({c['type'] for c in mapped['cells'].values()}|{'gf180mcu_fd_sc_mcu7t5v0__filltie'}):
    script+=f'load {typename}\nsave {typename}\n'
script+='load LfRcMacro\ngetcell LfRcAnalog child 0 0 parent 0 0\nidentify Xanalog\n'
def rect(x0,y0,x1,y1,layer):return f'box values {x0:.5f}um {y0:.5f}um {x1:.5f}um {y1:.5f}um\npaint {layer}\n'
def via(x,y,lower,v,upper):
    radius=.13 if v=='via1' else .14
    lo=.19 if lower=='metal1' else .2
    hi=.22 if upper=='metal5' else .2
    return rect(x-lo,y-lo,x+lo,y+lo,lower)+rect(x-radius,y-radius,x+radius,y+radius,v)+rect(x-hi,y-hi,x+hi,y+hi,upper)
nodes={};placement=[]
# The row is in verified empty space below the analog transistor row, right of Rbias.
cursor=160.;row=20.
for i,cell in enumerate(mapped['cells'].values()):
    typename=cell['type'];mag=(lib/'maglef'/f'{typename}.mag').read_text()
    bounds=[int(v)*.005 for v in re.search(r'string FIXED_BBOX (.+)',mag)[1].split()]
    pins={}
    for m in re.finditer(r'^rlabel (\S+) s (-?\d+) (-?\d+) (-?\d+) (-?\d+) \d+ (\S+)$',mag,re.M):
        if m[1]=='metal1':pins.setdefault(m[6],[]).append(tuple(int(m[j])*.005 for j in range(2,6)))
    connections={k:net(v[0]) for k,v in cell['connections'].items()}
    connections.update(VDD='vdd',VNW='vdd',VPW='vss',VSS='vss')
    reference+=f'Xready{i} '+ ' '.join(connections[p] for p in pinorders[typename])+f' {typename}\n'
    script+=f'getcell {typename} child 0 0 parent {cursor:.5f}um {row:.5f}um\nidentify Xready{i}\n'
    placement.append(dict(cell=typename,x=cursor,y=row))
    for j,pin in enumerate(k for k in connections if k not in ('VNW','VPW')):
        choices=[b for b in pins[pin] if b[2]-b[0]>=.38-1e-9 and b[3]-b[1]>=.38-1e-9]
        # Some library access rectangles are narrower than a new landing.
        # Expansion is allowed only if the resulting full-layout DRC passes.
        if not choices:choices=pins[pin]
        b=max(choices,key=lambda b:(b[2]-b[0])*(b[3]-b[1]))
        px=round(((b[0]+b[2])/2)/.005)*.005
        if pin=='VDD':px=-.6
        if pin=='VSS':px=-1.4
        py=round(((b[1]+b[3])/2)/.005)*.005
        x,y=cursor+px,row+py
        if pin in ('VDD','VSS'):script+=rect(x-.2,y-.2,cursor+.5,y+.2,'metal1')
        ex=cursor+.5+j*1.;ey=row-1-j*.9
        script+=via(x,y,'metal1','via1','metal2')+via(x,y,'metal2','via2','metal3')
        script+=rect(x-.2,ey,x+.2,y,'metal3')+via(x,ey,'metal3','via3','metal4')
        script+=rect(min(x,ex),ey-.2,max(x,ex),ey+.2,'metal4')+via(ex,ey,'metal4','via4','metal5')
        nodes.setdefault(connections[pin],[]).append((ex,ey))
    tapx=cursor+bounds[2]-bounds[0]
    script+=f'getcell gf180mcu_fd_sc_mcu7t5v0__filltie child 0 0 parent {tapx:.5f}um {row:.5f}um\nidentify Xtap{i}\n'
    script+=f'getcell gf180mcu_fd_sc_mcu7t5v0__filltie child 0 0 parent {cursor-1.12:.5f}um {row:.5f}um\nidentify Xtapleft{i}\n'
    reference+=f'Xtap{i} vdd vss gf180mcu_fd_sc_mcu7t5v0__filltie\n'
    reference+=f'Xtapleft{i} vdd vss gf180mcu_fd_sc_mcu7t5v0__filltie\n'
    cursor+=bounds[2]-bounds[0]+1.12+4
# Connect the real analog ports, using distinct upper-metal risers.
mag=(analog/'LfRcAnalog.mag').read_text()
scale=re.search(r'^magscale (\d+) (\d+)',mag,re.M);unit=.05*int(scale[1])/int(scale[2])
for i,m in enumerate(re.finditer(r'^rlabel metal3 (?:s )?(-?\d+) (-?\d+) (-?\d+) (-?\d+) \d+ (\S+)$',mag,re.M)):
    b=[int(m[j])*unit for j in range(1,5)];name=m[5]
    x,y=(b[0]+b[2])/2,(b[1]+b[3])/2;ex=2+i*.9
    script+=via(x,y,'metal3','via3','metal4')+rect(min(x,ex),y-.2,max(x,ex),y+.2,'metal4')+via(ex,y,'metal4','via4','metal5')
    nodes.setdefault('init_n' if name=='power_n' else name,[]).append((ex,y))
for i,(name,pins) in enumerate(nodes.items()):
    y=-20+i*.9;left=1 if name in ports else min(x for x,py in pins)-.2;right=max(x for x,py in pins)+.2
    script+=rect(left,y-.2,right,y+.2,'metal4')
    for x,py in pins:script+=rect(x-.22,min(py,y),x+.22,max(py,y),'metal5')+via(x,y,'metal4','via4','metal5')
    if name in ports:script+=f'box values 1um {y-.2:.5f}um 2um {y+.2:.5f}um\nlabel {{{name}}} c metal4\nport make {ports.index(name)+1}\n'
    elif name=='init_n':script+=f'box values {left:.5f}um {y-.2:.5f}um {left+.4:.5f}um {y+.2:.5f}um\nlabel init_n c metal4\n'
for i,name in enumerate(ports):
    if name in nodes:continue
    y=15+i*.9;script+=rect(1,y,2,y+.4,'metal4')+f'label {{{name}}} c metal4\nport make {i+1}\n'
script+='save LfRcMacro\ndrc check\ndrc catchup\nputs "DRC_TOP [drc listall why]"\nextract all\next2spice lvs\next2spice -o extracted.spice\ngds write LfRcMacro.gds\nlef write LfRcMacro.lef\n'
(out/'reference.spice').write_text(reference+'.ends LfRcMacro\n')
(out/'assemble.tcl').write_text('if {[catch {\n'+script+'\n} m o]} {puts stderr $m;puts stderr [dict get $o -errorinfo];exit 1}\nquit -noprompt\n')
start=time.monotonic()
with (out/'assemble.log').open('w') as log:r=subprocess.run([magic,'-dnull','-noconsole','-rcfile',str(pdk/'libs.tech/magic/gf180mcuD.magicrc'),'assemble.tcl'],cwd=out,env={**os.environ,'PDK_ROOT':str(pdk.parent)},stdout=log,stderr=subprocess.STDOUT,timeout=120)
assert r.returncode==0
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
(out/'result.json').write_text(json.dumps({'status':'prototype_requires_checks','seconds':time.monotonic()-start,'script_sha256':sha(pathlib.Path(__file__)),'inputs':{str(p):sha(p) for p in [mapping,analog/'reference.spice',lib/'spice/gf180mcu_fd_sc_mcu7t5v0.spice',lib/'gds/gf180mcu_fd_sc_mcu7t5v0.gds']},'placement':placement},indent=2)+'\n')
print('Generated full LF prototype; checks still required')



evidence.finish()
