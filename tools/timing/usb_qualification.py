"""Audit actual applied USB exceptions and plant real over-budget data paths."""
import copy
import csv
import hashlib
import itertools
import json
import math
from pathlib import Path
import re
import subprocess


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def expected_pairs(certificate):
    if certificate.get('status')!='pass':raise ValueError('No register certificate')
    result={};reset=certificate['reset_aware'];groups=reset['groups']
    def add(launches,captures,setup,hold):
        for a,b in itertools.product(launches,captures):
            for mode,value in (('setup',setup),('hold',hold)):
                key=(mode,a+'/CLK',b+'/D')
                if key in result and result[key]!=value:raise ValueError('Conflicting certified exception')
                result[key]=value
    for a,b in reset['allowed_pairs']:add(groups[a],groups[b],4,3)
    pre=certificate.get('pre_enable',{})
    if pre:
        if pre.get('status')!='pass':raise ValueError('Unqualified pre-enable certificate')
        add([n for g in pre['allowed_launch_groups'] for n in groups[g]],list(pre['capture_pins']),3,2)
    return result


def applied_pairs(text,top=None):
    text=re.sub(r'\\\r?\n\s*',' ',text);result={}
    clock_groups=[]
    for line in text.splitlines():
        line=line.strip()
        if not line or line.startswith('#'):continue
        command=line.split()[0]
        if command not in {'current_design','create_clock','set_clock_groups','set_input_delay',
                'set_output_delay','set_input_transition','set_load','set_multicycle_path'}:
            raise ValueError('Unexpected timing command/override: '+command)
        if command=='set_clock_groups':clock_groups.append(line)
        if not line.startswith('set_multicycle_path'):continue
        match=re.fullmatch(r'set_multicycle_path -(setup|hold) -from (.+) -to (.+) (\d+)',line.strip())
        if not match:raise ValueError('Unsupported applied multicycle syntax')
        def pins(value,suffix):
            names=re.findall(r'\[get_pins \{([^{}]+)\}\]',value)
            remainder=re.sub(r'\s+',' ',re.sub(r'\[get_pins \{[^{}]+\}\]','',value)).strip()
            if (not names or len(names)!=len(set(names)) or
                remainder not in ('','[list ]') or
                any(not n.endswith('/'+suffix) or re.search(r'\s',n) for n in names)):
                raise ValueError('Ambiguous/non-register exception pins')
            return names
        for launch,capture in itertools.product(pins(match[2],'CLK'),pins(match[3],'D')):
            key=(match[1],launch,capture)
            if key in result and result[key]!=int(match[4]):raise ValueError('Conflicting applied exception')
            result[key]=int(match[4])
    if top=='Usb':
        if len(clock_groups)!=1 or not re.fullmatch(
                r'set_clock_groups -name \w+ -asynchronous(?:\s+-group \[get_clocks \{\w+\}\]){3}',clock_groups[0]) or \
                sorted(re.findall(r'\[get_clocks \{(\w+)\}\]',clock_groups[0]))!=['aonClock','appClock','usbClock']:
            raise ValueError('Unexpected asynchronous clock exclusions')
    elif clock_groups:raise ValueError('Unexpected single-domain clock exclusion')
    return result


def audit_exceptions(text,certificate,top=None):
    expected=expected_pairs(certificate);actual=applied_pairs(text,top)
    if not expected or actual!=expected:raise ValueError('Applied exceptions differ from certified pairs')
    return {mode+str(cycles):sum(k[0]==mode and v==cycles for k,v in actual.items())
            for mode,cycles in (('setup',4),('hold',3),('setup',3),('hold',2))}


def delay_fault(design,top,start,count=160):
    """Insert only identity buffers after one real launch; no state changes."""
    result=copy.deepcopy(design);m=result['modules'][top]
    if '/' in start:
        name,pin=start.rsplit('/',1);cell=m['cells'][name]
        if cell['port_directions'][pin]!='output':raise ValueError('Wrong delay-fault launch pin')
        bits=cell['connections'][pin]
    else:
        match=re.fullmatch(r'(.*)\[(\d+)\]',start)
        name,index=(match[1],int(match[2])) if match else (start,0)
        if m['ports'][name]['direction']!='input':raise ValueError('Wrong delay-fault port')
        bits=[m['ports'][name]['bits'][index]]
    if len(bits)!=1 or not isinstance(bits[0],int):raise ValueError('Mixed/constant delay-fault launch')
    bit=bits[0];first=max(b for c in m['cells'].values() for bs in c['connections'].values() for b in bs if isinstance(b,int))+1
    last=first+count-1;loads=0
    for c in m['cells'].values():
        for pin,bs in c['connections'].items():
            if c['port_directions'][pin]=='input':
                loads+=bs.count(bit);c['connections'][pin]=[last if b==bit else b for b in bs]
    for port_name,port in m['ports'].items():
        if port['direction']=='output':
            loads+=port['bits'].count(bit);port['bits']=[last if b==bit else b for b in port['bits']]
            # JSON ports and their named wires must describe the same bits.
            # Otherwise read_json aliases the old driver back onto the output.
            if port_name in m.get('netnames',{}):
                m['netnames'][port_name]['bits']=list(port['bits'])
    if not loads:raise ValueError('Disconnected delay-fault launch')
    if 'timing_fault_launch' in m.setdefault('netnames',{}):raise ValueError('Delay-fault launch alias collision')
    m['netnames']['timing_fault_launch']=dict(hide_name=0,bits=[bit],attributes={})
    for i in range(count):
        name='timing_fault_'+str(i)
        if name in m['cells']:raise ValueError('Delay-fault cell collision')
        m['cells'][name]=dict(hide_name=0,type='gf180mcu_fd_sc_mcu7t5v0__buf_1',parameters={},attributes={},
            port_directions={'I':'input','Z':'output'},connections={'I':[bit if i==0 else first+i-1],'Z':[first+i]})
        wire=name+'_wire'
        if wire in m.setdefault('netnames',{}):raise ValueError('Delay-fault net collision')
        m['netnames'][wire]=dict(hide_name=0,bits=[first+i],attributes={})
    return result,dict(launch=start,buffers=count,loads=loads)


