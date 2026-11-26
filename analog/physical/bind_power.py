"""Exploratory explicit common-supply binding; no signal-net rewrites."""
from pathlib import Path
import odb,json,hashlib
import argparse
from common import Evidence
p=argparse.ArgumentParser(description=__doc__)
for name in ('state','abstracts','output'):p.add_argument('--'+name,required=True)
a=p.parse_args();r=Path(__file__).resolve().parents[2]
out=(r/a.output).resolve();out.relative_to(r/'build');out.mkdir(parents=True,exist_ok=False)
state_path=(r/a.state).resolve();state_path.relative_to(r/'build');abstracts=(r/a.abstracts).resolve();abstracts.relative_to(r/'build')
state=json.loads(state_path.read_text());original=Path(state['odb'])
evidence=Evidence(out,__file__);evidence.add_inputs([state_path,original,*abstracts.glob('*.lef')])
db=odb.dbDatabase.create();odb.read_db(db,str(original));b=db.getChip().getBlock()
def validate(pin,supply,kind):
 old=b.findNet('i_chip_core.'+supply);assert old
 assert not old.getBTerms()
 expected={('i_chip_core.soc.lf',pin),('i_chip_core.soc.por',pin)}
 assert {(t.getInst().getName(),t.getMTerm().getName()) for t in old.getITerms()}==expected
 assert all(str(t.getMTerm().getSigType())==kind for t in old.getITerms())
 return old
import re
unit=b.getDbUnitsPerMicron()
for top in ('LfRcMacro','PorBrownoutMacro'):
 text=(abstracts/f'{top}.lef').read_text().split(' OBS\n')[1];expected=[]
 for layer,body in re.findall(r'  LAYER (Metal\d) ;\n(.*?)(?=  LAYER| END)',text,re.S):
  for rect in re.findall(r'RECT ([\d.]+) ([\d.]+) ([\d.]+) ([\d.]+)',body):expected.append((layer,*[round(float(v)*unit) for v in rect]))
 master=next(i.getMaster() for i in b.getInsts() if i.getMaster().getName()==top)
 actual=[(q.getTechLayer().getName(),q.xMin(),q.yMin(),q.xMax(),q.yMax()) for q in master.getObstructions()]
 assert sorted(expected)==sorted(actual),(top,'master obstruction mismatch')
rows=[]
for pin,supply,kind in [('vdd','VDD','POWER'),('vss','VSS','GROUND')]:
 old=validate(pin,supply,kind)
 # A signal consumer on the proposed supply alias must fail closed.
 fault=b.findInst('i_chip_core.soc.lf').findITerm('clock');saved=fault.getNet();fault.connect(old)
 try:validate(pin,supply,kind)
 except AssertionError:pass
 else:raise AssertionError('Signal consumer negative escaped')
 fault.connect(saved)
 target=b.findNet(supply)
 if target:
  assert str(target.getSigType())==kind,(supply,'conflicting supply type')
  assert all(str(t.getMTerm().getSigType())==kind for t in target.getITerms()),(supply,'signal consumer on destination')
  assert all(str(t.getSigType())==kind for t in target.getBTerms()),(supply,'signal boundary on destination')
 else:
  target=odb.dbNet.create(b,supply);target.setSigType(kind)
 moved=[]
 for t in list(old.getITerms()):moved.append(t.getInst().getName()+'/'+pin);t.connect(target)
 assert not old.getITerms();odb.dbNet.destroy(old)
 rows.append({'source':'i_chip_core.'+supply,'target':supply,'pins':moved,'negative_control':'signal consumer rejected'})
odb.write_db(db,str(out/'chip_top.odb'));odb.write_def(b,str(out/'chip_top.def'))
state.update(odb=str(out/'chip_top.odb'),**{'def':str(out/'chip_top.def')})
(out/'state.json').write_text(json.dumps(state,indent=2)+'\n')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
(out/'result.json').write_text(json.dumps({'status':'explicit_power_alias_binding','scope':'Exploratory physical geometry; not analog electrical acceptance','connections':rows,'inputs':{str(original):sha(original),str(state_path):sha(state_path),str(Path(__file__)):sha(Path(__file__)),**{str(q):sha(q) for q in abstracts.glob('*.lef')}},'artifacts':{p.name:sha(p) for p in out.iterdir()}},indent=2)+'\n')
print('PASS four analog PG pins bound to approved common supplies; both signal-consumer faults rejected')

evidence.finish("explicit_power_alias_binding")
