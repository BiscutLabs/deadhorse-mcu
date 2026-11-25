"""Keep certified USB input identities distinct using real, audited buffers."""
import copy
from tools.timing.fanout import BUFFER,verify

PORTS=('bus_bits_addr','bus_bits_origin')

def isolate(module,reference,prefix='digital.subsystem.usb.'):
    result=copy.deepcopy(module);inserted=[];bindings=[];by_source={}
    bits=[b for c in module['cells'].values() for bs in c['connections'].values() for b in bs if isinstance(b,int)]
    bits += [b for p in list(module['ports'].values())+list(module['netnames'].values()) for b in p['bits'] if isinstance(b,int)]
    next_bit=max(bits)+1
    other_inputs={b for name,p in reference['ports'].items()
        if p['direction']=='input' and name not in PORTS
        for b in module['netnames'][prefix+name]['bits'] if isinstance(b,int)}
    for port in PORTS:
        assert reference['ports'][port]['direction']=='input'
        originals=module['netnames'][prefix+port]['bits']
        assert len(originals)==len(reference['ports'][port]['bits'])
        for index,(source,refbit) in enumerate(zip(originals,reference['ports'][port]['bits'])):
            if not isinstance(source,int):continue
            assert source not in other_inputs,'USB data boundary aliases another input class'
            if source not in by_source:
                name=f'usb_boundary_{port}_{index}';alias=name+'_source';output=next_bit;next_bit+=1
                assert name not in result['cells'] and alias not in result['netnames']
                result['cells'][name]=dict(hide_name=0,type=BUFFER,parameters={},attributes={'keep':'1'},
                    port_directions={'I':'input','Z':'output'},connections={'I':[source],'Z':[output]})
                result['netnames'][alias]=dict(hide_name=0,bits=[source],attributes={'keep':'1'})
                inserted.append(name);by_source[source]=output
                bindings.append(dict(cell=name,source_alias=alias,port=port,index=index,reference_bit=refbit))
    # Only island consumers and island aliases change. Parent drivers, clocks,
    # resets and all other block consumers are byte-for-byte unchanged.
    for name,c in result['cells'].items():
        if not name.startswith(prefix):continue
        for pin,bs in c['connections'].items():
            if c['port_directions'][pin]=='input':c['connections'][pin]=[by_source.get(b,b) for b in bs]
    for name,n in result['netnames'].items():
        if name.startswith(prefix):n['bits']=[by_source.get(b,b) for b in n['bits']]
    verify(module,result,inserted)
    first=inserted[0]
    for fault in ('cycle','wrong_input'):
        bad=copy.deepcopy(result)
        bad['cells'][first]['connections']['I']=bad['cells'][first]['connections']['Z'][:] if fault=='cycle' else ['0']
        try:verify(module,bad,inserted)
        except ValueError:pass
        else:raise AssertionError(f'USB boundary {fault} fault escaped')
    return result,bindings

def audit(module,bindings,prefix='digital.subsystem.usb.'):
    for row in bindings:
        cell=module['cells'][row['cell']]
        assert cell['type']==BUFFER and cell['port_directions']==dict(I='input',Z='output')
        assert cell['connections']['I']==module['netnames'][row['source_alias']]['bits']
        assert cell['connections']['Z']==[module['netnames'][prefix+row['port']]['bits'][row['index']]]
