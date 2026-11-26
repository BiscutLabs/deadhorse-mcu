"""Generate the D111 LF candidate from pinned RISCay topology and PDK devices.

Experimental until the recorded electrical and physical checks close.
Generated circuit/layout outputs stay under build/. See README and NOTICE.
"""
import pathlib,re,subprocess,json,os,hashlib,time
import argparse,sys
from common import Evidence
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',required=True)
parser.add_argument('--pdk',default='build/t43/pdk-candidate/gf180mcuD')
parser.add_argument('--reference',default='build/riscay-mcu')
parser.add_argument('--role',choices=('lf','por-timebase'),default='lf')
args=parser.parse_args()
root=pathlib.Path(__file__).resolve().parents[2]
out=(root/args.output).resolve();out.relative_to(root/'build');out.mkdir(parents=True,exist_ok=False)
pdk=(root/args.pdk).resolve();pdk.relative_to(root/'build')
lock=json.loads((root/'analog/physical/inputs.lock.json').read_text())
magic=lock['magic_store_path']+'/bin/magic'
assert hashlib.sha256(pathlib.Path(magic).read_bytes()).hexdigest()==lock['magic_executable_sha256']
evidence=Evidence(out,__file__,pdk)
source=(root/args.reference/'analog/gf180-lf-osc/design.py').resolve()
source.relative_to(root/'build')
revision='4671317186003740ceb61360ba08c59bbdf10136'
assert lock['riscay_source']['revision']==revision
assert hashlib.sha256(source.read_bytes()).hexdigest()==lock['riscay_source']['files']['analog/gf180-lf-osc/design.py']
evidence.add_inputs([source])
sys.path.insert(0,str(source.parent))
from design import Design,netlist
original=netlist(Design(resistor_megohm=1,buffer_stack=2,stages=3,timing_gate_length_um=10.0))
original=original.replace('nmos_3p3','nfet_03v3').replace('pmos_3p3','pfet_03v3').replace('ppolyf_u_3k','ppolyf_u_1k')
original=re.sub(r'r_length=([0-9.]+)u',lambda m:f'r_length={float(m[1])*3:g}u',original)
circuit=original.replace('riscay_lf_osc_gf180','LfRcAnalog').replace('rst_n','enable').replace(' clk',' clock')
circuit=circuit.replace('.subckt LfRcAnalog vdd vss enable clock','.subckt LfRcAnalog vdd vss enable clock power_n')
ports=('vdd','vss','enable','clock','power_n')
circuit=re.sub(r'^XR\d+ .+\n','',circuit,flags=re.M)
circuit=re.sub(r'^XSTART\d+ .+\n','',circuit,flags=re.M)
# Preserve the nominal DC resistance including the removed end-contact terms.
# Source model: R = (rho*L + 2*contact*W)/(W-dW), rho=1000, contact=85.45.
bias_length=(10*95.436+18*85.45/1000)*(.58 if args.role=='lf' else .70)
startup_width=.22 if args.role=='lf' else .44
resistors=f'XRbias rtop vss vss ppolyf_u_1k r_width=1u r_length={bias_length:.6f}u\n'
for i in range(4):
    d='start_control' if i==0 else f'start_p{i}'
    src='vdd' if i==3 else f'start_p{i+1}'
    resistors+=f'Xstart_p{i} {d} vss {src} vdd pfet_03v3 w={startup_width:g}u l=50u\n'
resistors+='Xstart_sense start_control nbias vss vss nfet_03v3 w=4u l=0.28u\n'
resistors+='Xstart_kick pbias start_control vss vss nfet_03v3 w=0.22u l=10u\n'
resistors+='Xinitp power_n start_control vdd vdd pfet_03v3 w=1u l=.28u\n'
resistors+='Xinitn power_n start_control vss vss nfet_03v3 w=.5u l=.28u\n'
circuit=circuit.replace('.ends LfRcAnalog',resistors+'.ends LfRcAnalog')
circuit=re.sub(r'^(Xtiming[0-2] .*) l=10u ',r'\1 l=.55u ',circuit,flags=re.M)
if args.role=='lf':
    circuit,n=re.subn(r'^Xtiming(\d) vss (r\d) vss vss nfet_03v3.*$',r'Xtiming\1 \2 vss cap_mim_2f0_m4m5_noshield c_width=5u c_length=5u',circuit,flags=re.M)
    assert n==3
