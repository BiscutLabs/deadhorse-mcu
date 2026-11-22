"""D77 exact asynchronous sink qualification; raw STA is never suppressed."""
import copy
import csv
import hashlib
import json
import itertools
from pathlib import Path
import re


def logic_functions(liberty):
    from tools.timing.usb_boundary import groups
    result={}
    for name,body in groups(Path(liberty).read_text(),'cell'):
        ff=list(groups(body,'ff'))
        if ff:
            if re.fullmatch(r'gf180mcu_fd_sc_mcu7t5v0__dffrnq_\d+',name):
                fields=dict(re.findall(r'(\w+)\s*:\s*"([^"]+)"\s*;',ff[0][1]))
                normalized={k:re.sub(r'\s+','',v).strip('()') for k,v in fields.items()}
                if len(ff)!=1 or normalized!={'clocked_on':'CLK','next_state':'D','clear':'!RN'}:
                    raise ValueError('Unqualified reset-flop Liberty semantics')
                result[('__reset_ff__',name)]=True
            continue
        for pin,definition in groups(body,'pin'):
            function=re.search(r'\bfunction\s*:\s*"([^"]+)"',definition)
            if function:result[(name,pin)]=function[1]
    return result


def boolean_function(expression,values):
    """Restricted Liberty Boolean parser; no executable expression evaluation."""
    text=expression.replace(' ','').replace('*','&').replace('+','|')
    tokens=re.findall(r'[A-Za-z_][A-Za-z_0-9]*|[01!&|^()]',text)
    if ''.join(tokens)!=text:raise ValueError('Unsupported Liberty expression')
    pos=0
    def expression_at(level):
        nonlocal pos
        if level==3:
            if pos>=len(tokens):raise ValueError('Truncated Boolean expression')
            token=tokens[pos];pos+=1
            if token=='!':return not expression_at(3)
            if token=='(':
                value=expression_at(0)
                if pos>=len(tokens) or tokens[pos]!=')':raise ValueError('Unbalanced Boolean expression')
                pos+=1;return value
            if token in ('0','1'):return token=='1'
            if token not in values:raise ValueError('Unknown Liberty pin')
            return values[token]
        operation=('|','^','&')[level];left=expression_at(level+1)
        while pos<len(tokens) and tokens[pos]==operation:
            pos+=1;right=expression_at(level+1)
            left=(left or right) if operation=='|' else (left!=right) if operation=='^' else (left and right)
        return left
    result=expression_at(0)
    if pos!=len(tokens):raise ValueError('Trailing Boolean expression')
    return result


