"""Compare upstream and extracted TAP/DTM at the explicitly removed CDC seam."""
from pathlib import Path
import argparse,hashlib,json,subprocess,time,copy,sys
root=Path(__file__).resolve().parents[4]
ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',required=True)
args=ap.parse_args();out=(root/args.output).resolve();out.relative_to(root/'build');out.mkdir(parents=True,exist_ok=False)
ref=root/'hw/vendor/riscv_dbg';gate=root/'build/vendor/riscv_dbg'
cdc=root/'build/t32/riscv-dbg/src/dmi_cdc.sv'
commit=subprocess.check_output(['git','-C',str(cdc.parents[1]),'rev-parse','HEAD'],text=True).strip()
assert commit=='643607e19df3435cfd77cc56143e2637f5900a6e'
assert subprocess.check_output(['git','-C',str(cdc.parents[1]),'show','HEAD:src/dmi_cdc.sv']).replace(b'\r\n',b'\n')==cdc.read_bytes().replace(b'\r\n',b'\n')
names=['riscv-dbg/src/dm_pkg.sv','tech_cells_generic/src/rtl/tc_clk.sv','riscv-dbg/src/dmi_jtag_tap.sv','riscv-dbg/src/dmi_jtag.sv']
sources=[*[ref/n for n in names],*[gate/n for n in names],cdc]
lock=json.loads((ref/'riscv_dbg.lock.json').read_text())
for base,key in ((ref,'sha256'),(gate,'applied_sha256')):
    for name in names:assert hashlib.sha256((base/name).read_bytes()).hexdigest()==lock['files'][name][key]
cc=root/'build/t32/common_cells'
assert subprocess.check_output(['git','-C',str(cc),'rev-parse','HEAD'],text=True).strip()=='b5ec8905ed7828655155b0ae971023adf793c600'
deps=[cc/'src'/(n+'.sv') for n in ('cdc_reset_ctrlr_pkg','sync','spill_register_flushable','spill_register','cdc_4phase','cdc_reset_ctrlr','cdc_2phase_clearable')]
headers=list((cc/'include').rglob('*.svh'))
for p in deps+headers:
    assert subprocess.check_output(['git','-C',str(cc),'show','HEAD:'+p.relative_to(cc).as_posix()]).replace(b'\r\n',b'\n')==p.read_bytes().replace(b'\r\n',b'\n')
sources+=deps+headers+[Path(__file__).resolve(),ref/'riscv_dbg.lock.json',root/'tools/env/lock.json']
receipt=dict(status='running',scope='TAP/DTM sequential equivalence at original TCK-side CDC seam; does not equate old and new CDC implementations',
             source_sha256={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},runs=[])
def run(name,lines):
    script=out/(name+'.ys');script.write_text('\n'.join(lines)+'\n');start=time.monotonic()
    with(out/(name+'.log')).open('w') as f:
        try:code=subprocess.run(['yosys','-Q','-T','-s',str(script)],stdout=f,stderr=subprocess.STDOUT,timeout=120).returncode
        except subprocess.TimeoutExpired:code=124
    receipt['runs'].append(dict(command=['yosys','-Q','-T','-s',str(script)],returncode=code,seconds=time.monotonic()-start))
    return code
