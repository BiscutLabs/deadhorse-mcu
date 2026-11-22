"""Hierarchical mapping of the complete production logic, with named macro sockets."""
import copy, hashlib, json, subprocess, sys
from pathlib import Path
root=Path.cwd();base=root/'build/plan03/production-measure01'
lib=root/'build/riscay-mcu/.tools/physical/pdk/gf180mcu_fd_sc_mcu7t5v0__ss_125C_3v00.lib'
for mhz in (8,9):
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
    def run(lines,name):
        script=out/(name+'.ys');script.write_text('\n'.join(lines)+'\n')
        with (out/(name+'.log')).open('w') as f:
            subprocess.run(['yosys','-Q','-T','-s',str(script)],stdout=f,stderr=subprocess.STDOUT,check=True)
    run([f'read_json {out}/hier.json',
         'blackbox '+' '.join(i['module'] for i in cuts),
         'synth -top DeadhorseSoc',f'dfflibmap -liberty {lib}',f'abc -liberty {lib}',
         'opt_clean -purge',f'tee -o {out}/area.txt stat -liberty {lib}',
         f'write_json {out}/mapped-hier.json','flatten','opt_clean -purge',
         'check -assert',f'write_json {out}/mapped-flat.json'],'map')
    original=json.loads((out/'mapped-flat.json').read_text());projected=copy.deepcopy(original)
    top=projected['modules']['DeadhorseSoc'];removed={};ports=[]
    for index,item in enumerate(cuts):
        name=item['instance'].removesuffix('.Memory');cell=top['cells'].pop(name)
        assert cell['type']==item['module'];removed[name]=cell
        item['connections']=cell['connections'];item['ports']={}
        for pin,port in item['interface'].items():
            bits=cell['connections'][pin]
            if pin==item['clock_pin']:
                assert bits==top['ports']['i1_aonClock' if item['clock_domain']=='aon' else 'mainClock']['bits']
                continue
            name=f'macro_{index}_{pin}'
            assert name not in top['ports']
            top['ports'][name]=dict(direction='input' if port['direction']=='output' else 'output',bits=bits)
            ports.append(name);item['ports'][pin]=name
    restored=copy.deepcopy(projected)
    for p in ports:del restored['modules']['DeadhorseSoc']['ports'][p]
    restored['modules']['DeadhorseSoc']['cells'].update(removed)
    assert original==restored
    assert all(c['type'].startswith('gf180mcu_fd_sc_mcu7t5v0__') for c in top['cells'].values())
    (out/'projected.json').write_text(json.dumps(projected))
    run([f'read_json {out}/projected.json','hierarchy -top DeadhorseSoc','check -assert',
         'scc -expect 0',f'write_verilog -noattr -noexpr {out}/mapped.v'],'export')
    (out/'macro-sockets.json').write_text(json.dumps(cuts,indent=2)+'\n')
    print(f'{mhz}: mapped full production logic; six synchronous macro sockets, exact restoration',flush=True)