def inventory(module,top,functions):
    if top not in ('UsbEngine','Usb'):raise ValueError('Unsupported asynchronous boundary')
    cells=module['cells'];nets=module['netnames'];ports=module['ports'];drivers={}
    for name,c in cells.items():
        for pin,bits in c['connections'].items():
            if c['port_directions'][pin]=='output':
                for bit in bits:
                    if bit in drivers:raise ValueError('Multiple mapped drivers')
                    drivers[bit]=(name,pin)
    def canonical(bit,seen=()):
        if bit in seen:raise ValueError('Buffer loop')
        if bit in ('0','1') or bit not in drivers:return bit
        name,pin=drivers[bit];c=cells[name];kind=c['type'].split('__')[-1]
        if kind in ('tieh','tiel'):return '1' if kind=='tieh' else '0'
        if re.fullmatch(r'(?:buf|clkbuf)_\d+',kind):return canonical(c['connections']['I'][0],(*seen,bit))
        return bit
    loads={}
    for name,c in cells.items():
        if re.fullmatch(r'gf180mcu_fd_sc_mcu7t5v0__(?:buf|clkbuf)_\d+',c['type']):continue
        for pin,bits in c['connections'].items():
            if c['port_directions'][pin]=='input':
                for bit in bits:loads.setdefault(canonical(bit),[]).append(name+'/'+pin)
    output_bits={canonical(bit) for p in ports.values() if p['direction']=='output' for bit in p['bits']}
    clocks={canonical(p['bits'][0]):n for n,p in ports.items() if n in ('clk','appClock','usbClock','aonClock')}
    def register(bit):
        bit=canonical(bit);driver=drivers.get(bit)
        if not driver or driver[1]!='Q':raise ValueError('Missing/ambiguous mapped register identity')
        name,pin=driver;c=cells[name]
        if not re.fullmatch(r'gf180mcu_fd_sc_mcu7t5v0__dffrnq_\d+',c['type']) or any(len(v)!=1 for v in c['connections'].values()):
            raise ValueError('Unsupported asynchronous register type')
        if not functions.get(('__reset_ff__',c['type'])) or c.get('parameters',{}):raise ValueError('Unqualified reset-flop semantics')
        if canonical(c['connections']['CLK'][0]) not in clocks:raise ValueError('Non-root sampler clock')
        return name
    def net(name,width,unique=True):
        if name not in nets or len(nets[name]['bits'])!=width or (unique and len(set(nets[name]['bits']))!=width):
            raise ValueError('Missing/mixed asynchronous alias: '+name)
        return nets[name]['bits']
    def value(bit,assignment,seen=()):
        bit=canonical(bit)
        if bit in assignment:return assignment[bit]
        if bit in ('0','1'):return bit=='1'
        if bit in seen or bit not in drivers:raise ValueError('Unqualified reset cone root/loop')
        name,pin=drivers[bit];cell=cells[name]
        expression=functions.get((cell['type'],pin))
        if expression is None:raise ValueError('Reset cone reaches unqualified state/function')
        values={p:value(bs[0],assignment,(*seen,bit)) for p,bs in cell['connections'].items() if cell['port_directions'][p]=='input'}
        return boolean_function(expression,values)
    def root_check(pin,terms):
        # terms name each intended independent source and required polarity.
        bits=[canonical(bit) for bit,polarity in terms]
        if len(set(bits))!=len(bits):raise ValueError('Mixed reset root identities')
        for values in itertools.product((False,True),repeat=len(bits)):
            expected=all(v==polarity for v,(_,polarity) in zip(values,terms))
            if value(pin,dict(zip(bits,values)))!=expected:raise ValueError('Wrong reset root expression')
    def scalar(name):return net(name,1)[0]
    def toggle_bit(name):
        row=nets.get(name,{})
        # OpenROAD trims unused high output bits. Bit 1 must still have an
        # unambiguous zero-based vector identity; never accept a scalar alias.
        if row.get('offset',0)!=0 or row.get('upto',0)!=0 or not 2<=len(row.get('bits',[]))<=16:
            raise ValueError('Missing/mixed toggle-reset bit identity')
        return row['bits'][1]
    def pair(first,second,clock,reset=True):
        a,b=(cells[n]['connections'] for n in (first,second))
        if (clocks[canonical(a['CLK'][0])]!=clock or clocks[canonical(b['CLK'][0])]!=clock or
                canonical(a['RN'][0])!=canonical(b['RN'][0]) or canonical(b['D'][0])!=canonical(a['Q'][0])):
            raise ValueError('Wrong asynchronous chain clock/reset/next-state')
        if loads.get(canonical(a['Q'][0]))!=[second+'/D'] or canonical(a['Q'][0]) in output_bits:
            raise ValueError('Asynchronous first stage leaks or bypasses second stage')
        if reset and canonical(a['D'][0])!='1':raise ValueError('Reset release first stage is not constant one')
    usb_clock='usbClock' if top=='Usb' else 'clk';prefix='engine.' if top=='Usb' else ''
    samplers=[];exempt={}
    for port,bank in [('dpRx','dp_q'),('dnRx','dn_q')]:
        bits=net(prefix+'sie.u_phy_rx.'+bank,3);names=[register(b) for b in reversed(bits)]
        pair(names[0],names[1],usb_clock,False)
        # The second stage is also an intentional edge-detector input; only
        # the first stage must have no consumers except the following stage.
        last=cells[names[2]]['connections'];middle=cells[names[1]]['connections']
        if (canonical(last['D'][0])!=canonical(middle['Q'][0]) or clocks[canonical(last['CLK'][0])]!=usb_clock or
                canonical(last['RN'][0])!=canonical(middle['RN'][0])):
            raise ValueError('Wrong PHY third sampler stage')
        if canonical(cells[names[0]]['connections']['D'][0])!=ports[port]['bits'][0]:raise ValueError('Wrong raw pad source')
        root_check(cells[names[0]]['connections']['RN'][0],[(scalar(prefix+'_release_released'),True)])
        samplers.append(dict(source=port,first=names[0],second=names[1],third=names[2],clock=usb_clock))
        exempt[names[0]+'/D']=dict(kind='sampler',sources=[port])
    if top=='Usb':
        first=net('resume.pins.metastable',2)
        for port,offset in [('dpRx',0),('dnRx',1)]:
            a=register(first[offset]);targets=loads.get(canonical(first[offset]),[])
            if len(targets)!=1 or not targets[0].endswith('/D'):raise ValueError('Resume first sampler is not isolated')
            b=targets[0][:-2];register(cells[b]['connections']['Q'][0]);pair(a,b,usb_clock,False)
            if canonical(cells[a]['connections']['D'][0])!=ports[port]['bits'][0]:raise ValueError('Wrong resume pad source')
            root_check(cells[a]['connections']['RN'][0],[(scalar('_usbUp_r_released'),True)])
            samplers.append(dict(source=port,first=a,second=b,clock=usb_clock));exempt[a+'/D']=dict(kind='sampler',sources=[port])
    reset_names={prefix+n:usb_clock for n in ('release_0.first','inRelease.first','outRelease.first')}
    if top=='Usb':
        reset_names.update({'appUp_r.first':'appClock','usbUp_r.first':'usbClock','aonUp_r.first':'aonClock'})
        reset_names.update({f'{fifo}.{side}.first':clock for fifo in ('tx','rx','snapshot','events')
            for side,clock in ([('wr','appClock'),('rd','usbClock')] if fifo=='tx' else [('wr','usbClock'),('rd','appClock')])})
    if {n for n in nets if n.endswith('.first')}!=set(reset_names):raise ValueError('Incomplete reset-release alias inventory')
    chains=[]
    for alias,clock in sorted(reset_names.items()):
        first=register(net(alias,1)[0]);targets=loads.get(canonical(cells[first]['connections']['Q'][0]),[])
        if len(targets)!=1 or not targets[0].endswith('/D'):raise ValueError('Reset first stage not isolated')
        second=targets[0][:-2];register(cells[second]['connections']['Q'][0]);pair(first,second,clock)
        if alias in ('appUp_r.first','usbUp_r.first'):
            terms=[(ports[p]['bits'][0],True) for p in ('appReset_n','usbReset_n')]
        elif alias=='aonUp_r.first':terms=[(ports['aonReset_n']['bits'][0],True)]
        elif alias==prefix+'release_0.first':
            terms=([(scalar('_usbUp_r_released'),True),(scalar('enabledUsb'),True)] if top=='Usb' else [(ports['reset_n']['bits'][0],True)])+[(ports['vbus']['bits'][0],True)]
        elif alias in (prefix+'inRelease.first',prefix+'outRelease.first'):
            terms=[(scalar(prefix+'_release_released'),True),(scalar('_engine_configured' if top=='Usb' else 'configured'),True),
                   (scalar(prefix+'_sie_bus_reset_o'),False),(scalar(prefix+'_control_sessionFlush'),False),
                   (toggle_bit(prefix+'_control_'+('inToggleReset' if alias.endswith('inRelease.first') else 'outToggleReset')),False)]
        else:
            fifo=alias.split('.')[0];terms=[(scalar('_appUp_r_released'),True),(scalar('_usbUp_r_released'),True)]
            if fifo!='events':terms.append((scalar('_engine_'+{'tx':'txReset','rx':'rxReset','snapshot':'sessionReset'}[fifo]),False))
        root_check(cells[first]['connections']['RN'][0],terms)
        chains.append(dict(alias=alias,first=first,second=second,clock=clock))
        for name in (first,second):exempt[name+'/RN']=dict(kind='reset-release',alias=alias)
    root_aliases={prefix+'release_0.first':prefix+'_release_released',
                  prefix+'inRelease.first':prefix+'_inRelease_released',prefix+'outRelease.first':prefix+'_outRelease_released'}
    if top=='Usb':root_aliases.update({name+'_r.first':'_'+name+'_r_released' for name in ('appUp','usbUp','aonUp')})
    for row in chains:
        if row['alias'] in root_aliases and canonical(scalar(root_aliases[row['alias']]))!=canonical(cells[row['second']]['connections']['Q'][0]):
            raise ValueError('Declared release root differs from discovered second-stage Q')
    # Every raw pad load must be one of the declared first sampler D pins.
    for port in ('dpRx','dnRx'):
        if set(loads.get(ports[port]['bits'][0],[]))!={n for n,r in exempt.items() if r.get('sources')==[port]}:
            raise ValueError('Raw pad bypasses qualified first stages')
    # Independent endpoint inventory, before querying STA. Stop at register
    # pins; asynchronous peer-domain captures remain explicitly accounted for.
    fanout={}
    for name,c in cells.items():
        for pin,bits in c['connections'].items():
            if c['port_directions'][pin]=='input':
                for bit in bits:fanout.setdefault(bit,[]).append((name,pin))
    def downstream(first):
        todo=list(cells[first]['connections']['Q']);seen=set();endpoints={}
        source_clock=clocks[canonical(cells[first]['connections']['CLK'][0])]
        while todo:
            bit=todo.pop()
            if bit in seen:continue
            seen.add(bit)
            for name,pin in fanout.get(bit,[]):
                c=cells[name]
                if 'CLK' in c['connections']:
                    if pin not in ('D','RN','SETN'):raise ValueError('Unexpected downstream clock/control sink')
                    target_clock=clocks.get(canonical(c['connections']['CLK'][0]))
                    if not target_clock:raise ValueError('Unknown downstream domain')
                    endpoints[name+'/'+pin]=dict(clock=target_clock,relation='same-clock' if source_clock==target_clock else 'asynchronous-peer')
                else:todo.extend(b for p,bs in c['connections'].items() if c['port_directions'][p]=='output' for b in bs)
        return endpoints
    for row in [*samplers,*chains]:row['downstream']=downstream(row['second'])
    return dict(status='structurally-qualified',top=top,samplers=samplers,reset_chains=chains,sinks=exempt,
        recurrence='For each checked reset pair: reset low => both Q=0 asynchronously; on each local rising edge with reset high, first=1 and second=previous first. No first-stage leakage. Analog resolution excluded.')


