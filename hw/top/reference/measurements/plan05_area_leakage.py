"""PLAN05 mapped block/domain inventory and library-only static leakage estimate."""
import argparse,collections,hashlib,json,re,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from tools.timing.usb_boundary import groups
from hw.top.reference.measurements.plan04_screen import clock_manifest

PREFIXES={'digital.core':'performance_core','digital.memory':'main_memory_control','clocks':'clock_reset',
    'causes':'reset_causes'}
for instance,label in dict(liteHart='lite_core',retained='retained_memory_control',af='aon_fabric',mf='main_fabric',
        aonIo='aon_io_fabric',aonSpi='aon_spi',aonGpio='aon_gpio',aonTimer='aon_timers',timers='general_timers',
        p='pinmux',gpio='gpio',dma='dma',usb='usb',spi='spi',i2c='i2c',flash='qspi_xip',mailbox='mailbox',
        debugger='jtag_debug',leaf='debug_bridge',toAon='main_to_aon',boot='lite_boot_control',
        oscillator='oscillator_controller',powerReset='power_reset',uartSleep='uart_sleep',bist='sram_bist',
        channels_0='performance_watchdog',channels_1='lite_watchdog',uarts_0='uart0',uarts_1='uart1',uarts_2='uart2').items():
    PREFIXES['digital.subsystem.'+instance]=label

def label(name):
    return next((v for p,v in PREFIXES.items() if name==p or name.startswith(p+'.')),None)

