from pathlib import Path
import pya,re,json,hashlib
import argparse
from common import Evidence
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--access',required=True);p.add_argument('--interfaces',required=True);p.add_argument('--output',required=True);a=p.parse_args()
root=Path(__file__).resolve().parents[2];out=(root/a.output).resolve();out.relative_to(root/'build');out.mkdir(parents=True,exist_ok=False)
access=(root/a.access).resolve();access.relative_to(root/'build');interface_path=(root/a.interfaces).resolve();interface_path.relative_to(root/'build')
evidence=Evidence(out,__file__)
evidence.add_inputs([interface_path])
interfaces=json.loads(interface_path.read_text())['modules']
result=[]
for top in ('LfRcMacro','PorBrownoutMacro'):
 src=access/top;evidence.add_inputs([src/'ports.json',src/(top+'.gds')]);ports=json.loads((src/'ports.json').read_text());lay=pya.Layout();lay.read(str(src/(top+'.gds')));cell=lay.cell(top);bbox=cell.bbox();dx=-bbox.left;dy=-bbox.bottom;u=lay.dbu
 # A pure translation changes no physical geometry or connectivity.
 original=pya.Layout();original.read(str(src/(top+'.gds')));oldcell=original.cell(top)
 before={i:pya.Region(oldcell.begin_shapes_rec(original.layer(lay.get_info(i)))) for i in lay.layer_indexes() if lay.get_info(i).datatype!=10 and (lay.get_info(i).layer,lay.get_info(i).datatype)!=(63,63)}
 cell.transform(pya.Trans(dx,dy));assert cell.bbox().left==0 and cell.bbox().bottom==0
 for i,r in before.items():
  delta=r.transformed(pya.Trans(pya.Point(dx,dy))) ^ pya.Region(cell.begin_shapes_rec(i))
  if not delta.is_empty():print('XORFAIL',top,lay.get_info(i),delta.area(),delta.bbox(),dx,dy,flush=True)
  assert delta.is_empty(),(top,i)
 lay.write(str(out/(top+'.gds')));w=cell.bbox().width()*u;h=cell.bbox().height()*u
 lef=f'VERSION 5.7 ;\nBUSBITCHARS "[]" ;\nDIVIDERCHAR "/" ;\nMACRO {top}\n CLASS BLOCK ;\n ORIGIN 0 0 ;\n SIZE {w:.5f} BY {h:.5f} ;\n';pins=[];expected={}
 for name,p in interfaces[top]['ports'].items():
  for n in ([name] if len(p['bits'])==1 else [f'{name}[{i}]' for i in range(len(p['bits']))]):expected[n]=p['direction'].upper()
 names=[p['name'] for p in ports['ports']]
 assert len(names)==len(set(names)),(top,'duplicate physical port name')
 assert set(expected)==set(names)
 for p in ports['ports']:
  name=p['name'];power=name in ('vdd','vss');layer='Metal5' if power else p['layer'].capitalize();box=ports['rails'][name] if power else p['box'];x0,y0,x1,y1=box;rect=pya.DBox(x0+dx*u,y0+dy*u,x1+dx*u,y1+dy*u).to_itype(u);li=lay.layer({'Metal4':46,'Metal5':81}[layer],0)
  assert (pya.Region(rect)-pya.Region(cell.begin_shapes_rec(li))).is_empty(),(top,name)
  direction=expected[name];use='POWER' if name=='vdd' else 'GROUND' if name=='vss' else 'SIGNAL';b=[rect.left*u,rect.bottom*u,rect.right*u,rect.top*u]
  lef+=f' PIN {name}\n  DIRECTION {direction} ;\n  USE {use} ;\n  PORT\n   LAYER {layer} ;\n   RECT '+ ' '.join(f'{v:.5f}' for v in b)+f' ;\n  END\n END {name}\n';pins.append((layer,rect))
 # Clearing the full lower Metal4 band is legal only when that band
 # contains the two known supply landings and no signal/foreign metal.
 # Check the actual flattened GDS, not a presumed placement clearance.
 metal4=pya.Region(cell.begin_shapes_rec(lay.layer(46,0)))
 expected_landings=pya.Region()
 for j,name in enumerate(('vdd','vss')):
  x0,y0,x1,y1=ports['rails'][name]
  x=5+3*j+dx*u;y=(y0+y1)/2+dy*u
  expected_landings+=pya.Region(pya.DBox(x-.22,y-.22,x+.22,y+.22).to_itype(u))
 limit=max(rect.top for pl,rect in pins if pl=='Metal5')+round(.28/u)
 band=pya.Region(pya.Box(0,0,cell.bbox().right,limit))
 assert ((metal4 & band)-expected_landings).is_empty(),(top,'foreign Metal4 in lower power-access band')
 assert (expected_landings-metal4).is_empty(),(top,'missing power-access landing')
 lef+=' OBS\n'
 for layer in ('Metal1','Metal2','Metal3','Metal4','Metal5'):
  obs=pya.Region(pya.Box(0,0,cell.bbox().right,cell.bbox().top))
  for pl,r in pins:
   if pl==layer or (pl=='Metal5' and layer=='Metal4'):obs-=pya.Region(r.enlarged(round(.28/u)))
  if layer=='Metal4':
   limit=max(rect.top for pl,rect in pins if pl=='Metal5')+round(.28/u)
   obs-=pya.Region(pya.Box(0,0,cell.bbox().right,limit))
  lef+=f'  LAYER {layer} ;\n'
  for poly in obs.decompose_trapezoids_to_region().each():
   assert poly.is_box();r=poly.bbox();lef+='   RECT '+' '.join(f'{v*u:.5f}' for v in (r.left,r.bottom,r.right,r.top))+' ;\n'
 lef+=f' END\nEND {top}\nEND LIBRARY\n';(out/(top+'.lef')).write_text(lef)
 declaration='(* blackbox *) module '+top+'('+', '.join(interfaces[top]['ports'])+');\n'
 for name,p in interfaces[top]['ports'].items():declaration+=' '+p['direction']+' wire '+(f'[{len(p["bits"])-1}:0] ' if len(p['bits'])>1 else '')+name+';\n'
 (out/(top+'.v')).write_text(declaration+'endmodule\n')
 result.append(dict(top=top,width_um=w,height_um=h,footprint_mm2=w*h/1e6,translation_dbu=[dx,dy],source_sha256=hashlib.sha256((src/(top+'.gds')).read_bytes()).hexdigest(),scope='Provisional layout-derived geometry only; analog qualification open'))
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))




evidence.finish()