def negative_controls(module,top,good,functions):
    results={};sample=good['samplers'][0];chain=good['reset_chains'][0]
    for fault in ('pad-bypass','sampler-clock','sampler-reset','reset-bypass','reset-constant','reset-clock','first-leak','wrong-alias','reset-tied-high','reset-wrong-root','joint-release-alias'):
        bad=copy.deepcopy(module);cells=bad['cells'];a=cells[chain['first']]['connections'];b=cells[chain['second']]['connections']
        if fault=='pad-bypass':cells[sample['second']]['connections']['D']=bad['ports'][sample['source']]['bits'][:]
        elif fault=='sampler-clock':cells[sample['first']]['connections']['CLK']=bad['ports']['vbus']['bits'][:]
        elif fault=='sampler-reset':
            for name in (sample['first'],sample['second'],sample['third']):cells[name]['connections']['RN']=['1']
        elif fault=='reset-bypass':b['D']=['1']
        elif fault=='reset-constant':a['D']=['0']
        elif fault=='reset-clock':a['CLK']=bad['ports']['vbus']['bits'][:]
        elif fault=='first-leak':bad['ports']['fault_output']=dict(direction='output',bits=a['Q'][:])
        elif fault=='wrong-alias':bad['netnames'][chain['alias']]['bits']=b['Q'][:]
        elif fault=='joint-release-alias':
            alias=('engine.' if top=='Usb' else '')+'_release_released'
            old=bad['netnames'][alias]['bits'][0];new=bad['ports']['vbus']['bits'][0]
            bad['netnames'][alias]['bits']=[new]
            for cell in cells.values():
                for pin,bits in cell['connections'].items():
                    if cell['port_directions'][pin]=='input':cell['connections'][pin]=[new if bit==old else bit for bit in bits]
        else:a['RN']=b['RN']=['1'] if fault=='reset-tied-high' else bad['ports']['dpRx']['bits'][:]
        try:inventory(bad,top,functions)
        except ValueError:results[fault]='fault_rejected'
        else:raise ValueError('Asynchronous topology fault escaped: '+fault)
    return results


