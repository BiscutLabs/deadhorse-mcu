"""Hierarchical mapping of the complete production logic, with named macro sockets."""
import copy, hashlib, json, subprocess, sys
from pathlib import Path
root=Path.cwd();base=root/'build/t32/area07'
lib=root/'build/riscay-mcu/.tools/physical/pdk/gf180mcu_fd_sc_mcu7t5v0__ss_125C_3v00.lib'
for mhz in (8,):
    out=base/f'map-{mhz}';design=json.loads((out/'hier.json').read_text())
    inv=json.loads((out/'memory-inventory.json').read_text())
    cuts=[i for i in inv if i['parameters']['SIZE']>=768]
    assert len(cuts)==6
    for item in cuts:
        mod=design['modules'][item['module']]
        clock='R0_clk' if item['parameters']['WR_PORTS']==0 else 'RW0_clk'
        edges={};sequential=[]
        for n,c in mod['cells'].items():
            p=c['connections']
            if c['type'] in ('$dff','$dffe'):
                assert p['CLK']==mod['ports'][clock]['bits'] and int(c['parameters']['CLK_POLARITY'],2)==1
                sequential.append(n);continue
            if c['type']=='$mem_v2':
                assert int(c['parameters']['RD_CLK_ENABLE'],2)==0
                if item['parameters']['WR_PORTS']:
                    assert set(p['WR_CLK'])==set(mod['ports'][clock]['bits'])
                    assert int(c['parameters']['WR_CLK_ENABLE'],2)==15
                inputs=p['RD_ADDR']+p['RD_EN'];outputs=p['RD_DATA']
            else:
                assert c['type'].startswith('$')
                inputs=[b for k,v in p.items() if c['port_directions'][k]=='input' for b in v]
                outputs=[b for k,v in p.items() if c['port_directions'][k]=='output' for b in v]
            for bit in outputs:edges.setdefault(bit,set()).update(inputs)
        assert sequential
        inputs={b for p in mod['ports'].values() if p['direction']=='input' for b in p['bits']}
        todo=[b for p in mod['ports'].values() if p['direction']=='output' for b in p['bits']];seen=set()
        while todo:
            b=todo.pop()
            if not isinstance(b,int) or b in seen:continue
            assert b not in inputs,('asynchronous read',item,b)
            seen.add(b);todo.extend(edges.get(b,()))
        item.update(clock_pin=clock,interface=mod['ports'],registered_read=True,
                    clock_domain='aon' if item['instance'].startswith('subsystem.retained.') else 'main')
    (out/'macro-sockets.json').write_text(json.dumps(cuts,indent=2)+'\n')