# Historical reset-assistance comments do not describe this experiment.
circuit='\n'.join(l for l in circuit.splitlines() if not l.startswith('*'))+'\n'
(out/'reference.spice').write_text(circuit)
devices=[];cells={}
for line in circuit.splitlines():
    if not line.startswith('X'):continue
    tokens=line.split();model=next(v for v in tokens if v in ('nfet_03v3','pfet_03v3','ppolyf_u_1k','cap_mim_2f0_m4m5_noshield'))
    pos=tokens.index(model);nets=tokens[1:pos]
    params={k:float(v[:-1]) for k,v in re.findall(r'(w|l|r_width|r_length|c_width|c_length)=([\d.]+u)',line)}
    key=(model,tuple(sorted(params.items())))
    if key not in cells:cells[key]={'name':f'dev{len(cells)}','model':model,'parameters':params}
    devices.append({'name':tokens[0],'nets':nets,'cell':cells[key]['name']})
def run(name,script):
    path=out/(name+'.tcl');path.write_text('if {[catch {\n'+script+'\n} message options]} {puts stderr $message;puts stderr [dict get $options -errorinfo];exit 1}\nquit -noprompt\n')
    start=time.monotonic()
    with (out/(name+'.log')).open('w') as log:
        p=subprocess.run([magic,'-dnull','-noconsole','-rcfile',str(pdk/'libs.tech/magic/gf180mcuD.magicrc'),str(path)],cwd=out,env={**os.environ,'PDK_ROOT':str(pdk.parent)},stdout=log,stderr=subprocess.STDOUT,timeout=120)
    assert p.returncode==0,(name,p.returncode)
    print(name,time.monotonic()-start)
script='drc off\nlocking disable\ncrashbackups stop\n'
for cell in cells.values():
    model=cell['model'];p=cell['parameters']
    draw_model=model
    if model=='cap_mim_2f0_m4m5_noshield':
        draw_model='cap_mim_2p0fF';overrides=dict(w=p['c_width'],l=p['c_length'])
    elif model=='ppolyf_u_1k':
        nf=50 if p['r_length']>4000 else 30
        # PDK serpentine extraction: nf*drawn_length - .6*(nf-1) + .44.
        length=round(((p['r_length']+.6*(nf-1)-.44)/nf)/.005)*.005
        overrides=dict(w=p['r_width'],l=length,nx=nf,snake=1,guard=1)
    else:overrides={**p,'guard':1,'diff_gate_space':.5,'diff_spacing':.6,'gate_to_diffcont':.7}
    cell['draw_parameters']=overrides
    script+=f'load {cell["name"]}\nbox values 0 0 0 0\nset p [dict merge [gf180mcu::{draw_model}_defaults] {{{" ".join(f"{k} {v:g}" for k,v in overrides.items())}}}]\nset p [gf180mcu::{draw_model}_check $p]\ngf180mcu::{draw_model}_draw $p\nsave {cell["name"]}\n'
run('draw',script)
def rect(x0,y0,x1,y1,layer):return f'box values {x0:.5f}um {y0:.5f}um {x1:.5f}um {y1:.5f}um\npaint {layer}\n'
def land(x,y,lower,via,upper):
    radius=.14 if via in ('via2','via3','via4') else .13
    lo=.22 if lower=='metal5' else .2;hi=.22 if upper=='metal5' else .2
    return rect(x-lo,y-lo,x+lo,y+lo,lower)+rect(x-radius,y-radius,x+radius,y+radius,via)+rect(x-hi,y-hi,x+hi,y+hi,upper)