def main(base):
    base=(ROOT/base).resolve();base.relative_to(ROOT/'build')
    mapped=base/'map/canonical.json';receipt=json.loads((base/'map/result.json').read_text())
    digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    assert receipt['status']=='mapped' and digest(mapped)==receipt['mapped_sha256']
    m=json.loads(mapped.read_text())['modules']['DeadhorseSoc'];cells=m['cells'];clocks=clock_manifest(m)
    macro_lock_path=ROOT/'hw/vendor/gf180_sram/gf180_sram.lock.json';macro_lock=json.loads(macro_lock_path.read_text())
    macros={macro_lock['macro'],macro_lock['retained_macro']}
    inputs=[mapped,base/'map/result.json',macro_lock_path,Path(__file__),Path(__file__).with_name('plan04_screen.py'),ROOT/'tools/timing/usb_boundary.py']
    aliases=collections.defaultdict(set)
    for n,v in m['netnames'].items():
        group=label(n)
        if group and not v.get('hide_name'):
            for b in v['bits']:aliases[b].add(group)
    drivers={b:n for n,c in cells.items() for p,bs in c['connections'].items() if c['port_directions'][p]=='output' for b in bs if isinstance(b,int)}
    owner={};domain={};state=set()
    for n,c in cells.items():
        cp=next((p for p in ('CLK','CLKN') if p in c['connections']),None)
        if cp is None:continue
        state.add(n)
        group=label(n);found=set().union(*(aliases[b] for b in c['connections'].get('Q',[])))
        owner[n]={group} if group else found or {'other_state'}
        actual=clocks.get(n+'/'+cp)
        if c['type'] in macros:actual='aon' if '.retained.' in n else 'main'
        domain[n]={actual or 'clock_glue'}
    def spread(owners):
        queue=collections.deque(owners)
        while queue:
            n=queue.popleft()
            for p,bs in cells[n]['connections'].items():
                if cells[n]['port_directions'][p]!='input' or p in ('CLK','CLKN'):continue
                for b in bs:
                    source=drivers.get(b)
                    if source is None or source in state:continue
                    prior=owners.setdefault(source,set());extra=owners[n]-prior
                    if extra:prior.update(extra);queue.append(source)
    spread(owner);spread(domain)
    def group(owners,n):
        found=owners.get(n,set())
        return next(iter(found)) if len(found)==1 else 'shared_glue' if found else 'output_clock_glue'
    pdk_path=ROOT/'build/riscay-mcu/physical/gf180/pdk-lock.json';pdk=json.loads(pdk_path.read_text());inputs.append(pdk_path)
    result=dict(status='estimated_library_leakage',by_block={},by_domain={},corners={},
        method='Area/count from mapped cells; block ownership from sequential endpoint backward cones. Shared glue counted once. Leakage sums each cell conditional-state minimum/mean/maximum; means assume equally weighted characterized states, not actual sleep activity. SRAM uses the unconditional library cell_leakage_power scalar as an idle/standby proxy; CEN high and normal rail are assumed. The two macro sizes have identical library scalars, not inferred capacity scaling.',
        exclusions=['AON switching and SRAM read/write dynamic power','Analog LF/POR macros','Pad cells/pulls','Board oscillator standby, regulator and radio',('Future scan/physical cells' if receipt.get('implemented_rom') else 'Unimplemented ROM and future scan/physical cells')],
        qualification='Not a whole-system current prediction or power signoff. Main/USB clocks stop, supplies and all SRAM stay on. Powered digital+SRAM current is a static subtotal; excluded currents must be added.')
    for corner,voltage in [('tt_025C_3v30',3.3),('ff_125C_3v60',3.6)]:
        lib=ROOT/f'build/riscay-mcu/.tools/physical/pdk/gf180mcu_fd_sc_mcu7t5v0__{corner}.lib'
        assert digest(lib)==pdk['files'][lib.name];inputs.append(lib);text=lib.read_text()
        assert re.search(r'leakage_power_unit\s*:\s*"?1uW',text)
        data={}
        for name,body in groups(text,'cell'):
            if name not in {c['type'] for c in cells.values()}:continue
            values=[]
            for _,g in groups(body,'leakage_power'):
                assert re.search(r'related_pg_pin\s*:\s*"VDD"',g)
                if re.search(r'\bwhen\s*:',g):values.append(float(re.search(r'\bvalue\s*:\s*"?([\deE.+-]+)',g)[1]))
            if not values:values=[float(re.search(r'\bvalue\s*:\s*"?([\deE.+-]+)',g)[1]) for _,g in groups(body,'leakage_power')]
            assert values and all(v>=0 for v in values),name
            data[name]=(float(re.search(r'\barea\s*:\s*([\d.]+)',body)[1]),[min(values),sum(values)/len(values),max(values)])
        totals=[0.,0.,0.];macro_total=0.;per_domain={}
        for n,c in cells.items():
            if c['type'] in macros:continue
            area,values=data[c['type']];dom=group(domain,n);block=group(owner,n)
            for i,v in enumerate(values):totals[i]+=v
            bucket=per_domain.setdefault(dom,[0.,0.,0.])
            for i,v in enumerate(values):bucket[i]+=v
            if corner.startswith('tt'):
                for table,key in [(result['by_block'],block),(result['by_domain'],dom)]:
                    row=table.setdefault(key,dict(cells_measured=0,flops_measured=0,area_um2_measured=0.))
                    row['cells_measured']+=1;row['flops_measured']+=int('__dff' in c['type']);row['area_um2_measured']+=area
        macro_rows=[]
        for macro in sorted(macros):
            relative=f'cells/{macro}/{macro}__{corner}.lib';path=ROOT/'build/vendor/gf180_sram'/relative
            assert digest(path)==macro_lock['files'][relative];inputs.append(path);body=path.read_text()
            assert re.search(r'leakage_power_unit\s*:\s*"1mW"',body)
            value=float(re.search(r'(?<!default_)\bcell_leakage_power\s*:\s*([\deE.+-]+)',body)[1])*1000
            count=sum(c['type']==macro for c in cells.values());macro_total+=count*value
            macro_rows.append(dict(cell=macro,instances_measured=count,standby_uW_per_instance_estimated=value,subtotal_uW_estimated=count*value))
        result['corners'][corner]=dict(voltage_assumed=voltage,cell_leakage_uW_min_mean_max_estimated=totals,
            by_domain_uW_min_mean_max_estimated=per_domain,sram=macro_rows,sram_standby_uW_estimated=macro_total,
            powered_digital_sram_uA_min_mean_max_estimated=[(v+macro_total)/voltage for v in totals])
    result['input_sha256']={p.relative_to(ROOT).as_posix():digest(p) for p in inputs}
    (base/'block-area-leakage.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',required=True);main(p.parse_args().base)
