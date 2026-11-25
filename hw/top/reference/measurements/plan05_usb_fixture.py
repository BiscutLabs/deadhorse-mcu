"""Derive the physical slot boundary from actual PLAN05 mapped pin topology."""
import copy

BUFFER='gf180mcu_fd_sc_mcu7t5v0__buf_4'
PREFIX='digital.subsystem.usb.'

def buffered_slot(slot,parent,binding):
    result=copy.deepcopy(slot)
    drivers={b:(n,p) for n,c in parent['cells'].items() for p,bs in c['connections'].items()
             if c['port_directions'][p]=='output' for b in bs}
    used={b for c in result['cells'].values() for bs in c['connections'].values() for b in bs if isinstance(b,int)}
    next_bit=max(used)+1;groups={};rows=[]
    for port in sorted(slot['ports']):
        if not port.startswith('target_') or slot['ports'][port]['direction']!='output':continue
        peer='bus_'+port.removeprefix('target_');actual=parent['netnames'][PREFIX+peer]['bits']
        assert len(actual)==len(slot['ports'][port]['bits'])
        for index,destination in enumerate(actual):
            name=peer if len(actual)==1 else f'{peer}[{index}]'
            old=binding['ports'][name];cell=slot['cells'][old['cell']]
            assert cell['type']==old['type'] and old['pin']=='Q'
            original=cell['connections']['Q'][0]
            # Moving a port alias behind its real buffer must not remove the
            # only name of the original Q net. Explicit names also prevent
            # Yosys JSON import auto-name collisions with existing USB nets.
            qname='plan05_original_q_'+str(original)
            assert qname not in slot['netnames']
            result['netnames'][qname]=dict(hide_name=0,bits=[original],attributes={})
            n,p=drivers[destination];driver=parent['cells'][n];buffer=None;source=destination
            if driver['type']==BUFFER:
                assert p=='Z' and set(driver['connections'])=={'I','Z'}
                assert n.startswith('usb_boundary_')
                buffer=n;source=driver['connections']['I'][0]
            if isinstance(source,int):
                launch,pin=drivers[source];launch_cell=parent['cells'][launch]
                assert pin=='Q' and launch_cell['type']==old['type']
                assert launch_cell['connections']['CLK']==parent['netnames'][PREFIX+'appClock']['bits']
                groups.setdefault(source,original);fixture_source=groups[source]
            else:
                assert source in ('0','1');launch=None;fixture_source=source
            output=fixture_source
            if buffer:
                output=next_bit;next_bit+=1
                result['cells'][buffer]=dict(hide_name=0,type=BUFFER,parameters={},attributes={},
                    port_directions={'I':'input','Z':'output'},connections={'I':[fixture_source],'Z':[output]})
                result['netnames'][buffer+'_out']=dict(hide_name=0,bits=[output],attributes={})
            result['ports'][port]['bits'][index]=output
            if port in result['netnames']:result['netnames'][port]['bits'][index]=output
            rows.append(dict(port=port,index=index,peer=name,production_source=source,
                production_launch=launch,production_buffer=buffer,fixture_source=fixture_source,
                fixture_output=output,original_fixture_q=original))
    assert len(rows)==73 and sum(bool(r['production_buffer']) for r in rows)==35
    assert sum(not isinstance(r['production_source'],int) for r in rows)==1
    audit(result,slot,rows)
    return result,rows

def audit(result,original,rows):
    added={r['production_buffer'] for r in rows if r['production_buffer']}
    assert set(result['cells'])==set(original['cells'])|added
    for name,cell in original['cells'].items():assert result['cells'][name]==cell
    sources={}
    for row in rows:
        port=row['port'];index=row['index'];output=result['ports'][port]['bits'][index]
        if row['production_buffer']:
            c=result['cells'][row['production_buffer']]
            assert c['type']==BUFFER and c['connections']==dict(I=[row['fixture_source']],Z=[output])
            assert c['port_directions']==dict(I='input',Z='output')
        else:assert output==row['fixture_source']
        source=row['production_source']
        if isinstance(source,int):
            assert row['fixture_source'] in {c['connections']['Q'][0] for c in original['cells'].values() if 'Q' in c['connections']}
            if source in sources:assert sources[source]==row['fixture_source'],'Split actual source alias'
            sources[source]=row['fixture_source']
        else:assert row['fixture_source']==source,'Changed actual constant'
    assert len(set(sources.values()))==len(sources),'Merged independent actual sources'
    allowed={r['port'] for r in rows}
    for name,p in original['ports'].items():
        if name not in allowed:assert result['ports'][name]==p

def faults(result,original,rows):
    first=next(r for r in rows if r['production_buffer'] and isinstance(r['production_source'],int))
    constant=next(r for r in rows if not isinstance(r['production_source'],int))
    repeated=next(r for r in rows if r['fixture_source']!=r['original_fixture_q'] and isinstance(r['production_source'],int))
    caught=[]
    for name in ('wrong-input','omitted-buffer','wrong-constant','split-alias'):
        bad=copy.deepcopy(result)
        if name=='wrong-input':bad['cells'][first['production_buffer']]['connections']['I']=['1']
        elif name=='omitted-buffer':del bad['cells'][first['production_buffer']]
        elif name=='wrong-constant':bad['cells'][constant['production_buffer']]['connections']['I']=['1' if constant['production_source']=='0' else '0']
        else:bad['cells'][repeated['production_buffer']]['connections']['I']=[repeated['original_fixture_q']]
        try:audit(bad,original,rows)
        except AssertionError:caught.append(name)
        else:raise AssertionError('Fixture fault escaped: '+name)
    return caught
