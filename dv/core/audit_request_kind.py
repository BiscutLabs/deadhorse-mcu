"""Authenticate active capture and real saved-request mutation witnesses."""
import argparse
import json
from pathlib import Path
from common import local
from jalr_invariant import digest
from jalr_receipts import verify_hashes


def witness(text,role):
    fields=('capture','requestKind','requestFirst');scope=[];names={};values={};found=[];time=0
    def sample():
        if any(n not in names or names[n] not in values for n in fields):return
        bits={n:values[names[n]] for n in fields}
        if any(set(v)-set('01') for v in bits.values()):return
        d={n:int(v,2) for n,v in bits.items()}
        expected={'capture-cover':(0,1),'kind-fault':(1,1),'first-fault':(0,0)}[role]
        if d['capture']==1 and (d['requestKind'],d['requestFirst'])==expected:
            found.append(dict(time=time,values=d))
    for line in text.splitlines():
        parts=line.split()
        if not parts:continue
        if parts[0]=='$scope':scope.append(parts[2])
        elif parts[0]=='$upscope':scope.pop()
        elif parts[0]=='$var':
            full='.'.join(scope+[parts[4]])
            for field in fields:
                if full=='rvfi_testbench.__phase_'+field:names[field]=parts[3]
        elif line.startswith('#'):sample();time=int(line[1:])
        elif line[0] in 'bB' and len(parts)==2:values[parts[1]]=parts[0][1:]
        elif line[0] in '01xXzZ':values[line[1:]]=line[0]
    sample()
    if not found:raise ValueError('No exact active saved-request witness: '+role)
    return found[0]


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',required=True)
    args=ap.parse_args();out=local(args.output);raw=out/'result.json';evidence=json.loads(raw.read_text())
    receipt=dict(status='running',scope='kind/first alignment only; arithmetic/ISA unresolved')
    try:
        if evidence['status']!='composition proved; active witness audit and independent review pending':
            raise ValueError('Incomplete kind/first composition')
        protected={**evidence['input_sha256'],str(raw):digest(raw),str(Path(__file__)):digest(Path(__file__))}
        verify_hashes(protected)
        events={}
        for role in ('capture-cover','kind-fault','first-fault'):
            expected='PASS' if role=='capture-cover' else 'FAIL'
            if evidence['results'][role]['status']!=expected or (out/role/'work/status').read_text().split()[0]!=expected:
                raise ValueError('Role status mismatch')
            events[role]=[]
            for w in evidence['results'][role]['witnesses']:
                p=local(w['path'])
                if digest(p)!=w['sha256']:raise ValueError('Witness bytes changed')
                events[role].append(witness(p.read_text(),role))
            if not events[role]:raise ValueError('Missing active witness')
        receipt.update(status='pass',events=events,input_sha256=protected)
        print('PASS saved kind/first composition audit: active cover and exact real-driver faults')
    except BaseException as exc:
        receipt.update(status='failed',error=str(exc));raise
    finally:(out/'audit.json').write_text(json.dumps(receipt,indent=2)+'\n')


if __name__=='__main__':main()
