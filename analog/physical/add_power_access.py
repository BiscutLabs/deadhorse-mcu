from pathlib import Path
import pya,re,subprocess,os,json
import argparse,hashlib
from common import Evidence
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--lf',required=True);p.add_argument('--por',required=True);p.add_argument('--tech',required=True);p.add_argument('--output',required=True);p.add_argument('--pdk',default='build/t43/pdk-candidate/gf180mcuD');a=p.parse_args()
root=Path(__file__).resolve().parents[2];out=(root/a.output).resolve();out.relative_to(root/'build');out.mkdir(parents=True,exist_ok=False)
pdk=(root/a.pdk).resolve();pdk.relative_to(root/'build');tech=(root/a.tech).resolve();tech.relative_to(root/'build')
evidence=Evidence(out,__file__,pdk)
evidence.add_inputs([tech])
lock=json.loads((root/'analog/physical/inputs.lock.json').read_text());assert hashlib.sha256(tech.read_bytes()).hexdigest()==lock['patched_tech_sha256'];results=[]
for source,top in [(a.lf,'LfRcMacro'),(a.por,'PorBrownoutMacro')]:
 src=(root/source).resolve();src.relative_to(root/'build');evidence.add_inputs([src/(top+'.gds'),src/(top+'.mag')]);d=out/top;d.mkdir();lay=pya.Layout();lay.read(str(src/(top+'.gds')));cell=lay.cell(top);bbox=cell.dbbox();cell.name=top+'Body';lay.write(str(d/'body.gds'))
 mag=(src/(top+'.mag')).read_text();m=re.search(r'magscale (\d+) (\d+)',mag);u=.05*int(m[1])/int(m[2]);ports=[]
 for m in re.finditer(r'^rlabel (metal\d) (?:s )?(-?\d+) (-?\d+) (-?\d+) (-?\d+) \d+ (\S+)\nport (\d+) ',mag,re.M):ports.append(dict(layer=m[1],box=[int(m[j])*u for j in range(2,6)],name=m[6],index=int(m[7])))
 def rect(x0,y0,x1,y1,l):return f'box values {x0:.5f}um {y0:.5f}um {x1:.5f}um {y1:.5f}um\npaint {l}\n'
 def via(x,y,lo,v,hi):return rect(x-.22,y-.22,x+.22,y+.22,lo)+rect(x-.14,y-.14,x+.14,y+.14,v)+rect(x-.22,y-.22,x+.22,y+.22,hi)
 s=f'gds readonly true\ndrc off\ntech load {tech}\ngds read {d}/body.gds\nload {top}\ngetcell {top}Body child 0 0 parent 0 0\nidentify body\n';rails={}
 metal=pya.Region(cell.begin_shapes_rec(lay.layer(46,0)))
 for i,name in enumerate(('vdd','vss')):
  p=next(p for p in ports if p['name']==name);x=5+i*3;y=(p['box'][1]+p['box'][3])/2;ry=bbox.bottom-10-i*4
  q=pya.DBox(x-.2,y-.2,x+.2,y+.2).to_itype(lay.dbu);assert (pya.Region(q)-metal).is_empty(),(top,name)
  s+=via(x,y,'metal3','via3','metal4')+rect(x-.22,ry,x+.22,y,'metal3')+via(x,ry,'metal3','via3','metal4')+via(x,ry,'metal4','via4','metal5')
  rb=[bbox.left,ry-1,bbox.right,ry+1];s+=rect(*rb,'metal5');rails[name]=rb
 for p in ports:
  x0,y0,x1,y1=p['box'];s+=rect(x0,y0,x1,y1,p['layer']);s+=f'box values {x0:.5f}um {y0:.5f}um {x1:.5f}um {y1:.5f}um\nlabel {{{p["name"]}}} c {p["layer"]}\nport make {p["index"]}\n'
 s+=f'save {top}\ngds write {top}.gds\nflatten -dotoplabels {top}Flat\nload {top}Flat\nextract all\next2spice lvs\next2spice -o extracted.spice\nquit -noprompt\n';(d/'access.tcl').write_text(s)
 with (d/'access.log').open('w') as f:r=subprocess.run([str(evidence.magic),'-dnull','-noconsole','-rcfile',str(pdk/'libs.tech/magic/gf180mcuD.magicrc'),'access.tcl'],cwd=d,env={**os.environ,'PDK_ROOT':str(pdk.parent)},stdout=f,stderr=subprocess.STDOUT,timeout=60)
 assert r.returncode==0
 (d/'ports.json').write_text(json.dumps({'ports':ports,'rails':rails,'source':str(src)},indent=2)+'\n');results.append(dict(top=top,rails=rails))
print(json.dumps(results,indent=2))


evidence.finish()
