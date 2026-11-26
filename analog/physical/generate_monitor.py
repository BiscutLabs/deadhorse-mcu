"""Generate the D111 supply-monitor candidate; complete POR also needs clocked qualification.

Uses pinned RISCay topology and unchanged foundry PNP geometry.
"""
import pathlib,re,subprocess,json,os,hashlib,time,shutil
import argparse,sys
from common import Evidence
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',required=True)
parser.add_argument('--pdk',default='build/t43/pdk-candidate/gf180mcuD')
parser.add_argument('--reference',default='build/riscay-mcu')
parser.add_argument('--tech',required=True)
args=parser.parse_args()
root=pathlib.Path(__file__).resolve().parents[2]
out=(root/args.output).resolve();out.relative_to(root/'build');out.mkdir(parents=True,exist_ok=False)
pdk=(root/args.pdk).resolve();pdk.relative_to(root/'build')
lock=json.loads((root/'analog/physical/inputs.lock.json').read_text())
magic=lock['magic_store_path']+'/bin/magic'
assert hashlib.sha256(pathlib.Path(magic).read_bytes()).hexdigest()==lock['magic_executable_sha256']
tech=(root/args.tech).resolve();tech.relative_to(root/'build')
assert hashlib.sha256(tech.read_bytes()).hexdigest()==lock['patched_tech_sha256']
evidence=Evidence(out,__file__,pdk)
evidence.add_inputs([tech])
source=(root/args.reference/'analog/gf180-clock-reset/circuits.py').resolve()
source.relative_to(root/'build')
revision='4671317186003740ceb61360ba08c59bbdf10136'
assert lock['riscay_source']['revision']==revision
assert hashlib.sha256(source.read_bytes()).hexdigest()==lock['riscay_source']['files']['analog/gf180-clock-reset/circuits.py']
evidence.add_inputs([source])
sys.path.insert(0,str(source.parent))
from circuits import supply_monitor
s=supply_monitor().replace('pmos_3p3','pfet_03v3').replace('nmos_3p3','nfet_03v3').replace('vpnp_0p42x5','pnp_05p00x00p42')
lines=[]
for line in s.splitlines():
    if 'ppolyf_u_3k' not in line:lines.append(line);continue
    t=line.split();name,hi,lo=t[:3]
    old=float(re.search(r'r_length=([\d.]+)u',line)[1])
    ohms=(old+.1864)*3000/.955
    if name in ('Xtop','Xbottom','Xhysteresis'):ohms/=4
    n=max(1,int(ohms/5e6)+1)
    length=(ohms/n*.9704-170.9)/1000
    for i in range(n):
        a=hi if i==0 else f'{name}_n{i}'
        b=lo if i==n-1 else f'{name}_n{i+1}'
        lines.append(f'{name}_{i} {a} {b} vss ppolyf_u_1k r_width=1u r_length={length:.6f}u')
s='\n'.join(lines)+'\n'
s=s.replace('riscay_supply_monitor_gf180','PorMonitorAnalog')
s=s.replace('.subckt PorMonitorAnalog vdd vss good','.subckt PorMonitorAnalog vdd vss higher qualified good')
s=s.replace('Xtop_0 vdd ','Xtop_0 selected_vdd ').replace('Xhysteresis_0 good ','Xhysteresis_0 qualified ')
length=(21300*.9704-170.9)/1000
extra=f'XselectR vdd selected_vdd vss ppolyf_u_1k r_width=1u r_length={length:.6f}u\n'
extra+='XselectP selected_vdd higher vdd vdd pfet_03v3 w=4u l=.28u\n'
baseline=s.replace('.ends PorMonitorAnalog',extra+'.ends PorMonitorAnalog')
# Preserve the base monitor; the selected candidate uses transistor startup.
s=re.sub(r'^Xstartup_\d+ .+\n','',s,flags=re.M)
for i in range(4):
 d='start_control' if i==0 else f'start_p{i}'
 src='vdd' if i==3 else f'start_p{i+1}'
 extra+=f'Xstart_p{i} {d} vss {src} vdd pfet_03v3 w=.44u l=50u\n'