def split_violations(rows,qualified):
    if qualified.get('status')!='pass':raise ValueError('Unqualified asynchronous boundary')
    retained=[];diagnostic=[]
    for row in rows:
        sink=qualified['inventory']['sinks'].get(row['end']);check=row['check']
        eligible=(sink and ((sink['kind']=='sampler' and check.startswith('hold/') and row['start'] in sink['sources']) or
                           (sink['kind']=='reset-release' and check.startswith('reset/'))))
        (diagnostic if eligible else retained).append(dict(row))
    return retained,diagnostic


def expected_checks(bound):
    rows=[]
    for kind,group in [('sampler',bound['samplers']),('reset',bound['reset_chains'])]:
        for row in group:
            for mode in ('max_rise','max_fall','min_rise','min_fall'):
                rows.append((kind+'/interstage',mode,row['first']+'/Q',row['second']+'/D'))
            for endpoint,relation in sorted(row['downstream'].items()):
                if relation['relation']!='same-clock':continue
                modes=('max_rise','max_fall','min_rise','min_fall') if endpoint.endswith('/D') else ('max_rise','min_rise')
                rows.extend((kind+'/downstream',mode,row['second']+'/Q',endpoint) for mode in modes)
    if len(rows)!=len(set(rows)):raise ValueError('Duplicate asynchronous timing obligation')
    return rows