def qualify(output,top,certificate,classes,limits,run,classifier):
    """Called after complete positive STA; every populated class is exercised."""
    root=Path(__file__).resolve().parents[2];target=output/'protocol-qualification';target.mkdir(exist_ok=False)
    original=(root/'tools/timing/analyze.tcl').read_text()
    analysis=target/'applied.tcl';analysis.write_text(original+f'\nwrite_sdc {{{target}/applied.sdc}}\nputs USB_EXCEPTION_EXPORT_COMPLETE\n')
    driver=target/'applied-driver.tcl'
    driver.write_text((output/'timing.tcl').read_text().replace(str(root/'tools/timing/analyze.tcl'),str(analysis))
        .replace(str(output/'paths.tsv'),str(target/'paths.tsv')).replace(str(output/'gate_checks.tsv'),str(target/'gate_checks.tsv')))
    log=run(['sta','-no_init','-exit',str(driver)],output,'protocol-applied')
    if 'USB_EXCEPTION_EXPORT_COMPLETE' not in log:raise ValueError('Missing applied SDC')
    text=(target/'applied.sdc').read_text();counts=audit_exceptions(text,certificate,top)
    # Actual SDC mutations must be rejected by the independent pair audit.
    flat=re.sub(r'\\\r?\n\s*',' ',text)
    for label,bad in [('wrong-multiplier',re.sub(r'(set_multicycle_path[^\n]* )4\n',r'\g<1>5\n',flat,count=1)),
                      ('wrong-hold',re.sub(r'(set_multicycle_path -hold[^\n]* )3\n',r'\g<1>2\n',flat,count=1)),
                      ('missing-pair',re.sub(r'set_multicycle_path[^\n]*\n','',flat,count=1)),
                      ('false-path',text+'\n set_false_path -from [all_registers]\n'),
                      ('clock-bypass',text+'\nset_clock_groups -asynchronous -group [get_clocks {block_clock}]\n'),
                      ('wrong-capture-pin',text.replace('/D}', '/CLK}',1))]:
        if bad==text:raise ValueError('Unreachable exception negative control')
        try:audit_exceptions(bad,certificate,top)
        except ValueError:pass
        else:raise ValueError('Exception mutation escaped: '+label)
        (target/(label+'.sdc')).write_text(bad)
    design=json.loads((output/'mapped.json').read_text());faults={}
    for kind,path in classes.items():
        if path is None:continue
        case=target/kind;case.mkdir();bad,mutation=delay_fault(design,top,path['start'])
        (case/'mapped.json').write_text(json.dumps(bad))
        script=case/'emit.ys';script.write_text(f'read_json {case}/mapped.json\ncheck -assert\nwrite_verilog -noattr -noexpr {case}/mapped.v\n')
        run(['yosys','-Q','-T','-s',str(script)],output,'protocol-fault-emit-'+kind)
        driver=case/'timing.tcl';driver.write_text((output/'timing.tcl').read_text()
            .replace(str(output/'mapped.v'),str(case/'mapped.v')).replace(str(output/'paths.tsv'),str(case/'paths.tsv'))
            .replace(str(output/'gate_checks.tsv'),str(case/'gate_checks.tsv')))
        log=run(['sta','-no_init','-exit',str(driver)],output,'protocol-fault-'+kind)
        if 'TIMING_COMPLETE' not in log:raise ValueError('Incomplete over-budget fault STA: '+kind)
        with (case/'paths.tsv').open() as stream:paths=[r for r in csv.DictReader(stream,delimiter='\t') if r['class']==kind]
        worst=max(paths,key=lambda r:float(r['delay_ns']),default=None)
        if (worst is None or not math.isfinite(float(worst['delay_ns'])) or
                float(worst['delay_ns'])<=max(limits[kind],path['delay_ns']) or worst['start']!=path['start'] or
                any(f'timing_fault_{i}/' not in worst['points'] for i in range(mutation['buffers']))):
            raise ValueError('Over-budget class fault escaped/missed injected chain: '+kind)
        measured=dict(worst,delay_ns=float(worst['delay_ns']))
        verdict=classifier([measured],{kind:limits[kind]},{kind:limits[kind]},
            {'max_capacitance_and_slew_violations':0},[],[])
        if verdict['setup_status']!='fail' or verdict['status']!='fail':raise ValueError('Production classifier accepted planted delay')
        faults[kind]=dict(status='fault_rejected',mutation=mutation,delay_ns=float(worst['delay_ns']),limit_ns=limits[kind],
            start=worst['start'],end=worst['end'],classifier=verdict,baseline_class_max_ns=path['delay_ns'])
    result=dict(status='pass',pair_counts=counts,negative_controls=faults,
        certificate_sha256=hashlib.sha256(json.dumps(certificate,sort_keys=True).encode()).hexdigest(),
        qualification='Only certified setup4/hold3 and setup3/hold2 pairs applied; every other pair retains default single-cycle constraints; every populated path class rejects real inserted delay',
        artifact_sha256={str(p):digest(p) for p in target.rglob('*') if p.is_file()})
    (target/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