extra+='Xstart_n0 start_control vref start_mid vss nfet_03v3 w=4u l=.28u\n'
extra+='Xstart_n1 start_mid vref vss vss nfet_03v3 w=4u l=.28u\n'
extra+='Xstart_kick pbias start_control vss vss nfet_03v3 w=.22u l=10u\n'
s=s.replace('.ends PorMonitorAnalog',extra+'.ends PorMonitorAnalog')
circuit=s
ports=('vdd','vss','higher','qualified','good')
# Fold each simple series group into one real resistor, preserving its nominal
# length plus the removed end-contact terms. No branch node may be discarded.
for prefix in ('Xptat','Xgain','Xtop','Xbottom','Xhysteresis'):
    rows=[l.split() for l in circuit.splitlines() if re.match('^'+prefix+r'_\d+ ',l)]
    assert rows,prefix
    for a,b in zip(rows,rows[1:]):
        assert a[2]==b[1]
        assert len(re.findall(r'(?<!\S)'+re.escape(a[2])+r'(?!\S)',circuit))==2
    length=sum(float(re.search(r'r_length=([\d.]+)u',' '.join(r))[1]) for r in rows)+(len(rows)-1)*.1709
    circuit=re.sub('^'+prefix+r'_\d+ .+\n','',circuit,flags=re.M)
    if prefix=='Xhysteresis':
        # Two sub-15000um2 resistor markers avoid the large-marker 20um
        # adjacency rule, without changing total nominal DC resistance.
        half=(length-.1709)/2
        replacement=f'{prefix}fold0 {rows[0][1]} hys_mid vss ppolyf_u_1k r_width=1u r_length={half:.6f}u\n{prefix}fold1 hys_mid {rows[-1][2]} vss ppolyf_u_1k r_width=1u r_length={half:.6f}u\n'
    else:replacement=f'{prefix}fold {rows[0][1]} {rows[-1][2]} vss ppolyf_u_1k r_width=1u r_length={length:.6f}u\n'
    circuit=circuit.replace('.ends PorMonitorAnalog',replacement+'.ends PorMonitorAnalog')
(out/'reference.spice').write_text(circuit)
devices=[];cells={}
for line in circuit.splitlines():
    if not line.startswith('X'):continue
    tokens=line.split();model=next(v for v in tokens if v in ('nfet_03v3','pfet_03v3','ppolyf_u_1k','pnp_05p00x00p42'))
    pos=tokens.index(model);nets=tokens[1:pos]
    params={k:float(v[:-1]) for k,v in re.findall(r'(w|l|r_width|r_length)=([\d.]+u)',line)}
    key=(model,tuple(sorted(params.items())))
    if key not in cells:cells[key]={'name':f'dev{len(cells)}','model':model,'parameters':params}
    devices.append({'name':tokens[0],'nets':nets,'cell':cells[key]['name']})
def run(name,script):
    path=out/(name+'.tcl');path.write_text('if {[catch {\n'+f'tech load {tech}\n'+script+'\n} message options]} {puts stderr $message;puts stderr [dict get $options -errorinfo];exit 1}\nquit -noprompt\n')
    start=time.monotonic()
    with (out/(name+'.log')).open('w') as log:
        p=subprocess.run([magic,'-dnull','-noconsole','-rcfile',str(pdk/'libs.tech/magic/gf180mcuD.magicrc'),str(path)],cwd=out,env={**os.environ,'PDK_ROOT':str(pdk.parent)},stdout=log,stderr=subprocess.STDOUT,timeout=120)
    assert p.returncode==0,(name,p.returncode)
    print(name,time.monotonic()-start)
script='drc off\nlocking disable\ncrashbackups stop\n'
for cell in cells.values():
    model=cell['model'];p=cell['parameters']
    if model=='pnp_05p00x00p42':
        original=pdk/'libs.ref/gf180mcu_fd_pr/mag/pnp_05p00x00p42_0.mag'
        shutil.copyfile(original,out/original.name)
        # Preserve the authenticated GDS-backed leaf; access geometry belongs
        # to a wrapper and must survive stream-out independently.
        (out/(cell['name']+'.mag')).write_text('magic\ntech gf180mcuD\nmagscale 1 10\nuse pnp_05p00x00p42_0 primitive\ntransform 1 0 0 0 1 0\nbox -338 -796 338 796\n<< end >>\n')
        cell['geometry_file']=original.name
        cell['source_sha256']=hashlib.sha256(original.read_bytes()).hexdigest()
        continue
    if model=='ppolyf_u_1k':
        nf=90 if p['r_length']>8000 else 45 if p['r_length']>1000 else 5 if p['r_length']>100 else 2
        # PDK serpentine extraction: nf*drawn_length - .6*(nf-1) + .44.
        length=round(((p['r_length']+.6*(nf-1)-.44)/nf)/.005)*.005
        overrides=dict(w=p['r_width'],l=length,nx=nf,snake=1,guard=1)
    else:overrides={**p,'guard':1,'diff_gate_space':.5,'diff_spacing':.6,'gate_to_diffcont':.7}
    cell['draw_parameters']=overrides
    script+=f'load {cell["name"]}\nbox values 0 0 0 0\nset p [dict merge [gf180mcu::{model}_defaults] {{{" ".join(f"{k} {v:g}" for k,v in overrides.items())}}}]\nset p [gf180mcu::{model}_check $p]\ngf180mcu::{model}_draw $p\nsave {cell["name"]}\n'