try:
    for label,base in [('gold',ref),('gate',gate)]:
        files=[base/n for n in names]+([*deps,cdc] if label=='gold' else [])
        lines=[f'read_slang --top dmi_jtag --blackboxed-module dmi_cdc -I{cc}/include '+' '.join(map(str,files)),
               'hierarchy -top dmi_jtag','proc','flatten']
        lines += [f'write_json {out}/{label}-seam.json']
        if label=='gold':lines+=['select -assert-count 1 t:dmi_cdc','delete t:dmi_cdc']
        lines+=['delete -port '+' '.join('dmi_jtag/w:'+n for n in ('clk_i','rst_ni','dmi_rst_no','dmi_req_o','dmi_req_valid_o','dmi_req_ready_i','dmi_resp_i','dmi_resp_ready_o','dmi_resp_valid_i')),
                'expose -input '+' '.join('dmi_jtag/w:'+n for n in ('dmi_req_ready','dmi_resp','dmi_resp_valid')),
                'expose '+' '.join('dmi_jtag/w:'+n for n in ('dmi_req','dmi_req_valid','dmi_resp_ready','dmi_clear')),
                'opt_clean -purge','clk2fflogic','opt_clean -purge','check -assert',f'write_json {out}/{label}.json']
        assert run(label,lines)==0,label
    # Check the removed instance's real seam and the production extraction's
    # external wiring BEFORE either side is cut for frontend equivalence.
    g=json.loads((out/'gold-seam.json').read_text())['modules']['dmi_jtag']
    a=json.loads((out/'gate-seam.json').read_text())['modules']['dmi_jtag']
    def canonical(module):
        buffers={}
        for cell in module['cells'].values():
            if cell['type']=='$buf':
                aa=cell['connections']['A'];yy=cell['connections']['Y'];assert len(aa)==len(yy)
                for src,dst in zip(aa,yy):
                    assert dst not in buffers or buffers[dst]==src
                    buffers[dst]=src
        def bits(values):
            result=[]
            for bit in values:
                seen=set()
                while bit in buffers:
                    assert bit not in seen,'Buffer cycle';seen.add(bit);bit=buffers[bit]
                result.append(bit)
            return result
        return bits
    gb=canonical(g);ab=canonical(a)
    cells=[c for c in g['cells'].values() if c['type']=='dmi_cdc'];assert len(cells)==1
    seam={'jtag_dmi_req_i':'dmi_req','jtag_dmi_valid_i':'dmi_req_valid','jtag_dmi_ready_i':'dmi_resp_ready',
          'jtag_dmi_cdc_clear_i':'dmi_clear','jtag_dmi_ready_o':'dmi_req_ready',
          'jtag_dmi_resp_o':'dmi_resp','jtag_dmi_valid_o':'dmi_resp_valid','tck_i':'tck','trst_ni':'trst_ni'}
    for pin,net in seam.items():assert gb(cells[0]['connections'][pin])==gb(g['netnames'][net]['bits']),pin
    aliases={'dmi_req_o':'dmi_req','dmi_req_valid_o':'dmi_req_valid','dmi_req_ready_i':'dmi_req_ready',
             'dmi_resp_i':'dmi_resp','dmi_resp_valid_i':'dmi_resp_valid','dmi_resp_ready_o':'dmi_resp_ready'}
    for pin,net in aliases.items():assert ab(a['ports'][pin]['bits'])==ab(a['netnames'][net]['bits']),pin
    inversion=[c for c in a['cells'].values() if c['type'] in ('$not','$logic_not') and
               ab(c['connections']['A'])==ab(a['netnames']['dmi_clear']['bits']) and ab(c['connections']['Y'])==ab(a['ports']['dmi_rst_no']['bits'])]
    assert len(inversion)==1,'TCK clear polarity/alias changed'
    receipt['seam_audit']=dict(original_instance_pins=seam,extracted_port_aliases=aliases,clear='dmi_rst_no == !dmi_clear')
    gold=json.loads((out/'gold.json').read_text())['modules']['dmi_jtag'];modified=json.loads((out/'gate.json').read_text())
    m=modified['modules']['dmi_jtag']
    assert {n:(p['direction'],len(p['bits'])) for n,p in gold['ports'].items()}=={n:(p['direction'],len(p['bits'])) for n,p in m['ports'].items()}
    receipt['boundary']={n:dict(direction=p['direction'],width=len(p['bits'])) for n,p in m['ports'].items()}
    def equiv(candidate,tail):return [f'read_json {out}/gold.json','rename dmi_jtag gold','design -stash gold',f'read_json {candidate}',
        'rename dmi_jtag gate','design -stash gate','design -copy-from gold -as gold gold','design -copy-from gate -as gate gate',
        'equiv_make gold gate equivalence','hierarchy -top equivalence',*tail]
    code=run('prove',equiv(out/'gate.json',['equiv_simple','equiv_induct -seq 4','equiv_status -assert']))
    if code:raise RuntimeError('Positive equivalence unresolved' if code==124 else 'Positive equivalence failed')
    # Actual serial input corruption on the extracted frontend, not its oracle.
    bit=m['ports']['td_i']['bits'][0];fresh=1+max(b for c in m['cells'].values() for bs in c['connections'].values() for b in bs if isinstance(b,int))
    loads=0
    for c in m['cells'].values():
        for pin,bits in c['connections'].items():
            if c['port_directions'][pin]=='input':loads+=bits.count(bit);c['connections'][pin]=[fresh if b==bit else b for b in bits]
    assert loads
    m['cells']['tap_input_fault']=dict(hide_name=0,type='$not',parameters={'A_SIGNED':0,'A_WIDTH':1,'Y_WIDTH':1},attributes={},
        port_directions={'A':'input','Y':'output'},connections={'A':[bit],'Y':[fresh]})
    fault=out/'fault.json';fault.write_text(json.dumps(modified))
    # SAT concrete witness over the equivalence miter; a failed induction alone
    # is insufficient to qualify this negative control.
    tail=['equiv_miter -assert miter','hierarchy -top miter','flatten','opt_clean',
          'sat -seq 24 -set-init-zero -set-at 1 trst_ni 0 -show-inputs -show-outputs -prove-asserts -verify -dump_vcd '+str(out/'fault.vcd')]
    code=run('fault',equiv(fault,tail))
    assert code==1 and (out/'fault.vcd').exists() and 'model found: FAIL' in (out/'fault.log').read_text(),'Unqualified serial fault'
    receipt['status']='pass'
except Exception as e:receipt.update(status='failed',error=str(e))
receipt['artifact_sha256']={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()}
(out/'result.json').write_text(json.dumps(receipt,indent=2)+'\n');print(receipt['status'],receipt.get('error',''))
sys.exit(0 if receipt['status']=='pass' else 1)