script='drc off\nlocking disable\ncrashbackups stop\n'
for cell in cells.values():
    name=cell['name'];model=cell['model'];layers={};layer=None
    for line in (out/(name+'.mag')).read_text().splitlines():
        if line.startswith('<< '):layer=line[3:-3];layers.setdefault(layer,[])
        elif line.startswith('rect ') and layer!='checkpaint':layers[layer].append(tuple(int(x)*.005 for x in line.split()[1:]))
    allrects=[r for rr in layers.values() for r in rr]
    cell['bounds']=[min(r[0] for r in allrects),min(r[1] for r in allrects),max(r[2] for r in allrects),max(r[3] for r in allrects)]
    def centers(layer):return [((r[0]+r[2])/2,(r[1]+r[3])/2) for r in layers[layer]]
    if model=='cap_mim_2f0_m4m5_noshield':
        assert len(centers('mimcapcontact'))==1 and len(centers('via4'))==1
        pins={'A':(-6.,0.),'Z':(6.,0.)};script+=f'load {name}\n'
        for i,((pin,(ex,ey)),(x,y)) in enumerate(zip(pins.items(),[centers('mimcapcontact')[0],centers('via4')[0]]),1):
            assert y==ey
            script+=rect(min(x,ex),y-.22,max(x,ex),y+.22,'metal5')
            script+=land(ex,y,'metal4','via4','metal5')+land(ex,y,'metal3','via3','metal4')+land(ex,y,'metal2','via2','metal3')
            script+=f'label {pin} c metal2\nport make {i}\n'
        cell['pins']=pins;cell['bounds'][0]=-6.22;cell['bounds'][2]=6.22
        script+=f'property FIXED_BBOX\nsave {name}\nextract all\next2spice lvs\next2spice -o {name}.spice\n'
        continue
    if model=='ppolyf_u_1k':
        contacts=sorted(centers('polycontact'));pins={'A':contacts[0],'Z':contacts[-1],'B':min(centers('psubdiffcont'))}
    else:
        contacts=sorted(centers('pdiffc' if model.startswith('p') else 'ndiffc'))
        pins={'D':contacts[-1],'G':max(centers('polycontact'),key=lambda q:q[1]),'S':contacts[0],'B':min(centers('nsubdiffcont' if model.startswith('p') else 'psubdiffcont'))}
    cell['pins']=pins;script+=f'load {name}\n'
    for x,y in centers('polycontact'):
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
    if cell['model'] in ('ppolyf_u_1k','cap_mim_2f0_m4m5_noshield') or cell['parameters']['l']<20:continue
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
shorts=[d for d in devices if d not in resistors and d not in longs]
preferred=['Xmidp','Xmidn','Xgatep1','Xgatep2','Xgaten1','Xgaten2','Xoutp','Xoutn']
preferred += [f'X{n}{i}' for i in range(3) for n in ('ps','p','n','ns','timing')]
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
script='drc off\nlocking disable\ncrashbackups stop\nload LfRcAnalog\n'
for dev in devices:
    cell=byname[dev['cell']];bb=cell['bounds'];x,y,metal=placements[dev['name']]
    script+=f'getcell {cell["name"]} child 0 0 parent {x:.5f}um {y:.5f}um\nidentify {dev["name"]}\n'
    dev['origin']=[x,y]
    for net,point in zip(dev['nets'],cell['pins'].values()):nodes.setdefault(net,[]).append((x+point[0],y+point[1],metal))
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
script+='save LfRcAnalog\ndrc check\ndrc catchup\nputs "DRC_TOP [drc listall why]"\nextract all\next2spice lvs\next2spice -o extracted.spice\ngds write LfRcAnalog.gds\n'
run('route',script)
result={'status':'prototype_requires_checks','source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'script_sha256':hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),'cells':list(cells.values()),'devices':devices,'planned_bounds_um':[width,channel0+(len(nodes)-1)*.9+3]}
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(result['planned_bounds_um'])



evidence.finish()