run('draw',script)
def rect(x0,y0,x1,y1,layer):return f'box values {x0:.5f}um {y0:.5f}um {x1:.5f}um {y1:.5f}um\npaint {layer}\n'
def land(x,y,lower,via,upper):
    radius=.14 if via in ('via2','via3') else .13
    return rect(x-.2,y-.2,x+.2,y+.2,lower)+rect(x-radius,y-radius,x+radius,y+radius,via)+rect(x-.2,y-.2,x+.2,y+.2,upper)
script='drc off\nlocking disable\ncrashbackups stop\n'
for cell in cells.values():
    name=cell['name'];model=cell['model'];layers={};layer=None
    for line in (out/cell.get('geometry_file',name+'.mag')).read_text().splitlines():
        if line.startswith('<< '):layer=line[3:-3];layers.setdefault(layer,[])
        elif line.startswith('rect ') and layer!='checkpaint':layers[layer].append(tuple(int(x)*.005 for x in line.split()[1:]))
    allrects=[r for rr in layers.values() for r in rr]
    cell['bounds']=[min(r[0] for r in allrects),min(r[1] for r in allrects),max(r[2] for r in allrects),max(r[3] for r in allrects)]
    def centers(layer):return [((r[0]+r[2])/2,(r[1]+r[3])/2) for r in layers[layer]]
    if model=='pnp_05p00x00p42':
        pins={'C':(1.5,.005),'B':(-.75,.015),'E':(0,-.005)}
    elif model=='ppolyf_u_1k':
        contacts=sorted(centers('polycontact'));pins={'A':contacts[0],'Z':contacts[-1],'B':min(centers('psubdiffcont'))}
    else:
        contacts=sorted(centers('pdiffc' if model.startswith('p') else 'ndiffc'))
        pins={'D':contacts[-1],'G':max(centers('polycontact'),key=lambda q:q[1]),'S':contacts[0],'B':min(centers('nsubdiffcont' if model.startswith('p') else 'psubdiffcont'))}
    cell['pins']=pins;script+=f'load {name}\n'
    for x,y in centers('polycontact') if 'polycontact' in layers else []:
        script+=rect(x-.2,y-.2,x+.2,y+.2,'metal1')
    for i,(pin,(x,y)) in enumerate(pins.items(),1):script+=land(x,y,'metal1','via1','metal2')+f'label {pin} c metal2\nport make {i}\n'
    # Remove the generator's display-selection box; actual geometry sets the macro bounds.
    script+=f'property FIXED_BBOX\nsave {name}\ndrc check\ndrc catchup\nputs "DRC_{name} [drc listall why]"\nextract all\next2spice lvs\next2spice -o {name}.spice\n'
run('access',script)
for cell in cells.values():
    path=out/(cell['name']+'.mag')
    path.write_text('\n'.join(line for line in path.read_text().splitlines() if not line.startswith('string FIXED_BBOX '))+'\n')
script='drc off\nlocking disable\ncrashbackups stop\n'
rotated={}
for cell in list(cells.values()):
    if cell['model'] in ('ppolyf_u_1k','pnp_05p00x00p42') or cell['parameters']['l']<20:continue
    name=cell['name'];rname=name+'_rot';bb=cell['bounds']
    (out/(rname+'.mag')).write_text('magic\ntech gf180mcuD\nmagscale 1 10\n'+f'use {name} core\ntransform 0 -1 0 1 0 0\nbox '+ ' '.join(str(round(v*200)) for v in bb)+'\n<< end >>\n')
    pins={};script+=f'load {rname}\n'
    for i,(pin,(oldx,oldy)) in enumerate(cell['pins'].items(),1):
        x,y=-oldy,oldx;escape=2+(i-1)*.9
        script+=land(x,y,'metal2','via2','metal3')+rect(min(x,escape),y-.2,max(x,escape),y+.2,'metal3')+land(escape,y,'metal2','via2','metal3')+f'label {pin} c metal2\nport make {i}\n'
        pins[pin]=(escape,y)
    rotated[name]={'name':rname,'model':cell['model'],'parameters':cell['parameters'],'bounds':[-bb[3],bb[0],max(-bb[1],5),bb[2]],'pins':pins}
    script+=f'save {rname}\ndrc check\ndrc catchup\nputs "DRC_{rname} [drc listall why]"\nextract all\next2spice lvs\next2spice -o {rname}.spice\n'
