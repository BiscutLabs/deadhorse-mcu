"""Independent bit-parallel serial replay of the inserted scan FF graph.

64 seeded patterns are simulated simultaneously. Each edge uses the actual SI
net of each mapped FF; the chain manifest supplies only tester order/expected
values. Capture/logic ATPG is deliberately not claimed by this shift check.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import time


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def replay(graph, chain_rows, seed, mutate=False):
    mask=(1<<64)-1
    rng=random.Random(seed)
    names=sorted(n for row in chain_rows for n in row['cells'])
    index={n:i for i,n in enumerate(names)}
    by_q={graph[n]['pins']['Q']:index[n] for n in names}
    si={graph['_t37_scan_in_'+str(i)]['pins']['Z']:len(names)+i for i in range(7)}
    if len(by_q)!=len(names) or len(si)!=7:raise ValueError('Ambiguous serial inputs/state')
    predecessors=[]
    for name in names:
        pin=graph[name]['pins']['SI']
        if pin in by_q:predecessors.append(by_q[pin])
        elif pin in si:predecessors.append(si[pin])
        else:raise ValueError('Unmodelled scan input')
    desired=[rng.getrandbits(64) for _ in names]
    state=[rng.getrandbits(64) for _ in names]+[0]*7
    longest=max(len(r['cells']) for r in chain_rows)
    lanes=[[index[n] for n in row['cells']] for row in chain_rows]
    tails=[]
    for lane in range(7):
        net=graph['i_chip_core.soc.scanHooks.lane_'+str(lane)]['pins']['I']
        if net not in by_q:raise ValueError('Unobserved scan tail')
        tails.append(by_q[net])
    # Actual inserted FF equations and phase/reset/SE control were qualified by
    # scan_insert. With SE=1 and reset inactive, every active event loads SI.
    # Groups share no state, so their rising/falling shift updates commute.
    # Do not use this commutation for functional capture, which is separate.
    if mutate:
        # Physically bypass one FF in a long chain; no manifest walk is called.
        victim=lanes[max(range(7),key=lambda i:len(lanes[i]))][1]
        predecessors[victim]=predecessors[predecessors[victim]]
    for cycle in range(longest):
        for lane,order in enumerate(lanes):
            position=longest-cycle-1
            state[len(names)+lane]=desired[order[position]] if position<len(order) else 0
        state=[state[p] for p in predecessors]+[0]*7
    if state[:len(names)]!=desired:raise ValueError('Serial load differs from arbitrary assigned state')
    for cycle in range(longest):
        for lane,order in enumerate(lanes):
            expected=desired[order[-cycle-1]] if cycle<len(order) else 0
            if state[tails[lane]]!=expected:raise ValueError('Serial output differs from assigned state')
        state=[state[p] for p in predecessors]+[0]*7
    if any(state):raise ValueError('Zero unload did not clear scan state')
    return dict(patterns=64,seed=seed,state_bits=len(names),shift_cycles=2*longest,
        arbitrary_bits_loaded_and_observed=64*len(names),
        protocol='Each OSC period shifts rising groups then falling TAP group; no cross-phase SI path')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--insert',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    receipt=json.loads((a.insert/'result.json').read_text())
    if receipt['status']!='pass_unplaced_insertion':raise ValueError('Insertion not qualified')
    for name in ('after.json','chains.json'):
        if sha(a.insert/name)!=receipt['artifacts'][name]:raise ValueError('Stale insertion artifact')
    graph=json.loads((a.insert/'after.json').read_text());chains=json.loads((a.insert/'chains.json').read_text())
    result=replay(graph,chains,37)
    try:replay(graph,chains,37,mutate=True)
    except ValueError as error:result['chain_break_negative_control']=str(error)
    else:raise ValueError('Serial replay missed broken chain')
    result.update(status='pass_serial_only',seconds=time.monotonic()-start,
        inputs={str(q):sha(q) for q in (Path(__file__),a.insert/'result.json',a.insert/'after.json',a.insert/'chains.json')},
        scope='Actual mapped SI/Q serial load/unload; functional capture, ATPG coverage, pad electrical and timing remain unqualified')
    (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS 64-pattern serial replay and chain-bypass negative control;',result['state_bits'],'state bits')


if __name__=='__main__':main()
