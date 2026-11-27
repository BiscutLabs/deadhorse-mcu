"""One bounded Quaigh attempt in its separately pinned offline container.

Host orchestrator only: all ATPG computation uses the authenticated executable.
Generated patterns are quarantined suggestions until physical fault replay.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[2]
TOOL='/work/build/t37/quaigh-result/bin/quaigh'
TOOL_SHA='e075ca76f5877b211b815412e656cfb067ea41f50cb3bc4152caaf03cac7611f'


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def execute(args,cap):
    # Preserve raw UTF-8/ANSI output; Windows' default cp1252 decoder can
    # otherwise discard the log after an expensive solver attempt.
    return subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=cap)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bench',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--container',default='deadhorse-t37-atpg')
    a=p.parse_args();out=a.output.resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    r=json.loads((a.bench/'result.json').read_text())
    if r['status']!='pass_pattern_suggestion_export_only':raise ValueError('Unqualified pattern model')
    for name,digest in r['artifacts'].items():
        if sha(a.bench/name)!=digest:raise ValueError('Changed model artifact')
    result=dict(status='error',cap_seconds=120,scope='Expanded capture-network suggestions only; no physical fault coverage',
        source_sha256=sha(__file__),inputs={str(q):sha(q) for q in (
            a.bench/'result.json',a.bench/'capture.bench',a.bench/'ports.json',ROOT/'tools/physical/atpg.lock.json')},
        tool_sha256=TOOL_SHA,commands=[])
    def run(args,cap=30):
        result['commands'].append(args)
        return execute(args,cap)
    try:
        tool=run(['docker','exec',a.container,'/root/.nix-profile/bin/sha256sum',TOOL])
        if tool.returncode or tool.stdout.split()[0].decode('ascii')!=TOOL_SHA:raise ValueError('Wrong ATPG executable')
        native='/work/'+out.relative_to(ROOT).as_posix()
        create=run(['docker','exec',a.container,'mkdir',native])
        if create.returncode:raise ValueError('Output already exists or cannot be created')
        copy=run(['docker','cp',str(a.bench/'capture.bench'),a.container+':'+native+'/capture.bench'])
        if copy.returncode:raise ValueError('Model copy failed')
        check=run(['docker','exec',a.container,'/root/.nix-profile/bin/sha256sum',native+'/capture.bench'])
        if check.returncode or check.stdout.split()[0].decode('ascii')!=sha(a.bench/'capture.bench'):raise ValueError('Model copy hash mismatch')
        command=['docker','exec',a.container,'/root/.nix-profile/bin/timeout','--signal=TERM','--kill-after=5','120',
            TOOL,'atpg',native+'/capture.bench','-o',native+'/patterns.test','--seed','37','--with-redundant-faults']
        # --num-random would select RANDOM-ONLY mode in this pinned release;
        # omit it to exercise combinational ATPG with SAT fallback.
        start=time.monotonic();job=run(command,150);result['seconds']=time.monotonic()-start
        result['returncode']=job.returncode;(out/'atpg.log').write_bytes(job.stdout)
        if job.returncode in (124,137):
            result['status']='unresolved_timeout'
        elif job.returncode:
            raise ValueError('ATPG failed; preserve log')
        else:
            copy=run(['docker','cp',a.container+':'+native+'/patterns.test',str(out/'patterns.test')])
            if copy.returncode:raise ValueError('Missing pattern file')
            result['patterns_sha256']=sha(out/'patterns.test')
            result['status']='suggestions_generated_unreplayed'
        print(result['status'],result['seconds'],'seconds')
    except Exception as error:
        result['error']=repr(error);raise
    finally:
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