run('rotated',script)
for dev in devices:
    if dev['cell'] in rotated:dev['cell']=rotated[dev['cell']]['name']
for name,cell in rotated.items():cells[('rotated',name)]=cell
byname={c['name']:c for c in cells.values()};nodes={};maxy=0
resistors=[d for d in devices if byname[d['cell']]['model']=='ppolyf_u_1k']
longs=[d for d in devices if d['cell'].endswith('_rot')]
pnps=[d for d in devices if byname[d['cell']]['model']=='pnp_05p00x00p42']
shorts=[d for d in devices if d not in resistors and d not in longs and d not in pnps]
preferred=[]
shorts.sort(key=lambda d:preferred.index(d['name']) if d['name'] in preferred else len(preferred)+devices.index(d))
def cw(d):b=byname[d['cell']]['bounds'];return b[2]-b[0]
def ch(d):b=byname[d['cell']]['bounds'];return b[3]-b[1]
leftbank=3+sum(cw(d)+2 for d in longs)
res_top=3+max(ch(d) for d in resistors)
aligned_top=max(res_top+2+max(ch(d) for d in shorts),3+max(ch(d) for d in longs))
placements={};edge=3
for group,start,top,metal in ((longs,3,aligned_top,'metal2'),(resistors,leftbank,res_top,'metal4'),(shorts,leftbank,aligned_top,'metal2')):
    cursor=start
    for dev in group:
        bb=byname[dev['cell']]['bounds'];x=cursor-bb[0];y=top-bb[3]
        placements[dev['name']]=(x,y,metal);cursor=x+bb[2]+2
    edge=max(edge,cursor)
ring=[(x,y) for y in range(3) for x in range(3) if (x,y)!=(1,1)]
for d in pnps:
    col,row=(1,1) if d['name']=='Xq1' else ring[int(d['name'].split('_')[-1])] if d['name'].startswith('Xq2_') else (0,3)
    bb=byname[d['cell']]['bounds']
    x=3-bb[0]+col*(bb[2]-bb[0]+2);y=3-bb[1]+row*(bb[3]-bb[1]+2)
    assert x+bb[2]<leftbank and y+bb[3]<aligned_top-max(ch(d) for d in longs)-2
    placements[d['name']]=(x,y,'metal4')
script='drc off\nlocking disable\ncrashbackups stop\nload PorMonitorAnalog\n'
for dev in devices:
    cell=byname[dev['cell']];bb=cell['bounds'];x,y,metal=placements[dev['name']]
    script+=f'getcell {cell["name"]} child 0 0 parent {x:.5f}um {y:.5f}um\nidentify {dev["name"]}\n'
    dev['origin']=[x,y]
    for pin,(net,point) in enumerate(zip(dev['nets'],cell['pins'].values())):
        px,py=x+point[0],y+point[1]
        if dev in pnps and pin==2 and dev['name'] in ('Xq1','Xq3'):
            # Separate emitter risers for the central unit and reference PNP;
            # repeated outer-unit/base/collector risers share their real nets.
            script+=land(px,py,'metal2','via2','metal3')+rect(px,py-.2,px+.8,py+.2,'metal3')
            px+=.8
        nodes.setdefault(net,[]).append((px,py,metal))
    maxy=max(maxy,y+bb[3])
width=edge+3.;channel0=maxy+3
for i,(net,pins) in enumerate(nodes.items()):
    y=channel0+i*.9
    left=1 if net in ports else min(x for x,py,m in pins)-.2
    right=max(x for x,py,m in pins)+.2
    script+=rect(left,y-.2,right,y+.2,'metal3')
    for x,py,metal in pins:
        script+=rect(x-.2,min(py,y),x+.2,max(py,y),metal)
        if metal=='metal2':script+=land(x,y,'metal2','via2','metal3')
        else:
            script+=land(x,py,'metal2','via2','metal3')+land(x,py,'metal3','via3','metal4')+land(x,y,'metal3','via3','metal4')
    if net in ports:
        script+=f'box values 1um {y-.2:.5f}um 2um {y+.2:.5f}um\nlabel {net} c metal3\nport make {ports.index(net)+1}\n'
script+='save PorMonitorAnalog\ndrc check\ndrc catchup\nputs "DRC_TOP [drc listall why]"\nextract all\next2spice lvs\next2spice -o extracted.spice\ngds write PorMonitorAnalog.gds\n'
run('route',script)
result={'status':'prototype_requires_checks','source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'script_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'cells':list(cells.values()),'devices':devices,'planned_bounds_um':[width,channel0+(len(nodes)-1)*.9+3]}
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['planned_bounds_um'])

evidence.finish()
