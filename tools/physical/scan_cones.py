"""Exact output-cone partition of the existing qualified ATPG network.

Every output is assigned exactly once; shared state/pad inputs keep their
original identities. A cone result is only a pattern suggestion, never a
physical fault coverage result.
"""
import argparse
import json
from pathlib import Path
import time

from scan_bench import Network
from scan_faults import load
from scan_capture import sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('capture','insert','manifest','core','liberty','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    m=load(a);m.verify_entry();n=Network(m);outputs=n.outputs();n.crosscheck(outputs)
    chunks=[];current=[];used=set()
    for output in outputs:
        support=n.used([output])
        # Keep related large cones together instead of duplicating their
        # common logic once per output. This changes partitioning only.
        if current and ((len(used|support)>2048 and len(support-used)>256) or len(current)>=128):
            chunks.append((current,used));current=[];used=set()
        current.append(output);used.update(support)
    if current:chunks.append((current,used))
    chunks.sort(key=lambda item:len(item[1]))
    rows=[]
    for i,(observed,support) in enumerate(chunks):
        directory=a.output/f'cone{i:04d}';directory.mkdir()
        inputs=[r for r in n.inputs if r['node'] in support]
        lines=[f'INPUT(n{r["node"]})' for r in inputs]
        for j,row in enumerate(observed):lines.extend([f'OUTPUT(q{j})',f'q{j} = BUF(n{row["node"]})'])
        for node in sorted(support):
            kind,args=n.nodes[node]
            if kind!='INPUT':lines.append(f'n{node} = {kind}('+', '.join('n'+str(i) for i in args)+')')
        (directory/'capture.bench').write_text('\n'.join(lines)+'\n')
        (directory/'ports.json').write_text(json.dumps(dict(inputs=inputs,outputs=observed)))
        rows.append(dict(name=directory.name,inputs=len(inputs),outputs=len(observed),nodes=len(support),
            files={q.name:sha(q) for q in directory.iterdir()}))
    if sorted(o['cell'] for c,_ in chunks for o in c)!=sorted(m.scanned):raise ValueError('Lost/duplicated output')
    result=dict(status='exact_output_partition',seconds=time.monotonic()-start,cones=rows,
        source_sha256={str(q):sha(q) for q in (Path(__file__),Path(__file__).with_name('scan_faults.py'),Path(__file__).with_name('scan_bench.py'))},
        capture_sha256=sha(a.capture/'result.json'),scope='Complete observation partition; no physical fault exclusions or coverage claims')
    (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS exact partition',len(rows),'cones;',len(outputs),'observations; max nodes',max(r['nodes'] for r in rows))


if __name__=='__main__':main()
