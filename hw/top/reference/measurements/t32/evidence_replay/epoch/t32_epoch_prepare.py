from pathlib import Path
import subprocess,json,hashlib
root=Path.cwd();out=root/'build/t32/epoch-lanes02';out.mkdir(parents=True,exist_ok=False)
base=root/'build/t32/epoch05'
lines=(base/'correct.sby').read_text().split('[script]\n')[1].split('[files]')[0].strip().splitlines()
sources=sorted((base/'emit/correct').glob('*.sv'))
lines[0]='read_slang --top DebugEpochFormal '+' '.join(map(str,sources))
idx=lines.index('clk2fflogic');lines=lines[:idx]+[f'write_json {out}/raw.json']
(out/'prepare.ys').write_text('\n'.join(lines)+'\n')
with(out/'prepare.log').open('w') as f:subprocess.run(['yosys','-Q','-T','-s',str(out/'prepare.ys')],stdout=f,stderr=subprocess.STDOUT,check=True)
m=json.loads((out/'raw.json').read_text())['modules']['DebugEpochFormal']
exp=m['netnames']['expected']['bits'];result=m['netnames']['d.result']['bits']
matches=[n for n,c in m['cells'].items() if c['type']=='$eq' and ((c['connections']['A']==exp and c['connections']['B']==result) or (c['connections']['A']==result and c['connections']['B']==exp))]
print(matches)
assert len(matches)==1
(out/'inputs.json').write_text(json.dumps(dict(eq=matches[0],raw_sha256=hashlib.sha256((out/'raw.json').read_bytes()).hexdigest(),source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}),indent=2)+'\n')
