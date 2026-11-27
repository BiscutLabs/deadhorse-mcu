"""Pinned OpenROAD T37 insertion on a fresh, unplaced production chip.

Run using OpenROAD's Python interpreter with T37_SCAN_CONFIG. Outputs are
logical/structural evidence only, never routed hold or ATPG acceptance.
"""
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(Path(__file__).parent))
from scan_cells import PREFIX, groups, qualify, qualify_gate, without_test_cell, expression
from scan_probe import snapshot, boundary
from scan_graph import chains, normal_mode, test_mode


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    import openroad
    import odb
    config_path=Path(os.environ['T37_SCAN_CONFIG']).resolve()
    config_path.relative_to(ROOT/'build')
    config=json.loads(config_path.read_text())
    out=(ROOT/config['output']).resolve();out.relative_to(ROOT/'build')
    out.mkdir(parents=True,exist_ok=False)
    started=time.monotonic()
    result=dict(status='error', scope='Unplaced scan insertion and functional structural certificate; ATPG, capture replay and electrical timing remain separate',
        input_sha256={str(config_path):sha(config_path)}, source_sha256={
            str(p.relative_to(ROOT)):sha(p) for p in [Path(__file__),Path(__file__).with_name('scan_graph.py'),
                Path(__file__).with_name('scan_cells.py'),Path(__file__).with_name('scan_probe.py'),
                Path(__file__).with_name('usb_cells.py'),ROOT/'tools/timing/usb_boundary.py']})
    try:
        executable=Path(config['openroad'])
        if sha(executable)!='a58debef32b592a7f2622a42a65434c313f2d332b84dc15af4798b33db24e0b4':
            raise ValueError('Wrong OpenROAD binary')
        mpath=ROOT/config['manifest'];m=json.loads(mpath.read_text())
        result['input_sha256'][str(mpath)]=sha(mpath)
        for path,digest in m['input_sha256'].items():
            if sha(ROOT/path)!=digest:raise ValueError('Stale manifest input: '+path)
            result['input_sha256'][path]=digest
        source=ROOT/config['odb'];imp=json.loads((ROOT/config['import_receipt']).read_text())
        if imp['status']!='imported_unplaced' or sha(source)!=imp['output_sha256']:
            raise ValueError('Wrong fresh input ODB')
        if imp.get('script_sha256')!={'tools/physical/scan_import.py':sha(ROOT/'tools/physical/scan_import.py')}:
            raise ValueError('Stale/unreviewed import recipe')
        v=[p for p in m['input_sha256'] if p.endswith('/chip_top.v')]
        if len(v)!=1 or imp['inputs'].get(str(ROOT/v[0]))!=m['input_sha256'][v[0]]:
            raise ValueError('Import is not the manifested physical netlist')
        for path,digest in imp['inputs'].items():
            if sha(path)!=digest:raise ValueError('Stale imported input: '+path)
            result['input_sha256'][path]=digest
        result['input_sha256'][str(source)]=sha(source)
        libdir=ROOT/config['libdir']
        lock_path=ROOT/'phys/gf180-ws-1x1/pdk-lock.json'
        lock=json.loads(lock_path.read_text());libraries=sorted(libdir.glob('*.lib'))
        if len(libraries)!=15:raise ValueError('Incomplete Liberty corner set')
        for lib in libraries:
            if sha(lib)!=lock['files'][lib.name]:raise ValueError('Wrong PDK Liberty')
        result['input_sha256'][str(lock_path)]=sha(lock_path)
        tech=openroad.Tech();tech.readLiberty(str(libdir/(PREFIX+'tt_025C_3v30.lib')))
        d=openroad.Design(tech);d.readDb(str(source));b=d.getBlock();db=tech.getDB()
        before=snapshot(b);ports=boundary(b)
        (out/'before.json').write_text(json.dumps(before))
        eligible={n for row in m['lanes'] for n in row['cells']}
        body=dict(groups((libdir/(PREFIX+'tt_025C_3v30.lib')).read_text(),'cell'))
        state=set();gates=set();sequential={}
        for kind in {c['type'] for c in before.values()} & set(body):
            text=without_test_cell(body[kind])
            sequential[kind]=('ff' if list(groups(text,'ff')) else 'other' if any(
                list(groups(text,k)) for k in ('latch','latch_bank','ff_bank','statetable')) else None)
        for name,cell in before.items():
            if cell['type'] not in body:
                if cell['type'].startswith(PREFIX):raise ValueError('Unknown standard cell')
                continue  # pad/memory/analog/wafer macros are explicit separate inventory below
            if sequential[cell['type']]=='ff':state.add(name)
            elif sequential[cell['type']]=='other':
                if name not in m['clock_gates']:raise ValueError('Unexpected unscanned state: '+name)
                gates.add(name)
        if state != eligible | set(m['excluded']) or gates != set(m['clock_gates']):
            raise ValueError('Incomplete state inventory')
        result['macro_inventory']=dict(Counter(c['type'] for c in before.values() if c['type'] not in body))
        expected_macros={'gf180mcu_fd_io__asig_5p0':2,'gf180mcu_fd_io__bi_24t':40,
            'gf180mcu_fd_io__in_s':1,'gf180mcu_fd_io__in_c':13,
            'gf180mcu_fd_io__dvdd':8,'gf180mcu_fd_io__dvss':10,
            'gf180mcu_ocd_ip_sram__sram1024x8m8wm1':16,
            'gf180mcu_ocd_ip_sram__sram512x8m8wm1':4,'LfRcMacro':1,'PorBrownoutMacro':1,
            **{'gf180mcu_ws_ip__'+name:1 for name in ('marker','project_id','qrcode_id','shuttle_id','logo')}}
        if result['macro_inventory']!=expected_macros:raise ValueError('Unknown/excluded macro inventory')
        io_paths=[p for p in imp['inputs'] if p.endswith('gf180mcu_fd_io__tt_025C_3v30.lib')]
        if len(io_paths)!=1:raise ValueError('Missing authenticated pad Liberty')
        io_cells=dict(groups(Path(io_paths[0]).read_text(),'cell'))
        for kind in expected_macros:
            if kind.startswith('gf180mcu_fd_io__') and kind in io_cells:
                if any(list(groups(io_cells[kind],k)) for k in ('ff','latch','ff_bank','latch_bank','statetable')):
                    raise ValueError('Unaccounted pad state')
            elif kind.startswith('gf180mcu_fd_io__') and kind not in ('gf180mcu_fd_io__dvdd','gf180mcu_fd_io__dvss','gf180mcu_fd_io__asig_5p0'):
                raise ValueError('Missing digital pad model')

        def ep(pair):
            inst=b.findInst(pair[0]);term=inst.findITerm(pair[1]) if inst else None
            if term is None or term.getNet() is None:raise ValueError('Missing mapped endpoint: '+str(pair))
            return term
        def net(name):
            if b.findNet(name):raise ValueError('Net collision')
            return odb.dbNet.create(b,name)
        added=[]
        def new(kind,name,pins):
            if b.findInst(name):raise ValueError('Instance collision')
            master=db.findMaster(PREFIX+kind)
            if master is None:raise ValueError('Missing approved cell')
            inst=odb.dbInst.create(b,master,name)
            for pin,n in pins.items():inst.findITerm(pin).connect(n)
            for pin in ('VDD','VNW'):inst.findITerm(pin).connect(b.findNet('VDD'))
            for pin in ('VSS','VPW'):inst.findITerm(pin).connect(b.findNet('VSS'))
            added.append(name);return inst
        commands=[]
        def tcl(command):
            commands.append(command)
            code=d.evalTclString('catch {'+command+'} _t37_result')
            message=d.evalTclString('set _t37_result')
            if code!='0':raise ValueError('OpenROAD command failed: '+command+'\n'+message)
            return message
        # Cache original pad/root nets BEFORE any endpoint is changed.
        mode=ep(m['mode']).getNet();enable=ep(m['enable']).getNet()
        reset_n=ep(m['reset_n']).getNet();osc=ep(m['osc']).getNet();tck=ep(m['tck']).getNet()
        si=[ep(pair).getNet() for pair in m['inputs']]
        roots={row['lane']:ep(row['clock_endpoint']).getNet() for row in m['lanes']}
        zero=b.findInst('i_chip_core.soc.scanHooks.lane_0').findITerm('I').getNet()
        one=b.findInst('i_chip_core.soc.lf').findITerm('enable').getNet()
        se=net('_t37_scan_enable');new('and2_1','_t37_scan_enable',{'A1':mode,'A2':enable,'Z':se})
        for lane,n in enumerate(si):
            z=net('_t37_scan_in_'+str(lane));new('buf_1','_t37_scan_in_'+str(lane),{'I':n,'Z':z})
        for name in m['excluded']:b.findInst(name).setDoNotTouch(True)
        inversion=None
        for row in m['lanes']:
            if row['clock_pin']!='CLKN':continue
            if inversion is not None:raise ValueError('Multiple negative partitions')
            inv=net('_t37_negative_clock')
            new('clkinv_4','_t37_negative_clock',{'I':roots[row['lane']],'ZN':inv})
            inversion=dict(cell='_t37_negative_clock', original=roots[row['lane']].getName(),output=inv.getName())
            for name in row['cells']:
                inst=b.findInst(name);p={t.getMTerm().getName():t.getNet() for t in inst.getITerms()}
                kind=inst.getMaster().getName().replace('dffnrnq','dffrnq').removeprefix(PREFIX)
                odb.dbInst.destroy(inst)
                new(kind,name,{('CLK' if pin=='CLKN' else pin):(inv if pin=='CLKN' else n)
                    for pin,n in p.items() if pin not in ('VDD','VNW','VSS','VPW')})
                added.remove(name)
        tcl('set_dft_config -clock_mixing no_mix -max_chains 1 -scan_enable_name_pattern _t37_scan_enable/Z -scan_in_name_pattern _t37_scan_in_{}/Z -scan_out_name_pattern i_chip_core.soc.scanHooks.lane_{}/I')
        tcl('scan_replace')
        # Replacement can delete the STA pin on the divider's output FF.
        # Define group clocks AFTER replacement, before chain architecture.
        for row in m['lanes']:
            clock=b.findNet(inversion['output']) if row['clock_pin']=='CLKN' else roots[row['lane']]
            drivers=[t for t in clock.getITerms() if str(t.getMTerm().getIoType())=='OUTPUT']
            if len(drivers)!=1:raise ValueError('Ambiguous clock driver')
            pin=drivers[0].getInst().getName()+'/'+drivers[0].getMTerm().getName()
            # Assumed architectural clock only, not an electrical signoff SDC.
            tcl('create_clock -name group_'+str(row['lane'])+' -period 100 [get_pins {'+pin+'}]')
        tcl('report_dft_plan');tcl('execute_dft_plan')
        chain_rows=chains(snapshot(b),m)
        (out/'chains.json').write_text(json.dumps(chain_rows,indent=2))

        serial=0
        def mux(original,test,label):
            nonlocal serial
            name='_t37_'+label+'_'+str(serial);serial+=1
            z=net(name);new('mux2_1',name,{'I0':original,'I1':test,'S':mode,'Z':z})
            return z
        # Gate outputs retain their original tree. Only the base roots get a
        # test clock, and TE forces both actual library ICGs open in test mode.
        gated={b.findInst(n).findITerm('Q').getNet().getName() for n in m['clock_gates']}
        muxed={}
        for root in {n.getName():n for n in roots.values()}.values():
            if root.getName()==osc.getName() or root.getName() in gated:continue
            target=mux(root,osc,'clock');muxed[root.getName()]=target
        for row in m['lanes']:
            original=roots[row['lane']]
            if row['clock_pin']=='CLKN':
                b.findInst(inversion['cell']).findITerm('I').connect(muxed[original.getName()])
            elif original.getName() in muxed:
                for name in row['cells']:b.findInst(name).findITerm('CLK').connect(muxed[original.getName()])
        for name in m['clock_gates']:
            gate=b.findInst(name);clock=gate.findITerm('CLK').getNet()
            if clock.getName() in muxed:gate.findITerm('CLK').connect(muxed[clock.getName()])
            if gate.findITerm('TE').getNet().getName()!=zero.getName():raise ValueError('Existing gate test connection')
            gate.findITerm('TE').connect(mode)
        resets={}
        for name in eligible:
            inst=b.findInst(name)
            for pin in ('RN','SN'):
                term=inst.findITerm(pin)
                if term is None:continue
                key=term.getNet().getName()
                if key not in resets:resets[key]=mux(term.getNet(),reset_n,'reset')
                term.connect(resets[key])
        # SRAM outputs get a raw net plus clamp at their physical interface.
        clamps=[]
        def output_clamp(inst,pin):
            term=inst.findITerm(pin);original=term.getNet()
            raw=net('_t37_raw_'+str(len(clamps)));term.connect(raw)
            name='_t37_output_clamp_'+str(len(clamps))
            new('mux2_1',name,{'I0':raw,'I1':zero,'S':mode,'Z':original})
            clamps.append(dict(cell=inst.getName(),pin=pin,raw=raw.getName(),original=original.getName()))
        memories=[i for i in b.getInsts() if i.getMaster().getName().startswith('gf180mcu_ocd_ip_sram__')]
        if len(memories)!=20:raise ValueError('Changed SRAM inventory')
        for inst in memories:
            outputs=[t for t in inst.getITerms() if str(t.getMTerm().getIoType())=='OUTPUT']
            if len(outputs)!=8:raise ValueError('Changed memory output width')
            for term in outputs:output_clamp(inst,term.getMTerm().getName())
            controls=[t for t in inst.getITerms() if t.getMTerm().getName() in ('CEN','GWEN') or t.getMTerm().getName().startswith('WEN[')]
            if len(controls)!=10:raise ValueError('Changed SRAM control interface')
            for term in controls:term.connect(mux(term.getNet(),one,'memory_disable'))
        por=b.findInst('i_chip_core.soc.por')
        output_clamp(por,'brownout')
        for term in por.getITerms():
            if term.getMTerm().getName().startswith('threshold['):
                term.connect(mux(term.getNet(),zero,'threshold'))
        output_pins={}
        for inst in b.getInsts():
            kind=inst.getMaster().getName()
            if kind not in output_pins:
                output_pins[kind]=[t.getMTerm().getName() for t in inst.getITerms()
                    if str(t.getMTerm().getIoType())=='OUTPUT' and str(t.getMTerm().getSigType()) not in ('POWER','GROUND')]
        for cell in before.values():
            if cell['type'] not in output_pins:
                master=db.findMaster(cell['type'])
                output_pins[cell['type']]=[t.getName() for t in master.getMTerms()
                    if str(t.getIoType())=='OUTPUT' and str(t.getSigType()) not in ('POWER','GROUND')]
        controls=dict(added=added,zero=zero.getName(),one=one.getName(),mode=mode.getName(),
            enable=enable.getName(),reset_n=reset_n.getName(),osc=osc.getName(),tck=tck.getName(),
            output_clamps=clamps,clock_muxes={k:v.getName() for k,v in muxed.items()},
            reset_muxes={k:v.getName() for k,v in resets.items()},inversion=inversion,
            output_pins=output_pins,state_or_macro=sorted(state|gates|{n for n,c in before.items() if c['type'] not in body}))
        after=snapshot(b)
        if boundary(b)!=ports:raise ValueError('Package boundary changed')
        result['functional']=normal_mode(before,after,m,controls)
        result['test_controls']=test_mode(after,m,controls)
        if chains(after,m)!=chain_rows:raise ValueError('Controls changed chain stitching')
        pairs=Counter((before[n]['type'],after[n]['type']) for n in eligible)
        result['qualified_views']={}
        for lib in libraries:
            cells=dict(groups(lib.read_text(),'cell'))
            result['qualified_views'][lib.name]=[qualify(cells,a,z) for a,z in pairs]
            qualify_gate(cells[PREFIX+'icgtp_1'])
            # Exact functions relied upon by the graph reducer, checked in every corner.
            from usb_cells import signature
            tests={'buf_1':('Z',['I'],lambda a:a[0]),'clkinv_4':('ZN',['I'],lambda a:not a[0]),
                'and2_1':('Z',['A1','A2'],lambda a:a[0] and a[1]),
                'mux2_1':('Z',['I0','I1','S'],lambda a:a[1] if a[2] else a[0])}
            import itertools
            for kind,(pin,inputs,expected) in tests.items():
                f=signature(cells[PREFIX+kind])
                if f['ff']:raise ValueError('Unexpected primitive state')
                for values in itertools.product((False,True),repeat=len(inputs)):
                    if expression(f['pins'][pin]['function'],dict(zip(inputs,values))) != expected(values):
                        raise ValueError('Wrong added primitive function')
        # Faults mutate actual OpenDB connections; restore and re-audit each.
        faults={};victim=next(n for n in sorted(eligible) if 'RN' in before[n]['pins'])
        for pin in ('D','RN'):
            term=b.findInst(victim).findITerm(pin);old=term.getNet()
            term.connect(b.findInst(victim).findITerm('Q').getNet())
            try:normal_mode(before,snapshot(b),m,controls)
            except ValueError as error:faults[pin]=str(error)
            else:raise ValueError('Functional fault escaped')
            finally:term.connect(old)
        term=b.findInst(chain_rows[0]['cells'][0]).findITerm('SI');old=term.getNet();term.connect(zero)
        try:chains(snapshot(b),m)
        except ValueError as error:faults['chain-break']=str(error)
        else:raise ValueError('Broken chain escaped')
        finally:term.connect(old)
        term=b.findInst(m['clock_gates'][0]).findITerm('TE');old=term.getNet();term.connect(zero)
        try:test_mode(snapshot(b),m,controls)
        except ValueError as error:faults['gate-test-disabled']=str(error)
        else:raise ValueError('Test-side gate fault escaped')
        finally:term.connect(old)
        term=b.findInst('_t37_scan_in_0').findITerm('I');old=term.getNet()
        term.connect(b.findInst('_t37_scan_in_1').findITerm('I').getNet())
        try:normal_mode(before,snapshot(b),m,controls)
        except ValueError as error:faults['si-pad-swap']=str(error)
        else:raise ValueError('SI pad swap escaped')
        finally:term.connect(old)
        normal_mode(before,snapshot(b),m,controls);chains(snapshot(b),m);test_mode(snapshot(b),m,controls)
        result['negative_controls']=faults
        def area(kind):return float(re.search(r'\barea\s*:\s*([\d.]+)\s*;',body[kind])[1])
        result['standard_cell_area_um2']={label:sum(area(c['type']) for c in graph.values() if c['type'] in body)
            for label,graph in [('before',before),('after',after)]}
        result['eligible']=len(eligible);result['excluded']=m['excluded']
        result['chain_lengths']=[len(r['cells']) for r in chain_rows]
        result['controls']=controls
        (out/'after.json').write_text(json.dumps(snapshot(b)))
        d.writeDb(str(out/'scan.odb'));tcl('write_verilog '+str(out/'scan.v'))
        (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
        result['artifacts']={p.name:sha(p) for p in out.iterdir() if p.is_file()}
        result['status']='pass_unplaced_insertion'
        print('PASS unplaced scan insertion:',len(eligible),'FFs; chains',result['chain_lengths'])
    except Exception as error:
        result['error']=repr(error)
        raise
    finally:
        result['seconds']=time.monotonic()-started
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        if 'commands' in locals():(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')


if __name__=='__main__':main()
