"""Bounded, checkpointed Quaigh portfolio over exact capture cones.

Host orchestration only. A single120-second solver portfolio replaces the
timed-out monolithic attempt; every unfinished cone remains unresolved.
"""
import argparse
import json
from pathlib import Path
import subprocess
import shlex
import tarfile
import time

from scan_patterns import TOOL, TOOL_SHA, ROOT, sha, execute


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cones',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--continue-from',type=Path,help='One native batch of only previously unattempted cones; no repeated timed-out job')
    a=p.parse_args();out=a.output.resolve();out.relative_to(ROOT/'build');out.mkdir(exist_ok=False)
    model=json.loads((a.cones/'result.json').read_text())
    if model['status']!='exact_output_partition':raise ValueError('Wrong partition')
    for row in model['cones']:
        for name,d in row['files'].items():
            if sha(a.cones/row['name']/name)!=d:raise ValueError('Stale cone')
    result=dict(status='error',cap_seconds=120,source_sha256=sha(__file__),
        inputs={str(a.cones/'result.json'):sha(a.cones/'result.json'),str(ROOT/'tools/physical/atpg.lock.json'):sha(ROOT/'tools/physical/atpg.lock.json')},
        tool_sha256=TOOL_SHA,commands=[],cones=[])
    def run(cmd,cap=30):result['commands'].append(cmd);return execute(cmd,cap)
    container='deadhorse-t37-atpg';native='/work/'+out.relative_to(ROOT).as_posix()
    try:
        r=run(['docker','exec',container,'/root/.nix-profile/bin/sha256sum',TOOL])
        if r.returncode or r.stdout.split()[0].decode()!=TOOL_SHA:raise ValueError('Wrong ATPG tool')
        if a.continue_from:
            previous=json.loads((a.continue_from/'result.json').read_text())
            if previous['status']!='bounded_suggestions_only' or previous['inputs'].get(str(a.cones/'result.json'))!=sha(a.cones/'result.json'):
                raise ValueError('Wrong earlier partition attempt')
            remaining={r['name'] for r in previous['cones'] if r['status']=='unresolved_not_attempted'}
            source='/work/'+a.continue_from.resolve().relative_to(ROOT).as_posix()
            result['inputs'][str(a.continue_from/'result.json')]=sha(a.continue_from/'result.json')
            lines=['#!/bin/bash','set -eu', 'cd '+shlex.quote(native)]
            for row in model['cones']:
                if row['name'] not in remaining:continue
                path=source+'/'+row['name']+'/capture.bench'
                lines.extend(['printf "%s  %s\\n" '+shlex.quote(row['files']['capture.bench'])+' '+shlex.quote(path)+' | /root/.nix-profile/bin/sha256sum -c - >/dev/null',
                    'mkdir '+row['name'],
                    shlex.quote(TOOL)+' atpg '+shlex.quote(path)+' -o '+row['name']+'/patterns.test --seed 37 --with-redundant-faults >'+row['name']+'/atpg.log 2>&1',
                    'printf "0\\n" > '+row['name']+'/rc'])
            (out/'jobs.sh').write_bytes(('\n'.join(lines)+'\n').encode('utf-8'))
            result['jobs_sha256']=sha(out/'jobs.sh')
            if run(['docker','exec',container,'mkdir',native]).returncode:raise ValueError('Native output exists')
            if run(['docker','cp',str(out/'jobs.sh'),container+':'+native+'/jobs.sh']).returncode:raise ValueError('Job transfer failed')
            start=time.monotonic()
            job=run(['docker','exec',container,'/root/.nix-profile/bin/timeout','--signal=TERM','--kill-after=5','120','bash',native+'/jobs.sh'],135)
            result['seconds']=time.monotonic()-start;result['returncode']=job.returncode;(out/'portfolio.log').write_bytes(job.stdout)
            if job.returncode not in (0,124,137):raise ValueError('Native portfolio tool error')
            archive=native+'.tar'
            if run(['docker','exec',container,'tar','-cf',archive,'-C',native,'.'],60).returncode:raise ValueError('Pattern archive failed')
            if run(['docker','cp',container+':'+archive,str(out/'results.tar')],60).returncode:raise ValueError('Pattern copy failed')
            with tarfile.open(out/'results.tar') as stream:stream.extractall(out/'native',filter='data')
            for row in model['cones']:
                name=row['name'];directory=out/'native'/name
                if name not in remaining:status='previously_attempted'
                elif (directory/'rc').exists():status='suggestions_generated'
                elif directory.exists():status='unresolved_timeout'
                else:status='unresolved_not_attempted'
                record=dict(name=name,status=status)
                if status=='suggestions_generated':record.update(patterns_sha256=sha(directory/'patterns.test'),directory='native/'+name)
                result['cones'].append(record)
            result['status']='bounded_suggestions_only';print('native portfolio',result['seconds'],'seconds');return
        r=run(['docker','cp',str(a.cones.resolve()),container+':'+native],120)
        if r.returncode:raise ValueError('Cone transfer failed')
        start=time.monotonic()
        for row in model['cones']:
            left=120-(time.monotonic()-start)
            if left<=1:
                result['cones'].append(dict(name=row['name'],status='unresolved_not_attempted'));continue
            directory=out/row['name'];directory.mkdir();path=native+'/'+row['name']
            check=run(['docker','exec',container,'/root/.nix-profile/bin/sha256sum',path+'/capture.bench'])
            if check.returncode or check.stdout.split()[0].decode()!=row['files']['capture.bench']:raise ValueError('Copied cone differs')
            cmd=['docker','exec',container,'/root/.nix-profile/bin/timeout','--signal=TERM','--kill-after=5',str(max(0.1,120-(time.monotonic()-start))),
                TOOL,'atpg',path+'/capture.bench','-o',path+'/patterns.test','--seed','37','--with-redundant-faults']
            then=time.monotonic();job=run(cmd,135);(directory/'atpg.log').write_bytes(job.stdout)
            status='suggestions_generated' if job.returncode==0 else 'unresolved_timeout' if job.returncode in (124,137) else 'tool_error'
            record=dict(name=row['name'],status=status,returncode=job.returncode,seconds=time.monotonic()-then)
            if job.returncode==0:
                copied=run(['docker','cp',container+':'+path+'/patterns.test',str(directory/'patterns.test')])
                if copied.returncode:raise ValueError('Missing patterns')
                record['patterns_sha256']=sha(directory/'patterns.test')
            result['cones'].append(record)
            print(row['name'],status,flush=True)
            if status=='tool_error':raise ValueError('Quaigh error; preserve output')
        result.update(status='bounded_suggestions_only',seconds=time.monotonic()-start)
    finally:
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
