"""Host orchestration for the separately pinned physical companion environment."""
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]

if __name__=='__main__':
    lock=json.loads((Path(__file__).parent/'lock.json').read_text())
    if not sys.argv[1:]:sys.exit('Explicit command required; this runner never defaults to CI')
    if '@sha256:' not in lock['image']:sys.exit('Physical runtime must use an immutable image digest')
    command=sys.argv[1:]
    if command[0]=='openroad':command[0]=lock['openroad']
    sys.exit(subprocess.call(['docker','run','--rm','--user','0:0','--platform',lock['platform'],'--network','none',
        '--mount',f'type=bind,source={ROOT},target=/work','-w','/work','--entrypoint','',
        lock['image'],*command],cwd=ROOT))
