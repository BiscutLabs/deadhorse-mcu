"""Layer-balanced reset tree, same GF180 buffer and fanout bound."""
import copy,math
from t32_packed_reset import packed
from tools.timing.fanout import BUFFER,verify

def layered(module,sources,limit=8,prefix='soc_reset_'):
    # Reuse independently checked input/source validation, but construct full
    # layers instead of the minimal mixed-depth packing used for exploration.
    packed(module,sources,limit,prefix)
    result=copy.deepcopy(module);cells=result['cells'];sinks={s:[] for s in sources}
    bits=[b for c in cells.values() for bs in c['connections'].values() for b in bs if isinstance(b,int)]
    bits += [b for n in list(module['ports'].values())+list(module['netnames'].values()) for b in n['bits'] if isinstance(b,int)]
    nextbit=max(bits)+1
    for name,c in cells.items():
        for pin,d in c['port_directions'].items():
            if d=='input':
                for i,b in enumerate(c['connections'][pin]):
                    if b in sources:sinks[b].append((name,pin,i))
    inserted=[];rows=[]
    for source,targets in sorted(sinks.items()):
        frontier=targets;start=len(inserted);depth=0
        while len(frontier)>limit:
            parents=[];depth+=1
            for offset in range(0,len(frontier),limit):
                group=frontier[offset:offset+limit];name=prefix+str(len(inserted));assert name not in cells
                bit=nextbit;nextbit+=1
                cells[name]=dict(hide_name=0,type=BUFFER,parameters={},attributes={},
                    port_directions={'I':'input','Z':'output'},connections={'I':[source],'Z':[bit]})
                inserted.append(name)
                for n,p,i in group:cells[n]['connections'][p][i]=bit
                parents.append((name,'I',0))
            frontier=parents
        for n,p,i in frontier:cells[n]['connections'][p][i]=source
        rows.append(dict(source=source,sinks=len(targets),buffers=len(inserted)-start,all_sink_depth=depth,
            theoretical_mixed_depth_minimum=max(0,math.ceil((len(targets)-limit)/(limit-1)))))
    verify(module,result,inserted)
    return result,inserted,rows
