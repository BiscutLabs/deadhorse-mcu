import json,subprocess,time
from pathlib import Path
out=Path('build/t32/area04');rows=[]
for name in ('map','partition','budget'):
    cmd=['python',f'scratch/t32_area04_{name}.py'];start=time.monotonic()
    with(out/(name+'.log')).open('w') as f:p=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
    rows.append(dict(command=cmd,returncode=p.returncode,seconds=time.monotonic()-start))
    (out/'run.json').write_text(json.dumps(rows,indent=2)+'\n');print(name,p.returncode,flush=True)
    if p.returncode:raise SystemExit(p.returncode)