def audit_checks(rows,expected):
    observed=[tuple(row[k] for k in ('kind','mode','start','end')) for row in rows]
    if len(observed)!=len(set(observed)) or set(observed)!=set(expected):
        raise ValueError('Missing/duplicate/mixed asynchronous timing endpoint or polarity')


def qualify(output,top,module,timing_tcl,run):
    """Run explicit interstage/downstream checks without modifying any SDC."""
    destination=output/'async-boundary';destination.mkdir(exist_ok=False)
    liberty=re.search(r'set liberty \{([^}]+)\}',timing_tcl.read_text())
    if not liberty:raise ValueError('Missing bound Liberty')
    functions=logic_functions(liberty[1]);bound=inventory(module,top,functions);faults=negative_controls(module,top,bound,functions)
    expected=expected_checks(bound)
    script=destination/'check.tcl'
    script.write_text(f'source {{{timing_tcl}}}\n'+
        f'set result [open {{{destination}/checks.tsv}} w]\nputs $result "kind\\tmode\\tstart\\tend\\tslack_ns"\n'+
        'foreach {kind mode first second} {'+' '.join(' '.join(row) for row in expected)+'} {\n'+
        ' set paths [find_timing_paths -from [get_pins $first] -to [get_pins $second] -path_delay $mode -group_path_count 1]\n'+
        ' if {[llength $paths]!=1} {error "Missing asynchronous endpoint/polarity: $first $second $mode"}\n'+
        ' foreach path $paths {puts $result "$kind\\t$mode\\t[get_full_name [get_property $path startpoint]]\\t[get_full_name [get_property $path endpoint]]\\t[get_property $path slack]"}\n'+
        '}\nclose $result\nputs USB_ASYNC_QUALIFICATION_COMPLETE\n')
    log=run(['sta','-no_init','-exit',str(script)],output,'async-boundary')
    if 'USB_ASYNC_QUALIFICATION_COMPLETE' not in log or re.search(r'(?im)^Error:',log):raise ValueError('Incomplete asynchronous timing')
    with (destination/'checks.tsv').open() as stream:rows=list(csv.DictReader(stream,delimiter='\t'))
    audit_checks(rows,expected)
    for row in rows:row['slack_ns']=float(row['slack_ns'])
    failed=[r for r in rows if not __import__('math').isfinite(r['slack_ns']) or r['slack_ns']<0]
    result=dict(status='fail' if failed else 'pass',inventory=bound,negative_controls=faults,expected_checks=expected,checks=rows,failures=failed,
        model_sha256=hashlib.sha256(json.dumps(module,sort_keys=True).encode()).hexdigest(),
        source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),timing_tcl,Path(liberty[1]))},
        artifact_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (script,destination/'checks.tsv',output/'async-boundary.log')},
        qualification='D77 digital structure/recurrence and interstage/downstream STA only. Raw asynchronous rows retained; pad/board, reset pulse/glitch and analog metastability remain tape-out debt.')
    (destination/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
