"""Same buffer cell and fanout bound, packed reset tree; physical experiment."""
import collections,copy,hashlib,json,math,sys
from pathlib import Path
root=Path.cwd();sys.path.insert(0,str(root))
from tools.timing.fanout import BUFFER,verify

def packed(module,sources,limit=8,prefix='soc_reset_'):
    assert limit>=2
    result=copy.deepcopy(module);cells=result['cells']
    clocks={b for c in cells.values() for pin in ('CLK','CLKN') for b in c['connections'].get(pin,[])}
    assert sources and not sources&clocks
    bits=[b for c in cells.values() for v in c['connections'].values() for b in v if isinstance(b,int)]
    bits += [b for v in list(module['ports'].values())+list(module['netnames'].values()) for b in v['bits'] if isinstance(b,int)]
    nextbit=max(bits)+1;sinks=collections.defaultdict(list)
    for name,c in cells.items():
        for pin,d in c['port_directions'].items():
            if d=='input':
                for index,b in enumerate(c['connections'][pin]):
                    if b in sources:sinks[b].append((name,pin,index))
    assert set(sinks)==sources
    inserted=[];rows=[]
    for source,targets in sorted(sinks.items()):
        frontier=collections.deque(targets);start=len(inserted)
        while len(frontier)>limit:
            group=[frontier.popleft() for _ in range(limit)]
            name=prefix+str(len(inserted));assert name not in cells
            bit=nextbit;nextbit+=1
            cells[name]=dict(hide_name=0,type=BUFFER,parameters={},attributes={},
                port_directions={'I':'input','Z':'output'},connections={'I':[source],'Z':[bit]})
            inserted.append(name)
            for n,p,i in group:cells[n]['connections'][p][i]=bit
            frontier.append((name,'I',0))
        for n,p,i in frontier:cells[n]['connections'][p][i]=source
        count=len(inserted)-start
        assert count==max(0,math.ceil((len(targets)-limit)/(limit-1)))
        rows.append(dict(source=source,sinks=len(targets),buffers=count))
    verify(module,result,inserted)
    loads=collections.Counter(b for c in cells.values() for p,d in c['port_directions'].items() if d=='input' for b in c['connections'][p])
    assert all(loads[b]<=limit for b in sources)
    assert all(loads[cells[n]['connections']['Z'][0]]<=limit for n in inserted)
    return result,inserted,rows

if __name__=='__main__':
    base=root/(sys.argv[1] if len(sys.argv)>1 else 'build/t32/area03/mapped/map-8')
    out=root/'build/t32/soc-area-review/packed-reset';out.mkdir(exist_ok=True)
    design=json.loads((base/'unbuffered.json').read_text());m=design['modules']['DeadhorseSoc']
    primary={b for p in m['ports'].values() if p['direction']=='input' for b in p['bits']}
    sources={b for c in m['cells'].values() for p,bits in c['connections'].items() if p in ('RN','SETN') for b in bits if isinstance(b,int)}-primary
    new,inserted,rows=packed(m,sources)
    faults={}
    wrong=copy.deepcopy(new);name=inserted[0];wrong['cells'][name]['connections']['I']=wrong['cells'][name]['connections']['Z'][:]
    try:verify(m,wrong,inserted)
    except ValueError: faults['cycle']='rejected'
    else:raise AssertionError('cycle fault escaped')
    wrong=copy.deepcopy(new);c=next(c for c in wrong['cells'].values() if 'RN' in c['connections'])
    c['connections']['RN']=['1']
    try:verify(m,wrong,inserted)
    except ValueError:faults['wrong_reset']='rejected'
    else:raise AssertionError('wrong reset escaped')
    design['modules']['DeadhorseSoc']=new
    (out/'mapped.json').write_text(json.dumps(design))
    result=dict(status='packed_tree_graph_verified_not_physical_signoff',limit=8,cell=BUFFER,buffers=len(inserted),roots=rows,faults=faults,
        source_sha256=hashlib.sha256((base/'unbuffered.json').read_bytes()).hexdigest(),producer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        qualification='No RTL change, no fanout or cell-size relaxation. Existing verify checks every original connection after collapsing inserted buffers. Shortest/longest reset delays and electrical checks need measurement.')
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(buffers=len(inserted),previous=json.loads((base/'mapping.json').read_text())['reset_buffers'],faults=faults)))
