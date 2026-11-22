"""Measure production DMA SRAM arbitration; audit/cut synchronous memory interfaces.

Same boundary technique as the T20 study. Macro delay/area and physical wiring
are excluded explicitly; all intervening production control logic is retained.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools.timing.check import measure

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    p.add_argument('--xip',action='store_true',help='Include the optional T30 native flash port; identical memory projection')
    a=p.parse_args()
    out=(ROOT/a.output).resolve();out.relative_to(ROOT/'build');out.mkdir(parents=True,exist_ok=False)
    paths=[f for name in ('hw/top/reference/src/main','hw/lib','tools/timing') for f in (ROOT/name).rglob('*')
           if f.is_file() and f.suffix in ('.scala','.py','.tcl')]
    paths += [Path(__file__),ROOT/'build/t20/map/soc.json',ROOT/'build/t20/i0-firmware/boot.hex',
              ROOT/'build.sbt',ROOT/'tools/env/lock.json',ROOT/'phys/gf180-ws-1x1/block-timing.json']
    hashes=lambda:{f.relative_to(ROOT).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in paths}
    result=dict(status='running',source_sha256=hashes(),
        commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        xip_enabled=a.xip,
        scope='Mapped pre-layout production local-memory control at main-9MHz; five synchronous memory interfaces exposed, macro area/delay excluded; zero IO delays, no physical signoff')
    def run(argv,name):
        with (out/(name+'.log')).open('w') as log:subprocess.run(argv,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
    def yosys(lines,name):
        f=out/(name+'.ys');f.write_text('\n'.join(lines)+'\n');run(['yosys','-Q','-T','-s',str(f)],name)
    try:
        emit=out/'emit'
        emitter='EmitXipMemory' if a.xip else 'EmitDmaMemory'
        run([sys.executable,'tools/sbt.py',f'hw/runMain deadhorse.top.{emitter} {emit.relative_to(ROOT)}'],'emit')
        sv=sorted(emit.glob('*.sv'))
        yosys(['read_slang --keep-hierarchy -DSYNTHESIS --top SocLocalMemory '+' '.join(map(str,sv)),
            'hierarchy -check -top SocLocalMemory','proc','chformal -remove','memory_collect',f'write_json {out}/hier.json'],'hier')
        design=json.loads((out/'hier.json').read_text());top=design['modules']['SocLocalMemory']
        expected=['rom_ext','outputs_memory_ext','outputs_memory_1_ext','outputs_memory_2_ext','outputs_memory_3_ext']
        inventory=[]
        for name in expected:
            cell=top['cells'][name];mod=design['modules'][cell['type']]
            arrays=[c for c in mod['cells'].values() if c['type']=='$mem_v2'];assert len(arrays)==1
            ar=arrays[0];params=ar['parameters'];size=16384 if name=='rom_ext' else 1024
            assert int(params['WIDTH'],2)==32 and int(params['SIZE'],2)==size
            edges={};sequential=[];clock_pin='R0_clk' if name=='rom_ext' else 'RW0_clk'
            for n,c in mod['cells'].items():
                kind=c['type'];pins=c['connections']
                if kind in ('$dff','$dffe'):
                    assert pins['CLK']==mod['ports'][clock_pin]['bits'] and int(c['parameters']['CLK_POLARITY'],2)==1
                    sequential.append(n);continue
                if kind=='$mem_v2':
                    assert int(params['RD_CLK_ENABLE'],2)==0
                    if name!='rom_ext':
                        count=int(params['WR_PORTS'],2)
                        assert int(params['WR_CLK_ENABLE'],2)==(1<<count)-1
                        assert set(pins['WR_CLK'])==set(mod['ports'][clock_pin]['bits'])
                    ins=pins['RD_ADDR']+pins['RD_EN'];outs=pins['RD_DATA']
                else:
                    assert kind.startswith('$')
                    ins=[b for p,bs in pins.items() if c['port_directions'][p]=='input' for b in bs]
                    outs=[b for p,bs in pins.items() if c['port_directions'][p]=='output' for b in bs]
                for b in outs:edges.setdefault(b,set()).update(ins)
            assert sequential
            inputs={b for p in mod['ports'].values() if p['direction']=='input' for b in p['bits']}
            todo=[b for p in mod['ports'].values() if p['direction']=='output' for b in p['bits']];seen=set()
            while todo:
                b=todo.pop()
                if not isinstance(b,int) or b in seen:continue
                assert b not in inputs,'Memory read has a combinational input dependency'
                seen.add(b);todo.extend(edges.get(b,()))
            inventory.append(dict(instance=name,module=cell['type'],interface=mod['ports'],size=size,width=32))
        yosys([f'read_json {out}/hier.json','blackbox '+' '.join(i['module'] for i in inventory),
            'flatten','check -assert',f'write_json {out}/flat.json'],'flatten')
        original=json.loads((out/'flat.json').read_text());cut=copy.deepcopy(original);t=cut['modules']['SocLocalMemory']
        removed={};added=[]
        for index,item in enumerate(inventory):
            cell=t['cells'].pop(item['instance']);removed[item['instance']]=cell
            for pin,port in item['interface'].items():
                bits=cell['connections'][pin]
                if pin.endswith('_clk'):assert bits==t['ports']['clk']['bits'];continue
                name=f'memcut_{index}_{pin}';assert name not in t['ports']
                t['ports'][name]=dict(direction='input' if port['direction']=='output' else 'output',bits=bits);added.append(name)
            del cut['modules'][item['module']]
        assert not any(c['type'].startswith('$mem') for c in t['cells'].values())
        restored=copy.deepcopy(cut)
        for n in added:del restored['modules']['SocLocalMemory']['ports'][n]
        restored['modules']['SocLocalMemory']['cells'].update(removed)
        for item in inventory:restored['modules'][item['module']]=original['modules'][item['module']]
        assert restored==original,'Projection changed production logic'
        (out/'cut.json').write_text(json.dumps(cut))
        yosys([f'read_json {out}/cut.json','hierarchy -check -top SocLocalMemory','check -assert','scc -expect 0',
               f'write_verilog {out}/cut.v'],'cut')
        result['memory_inventory']=inventory
        result['projection']='Exact graph restored by reinstating memory cells and deleting added ports; synchronous read boundary audited'
        result['measurement']=measure('SocLocalMemory',[str(out/'cut.v')],'clk',out/'timing',operating_point='main-9mhz')
        if hashes()!=result['source_sha256']:raise ValueError('Timing sources changed during run')
        result['status']=result['measurement']['status']
    except Exception as e:result.update(status='failed',error=str(e))
    result['artifact_sha256']={f.relative_to(out).as_posix():hashlib.sha256(f.read_bytes()).hexdigest()
        for f in out.rglob('*') if f.is_file() and f!=out/'result.json'}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(result['status'].upper(),result.get('error',''))
    return 0 if result['status']=='pass' else 1
if __name__=='__main__':sys.exit(main())
