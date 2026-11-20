"""D45 source/mapped enable, cadence-step and reset-cone certificate.

All sequential Q values are independent inputs for local implication proofs.
Reset-safe temporal cadence is composed with the source-bound external receipt.
"""
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def aliases(module):
    result = {}
    for name, net in module['netnames'].items():
        if '$' in name:
            continue
        for index, bit in enumerate(net['bits']):
            if isinstance(bit, int):
                result.setdefault(bit, set()).add((name, index + net.get('offset', 0)))
    return result


def eligible_name(top, name):
    if top=='Usb':
        if not name.startswith('engine.'):return False
        return eligible_name('UsbEngine',name[len('engine.'):])
    if top == 'UsbControl':
        local = name
    elif top in ('UsbEngine','UsbSieTiming'):
        if name.startswith('sie.') and name.count('.') == 1:
            return name.endswith('_q')
        if not name.startswith('control.'):
            return False
        local = name[len('control.'):]
    else:
        raise ValueError('D45 unsupported top')
    return bool(re.fullmatch(r'header_[0-7]|descriptorLength|decode(?:Valid|Reply|Length|Pending|Value)Q', local))


def bind_pins(module, certified):
    """Only the exact scalar Q/D pins of the enumerated mapped FF qualify."""
    for name, pins in certified.items():
        cell = module['cells'].get(name)
        if not cell or not re.fullmatch(r'gf180mcu_fd_sc_mcu7t5v0__dff(?:rn|sn)?q_[124]', cell['type']):
            raise ValueError('Unrecognized certified mapped register')
        if pins != {'launch': name + '/Q', 'capture': name + '/D'}:
            raise ValueError('Wrongly classified register pin')
        if any(len(cell['connections'].get(p, [])) != 1 for p in ('Q', 'D', 'CLK')):
            raise ValueError('Non-scalar certified register')


def _enable_certificate(top, sources, mapped, liberty, output, cadence_receipt=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    receipt = dict(status='failed', top=top, sources={str(p): sha(p) for p in sources},
                   mapped_sha256=sha(mapped), library_sha256=sha(liberty),
                   abstraction='All register Q values free; asynchronous reset not a data-path exception',
                   certified={}, full_rate=[], source_registers=[])

    def yosys(name, script, negative=False):
        path = output / (name + '.ys')
        path.write_text(script + '\n')
        run = subprocess.run(['yosys', '-Q', '-T', '-s', str(path)], text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
        (output / (name + '.log')).write_text(run.stdout)
        if negative:
            if run.returncode != 1 or 'proof did fail' not in run.stdout:
                raise ValueError('Negative enable control did not fail')
        elif run.returncode or ('sat ' in script and 'SUCCESS!' not in run.stdout):
            raise ValueError('Certificate failed: ' + name)

    def pin_fault(name, cell_name, pin, monitor, value, extra=''):
        # Rewire an actual mapped FF pin, then extract that mutated pin into
        # the same cutpoint monitor used by the positive certificate.
        faulty_module=copy.deepcopy(module)
        faulty_module['cells'][cell_name]['connections'][pin]=value
        (output/(name+'-mapped.json')).write_text(json.dumps({'modules':{top:faulty_module}}))
        faulty_model=copy.deepcopy(model)
        faulty_model['cells']['$'+monitor]['connections']['A']=faulty_module['cells'][cell_name]['connections'][pin]
        (output/(name+'-cut.json')).write_text(json.dumps({'modules':{top:faulty_model}}))
        yosys(name,'\n'.join([f'read_liberty -ignore_miss_func {liberty}',
            f'read_json {output}/{name}-cut.json',f'hierarchy -check -top {top}',
            'flatten','proc','opt_clean','check -assert','techmap','opt',
            f'sat -set-def-inputs {extra} -prove {monitor} 1 -verify']),negative=True)

    try:
        yosys('prepare', '\n'.join([
            f'read_slang --keep-hierarchy --top {top} -DSYNTHESIS ' + ' '.join(map(str, sources)),
            f'hierarchy -check -top {top}', 'proc', 'flatten', 'opt',
            f'write_json {output}/source.json']))
        source = json.loads((output / 'source.json').read_text())['modules'][top]
        names = aliases(source)
        model = copy.deepcopy(source)
        good_aliases = set()
        other_aliases = set()
        source_bits=[]
        source_sie_group={}
        assertions = []
        enable_name = 'bitEnable' if top == 'UsbControl' else ('engine.' if top=='Usb' else '')+'cadence.enable'
        enable = source['netnames'][enable_name]['bits']
        if len(enable)!=1 or enable[0] not in names:
            raise ValueError('Missing scalar protocol enable aliases')
        enable_aliases=names[enable[0]]
        model['ports']['certificate_enable'] = dict(direction='output', bits=enable)
        register_count = 0
        for name, cell in source['cells'].items():
            if 'latch' in cell['type']:
                raise ValueError('Latch in certificate source')
            if 'dff' not in cell['type']:
                continue
            pins = cell['connections']
            labels = set().union(*(names.get(q, set()) for q in pins['Q']))
            selected = any(eligible_name(top, n) for n, _ in labels)
            if selected:
                if cell['type'] not in ('$adffe', '$dffe') or int(cell['parameters']['EN_POLARITY'], 2) != 1:
                    raise ValueError('Candidate is not a positive-enabled register: ' + str(labels))
                port = f'en_{len(assertions)}'
                model['ports'][port] = dict(direction='output', bits=pins['EN'])
                assertions.append(port)
                good_aliases.update(labels)
                sie_prefix='engine.sie.' if top=='Usb' else 'sie.'
                is_sie=any(n.startswith(sie_prefix) and n.count('.')==sie_prefix.count('.') for n,_ in labels)
                for label in labels:source_sie_group[label]=is_sie
                source_bits.extend(names.get(q,set()) for q in pins['Q'])
                receipt['source_registers'].append(dict(cell=name, aliases=sorted(labels)))
            else:
                other_aliases.update(labels)
            model['ports'][f'q_{register_count}'] = dict(direction='input', bits=pins['Q'])
            register_count += 1
            del model['cells'][name]
        if not assertions or good_aliases & other_aliases:
            raise ValueError('Missing or mixed source register aliases')
        source_model = output / 'source-cut.json'
        source_model.write_text(json.dumps({'modules': {top: model}}))
        proof = ' '.join('-prove ' + p + ' 0' for p in assertions)
        yosys('source-proof', '\n'.join([f'read_json {source_model}', f'hierarchy -top {top}',
              'opt_clean', 'check -assert', 'techmap', 'opt',
              f'sat -set-def-inputs -set certificate_enable 0 {proof} -verify']))
        # Mutate the real prepared register, then extract its enable exactly as
        # in the positive case. Do not plant a failure in an assertion instead.
        mutant = copy.deepcopy(model)
        mutant_source = copy.deepcopy(source)
        first_cell=receipt['source_registers'][0]['cell']
        mutant_source['cells'][first_cell]['connections']['EN']=['1']
        (output/'always-enabled-source.json').write_text(json.dumps({'modules':{top:mutant_source}}))
        mutant['ports'][assertions[0]]['bits'] = mutant_source['cells'][first_cell]['connections']['EN']
        (output / 'always-enabled.json').write_text(json.dumps({'modules': {top: mutant}}))
        yosys('always-enabled', '\n'.join([f'read_json {output}/always-enabled.json',
              f'hierarchy -top {top}', 'opt_clean', 'techmap', 'opt',
              f'sat -set-def-inputs -set certificate_enable 0 {proof} -verify']), negative=True)

        mapped_design = json.loads(Path(mapped).read_text())
        module = mapped_design['modules'][top]
        from tools.timing.usb_enable_fanout import identities, prove_pair, PREFIX
        replica_bits = identities(module)
        if replica_bits:
            receipt['enable_replica_equivalence'] = dict(
                identities=replica_bits, proof=prove_pair(liberty,output/'enable-replicas'),
                scope='Actual D/CLK/RN/reset-value equality binds every physical copy to the proved common cadence; no phase shift')
            receipt['abstraction']='All other register Q values free; physical replica Q values constrained only by their independently proved equality to the original cadence FF'
        mapped_names = aliases(module)
        # Reject synthesis recoding or lost identity rather than guessing which
        # extra state bits inherited a source register's enable certificate.
        source_eligible_names={n for n,_ in good_aliases if eligible_name(top,n)}
        for bit,labels in mapped_names.items():
            unexpected={label for label in labels if label[0] in source_eligible_names and label not in good_aliases}
            if unexpected:
                raise ValueError('Recoded or ambiguous certified aliases: '+str(sorted(unexpected)))
        model = copy.deepcopy(module)
        enable_bits={bit for bit,labels in mapped_names.items() if labels & enable_aliases}
        if len(enable_bits)!=1:
            raise ValueError('Missing or ambiguous mapped protocol enable aliases')
        enable = list(enable_bits)
        model['ports']['certificate_enable'] = dict(direction='output', bits=enable)
        checks = []
        next_bit = 1 + max(b for net in module['netnames'].values() for b in net['bits'] if isinstance(b, int))
        for name, cell in module['cells'].items():
            pins = cell['connections']
            if 'CLK' not in pins:
                continue
            if 'dff' not in cell['type'] or len(pins.get('Q', [])) != 1:
                raise ValueError('Unsupported mapped sequential cell')
            labels = mapped_names.get(pins['Q'][0], set())
            matched = labels & good_aliases
            if matched:
                if labels & other_aliases:
                    raise ValueError('Mixed mapped register aliases: ' + name)
                receipt['certified'][name] = {'launch': name + '/Q', 'capture': name + '/D'}
                # Functional mapped hold proof. Liberty combinational cells stay
                # real, while every FF's Q is freed independently.
                port = f'hold_{len(checks)}'
                model['ports'][port] = dict(direction='output', bits=[next_bit])
                model['cells']['$certificate_' + port] = dict(type='$eq', parameters={'A_WIDTH':'1', 'B_WIDTH':'1',
                    'Y_WIDTH':'1', 'A_SIGNED':'0', 'B_SIGNED':'0'}, attributes={},
                    port_directions={'A':'input','B':'input','Y':'output'},
                    connections={'A':pins['D'], 'B':pins['Q'], 'Y':[next_bit]})
                next_bit += 1
                checks.append(port)
            else:
                receipt['full_rate'].append(name)
            model['ports']['free_' + name] = dict(direction='input', bits=pins['Q'])
            del model['cells'][name]
        if not checks:
            raise ValueError('No mapped certified registers')
        # Only the independently proved replica equalities are substituted in
        # the all-Q-free cut. Actual mapped identities/pins remain unmodified.
        if replica_bits:
            for c in model['cells'].values():
                c['connections']={p:[replica_bits.get(b,b) for b in bs] for p,bs in c['connections'].items()}
            for name in module['cells']:
                if name.startswith(PREFIX):del model['ports']['free_'+name]
        alias_to_bit={(n,index+net.get('offset',0)):bit for n,net in module['netnames'].items()
                      for index,bit in enumerate(net['bits'])}
        mapped_q={c['connections']['Q'][0]:n for n,c in module['cells'].items() if 'CLK' in c['connections'] and 'Q' in c['connections']}
        connected_bits={b for c in module['cells'].values() for bits in c['connections'].values() for b in bits}
        connected_bits.update(b for port in module['ports'].values() for b in port['bits'])
        receipt['eliminated_unused_source_bits']=[]
        for labels in source_bits:
            targets={alias_to_bit[label] for label in labels if label in alias_to_bit}
            if len(targets)!=1:
                raise ValueError('Missing or ambiguous source-to-mapped bit identity: '+str(sorted(labels)))
            target=next(iter(targets))
            if isinstance(target,int) and target not in connected_bits:
                receipt['eliminated_unused_source_bits'].append(sorted(labels))
                continue
            if isinstance(target,int) and mapped_q.get(target) not in receipt['certified']:
                raise ValueError('Certified source bit became an unclassified mapped register')
        # Every source-certified alias still present in mapped sequential state
        # must bind to a certified register; optimized constants need no timing.
        bind_pins(module, receipt['certified'])
        faulty = copy.deepcopy(receipt['certified'])
        first = next(iter(faulty))
        faulty[first]['capture'] = first + '/CLK'
        try:
            bind_pins(module, faulty)
        except ValueError:
            receipt['wrong_pin_rejected'] = True
        else:
            raise ValueError('Wrong pin escaped certificate')
        (output / 'mapped-cut.json').write_text(json.dumps({'modules': {top: model}}))
        yosys('mapped-proof', '\n'.join([f'read_liberty -ignore_miss_func {liberty}',
              f'read_json {output}/mapped-cut.json', f'hierarchy -check -top {top}',
              'flatten', 'proc', 'opt_clean', 'check -assert', 'techmap', 'opt',
              'sat -set-def-inputs -set certificate_enable 0 ' +
              ' '.join('-prove ' + p + ' 1' for p in checks) + ' -verify']))
        if top in ('UsbEngine','Usb','UsbSieTiming'):
            prefix=('engine.' if top=='Usb' else '')+'cadence.'
            actual=[p for p in sources if Path(p).name=='UsbBitEnable.sv']
            if len(actual)!=1:raise ValueError('Missing measured cadence emission')
            expected=sha(actual[0])
            matched=[]
            # Unused P is removed in the enable-only harness/standalone fixture.
            # Require the exact measured projection in a completed source-bound
            # proof; the actual mapped count/enable/reset equations are checked below.
            for role in ('cadence_reset','preenable_early'):
                case=cadence_receipt['cases'].get(role,{})
                if case.get('status')!='pass':continue
                if {j.get('result') for j in case.get('jobs',[])}!={'proved','covered','fault_rejected'}:continue
                if any(j['variant']=='correct' and j['source_sha256'].get('UsbBitEnable.sv')==expected for j in case['jobs']):matched.append(role)
            if not matched:raise ValueError('Measured cadence differs from proved production emissions')
            receipt['cadence_emission_proof_roles']=matched
            def translated(net):
                result=[]
                for bit in source['netnames'][net]['bits']:
                    targets={alias_to_bit[label] for label in names[bit] if label in alias_to_bit}
                    if len(targets)!=1:raise ValueError('Ambiguous cadence bit identity: '+net)
                    result.append(next(iter(targets)))
                return result
            count=translated(prefix+'count');ce=translated(prefix+'enable');reset=translated(prefix+'reset_n')
            if len(count)!=2 or len(ce)!=1 or len(reset)!=1:
                raise ValueError('Unexpected cadence width')
            clock=module['ports']['usbClock' if top=='Usb' else 'clk']['bits']
            cadence_checks=[]
            def equation(label,a,b):
                nonlocal next_bit
                port='cadence_'+label
                model['ports'][port]=dict(direction='output',bits=[next_bit])
                model['cells']['$'+port]=dict(type='$eq',parameters={'A_WIDTH':format(len(a),'b'),'B_WIDTH':format(len(b),'b'),
                    'Y_WIDTH':'1','A_SIGNED':'0','B_SIGNED':'0'},attributes={},
                    port_directions={'A':'input','B':'input','Y':'output'},connections={'A':a,'B':b,'Y':[next_bit]})
                next_bit+=1;cadence_checks.append(port)
            next_count=[next_bit,next_bit+1];next_bit+=2
            model['cells']['$cadence_next_count']=dict(type='$add',parameters={'A_WIDTH':'10','B_WIDTH':'10','Y_WIDTH':'10','A_SIGNED':'0','B_SIGNED':'0'},
                attributes={},port_directions={'A':'input','B':'input','Y':'output'},connections={'A':count,'B':['1','0'],'Y':next_count})
            next_enable=[next_bit];next_bit+=1
            model['cells']['$cadence_next_enable']=dict(type='$eq',parameters={'A_WIDTH':'10','B_WIDTH':'10','Y_WIDTH':'1','A_SIGNED':'0','B_SIGNED':'0'},
                attributes={},port_directions={'A':'input','B':'input','Y':'output'},connections={'A':count,'B':['1','1'],'Y':next_enable})
            for index,(q,want) in enumerate(zip(count+ce,next_count+next_enable)):
                cell=module['cells'][mapped_q[q]]
                if not re.fullmatch(r'gf180mcu_fd_sc_mcu7t5v0__dffrnq_[124]',cell['type']) or cell['connections']['CLK']!=clock:
                    raise ValueError('Cadence clock/reset polarity mismatch')
                equation('step'+str(index),cell['connections']['D'],[want])
                equation('reset'+str(index),cell['connections']['RN'],reset)
            (output/'cadence-cut.json').write_text(json.dumps({'modules':{top:model}}))
            yosys('cadence-mapped-step','\n'.join([f'read_liberty -ignore_miss_func {liberty}',
                f'read_json {output}/cadence-cut.json',f'hierarchy -check -top {top}','flatten','proc','opt_clean','check -assert','techmap','opt',
                'sat -set-def-inputs '+' '.join('-prove '+p+' 1' for p in cadence_checks)+' -verify']))
            pin_fault('wrong-cadence-step',mapped_q[ce[0]],'D','cadence_step2',['0'])
            pin_fault('wrong-cadence-reset',mapped_q[ce[0]],'RN','cadence_reset2',['1'])
            receipt['cadence_binding']=dict(status='pass',emitted_sha256=expected,
                mapped_registers=[mapped_q[q] for q in count+ce],clock=clock,reset=reset,
                proof='Mapped count increments modulo four and enable captures count==3; all three RN pins equal production reset; zero reset values')
        else:
            receipt['cadence_binding']=dict(status='external-contract',port='bitEnable',
                scope='Standalone EP0 timing is conditional on its production engine cadence certificate')
        # Certify the reset cone of every actual destination as well as its CE.
        # PHY bus_reset is still full-rate for timing; only its phase stability
        # is used to justify the retained SIE's asynchronous reset boundary.
        def reset_translate(net):
            targets={alias_to_bit[label] for bit in source['netnames'][net]['bits'] for label in names[bit] if label in alias_to_bit}
            if len(targets)!=1:raise ValueError('Missing/ambiguous reset identity: '+net)
            return [next(iter(targets))]
        base='engine.' if top=='Usb' else ''
        root_reset=reset_translate('reset_n' if top=='UsbControl' else base+'cadence.reset_n')
        sie_reset=None;reset_checks=[];bus_hold=[]
        def reset_equal(label,a,b):
            nonlocal next_bit
            port='reset_check_'+str(label)
            model['ports'][port]=dict(direction='output',bits=[next_bit])
            model['cells']['$'+port]=dict(type='$eq',parameters={'A_WIDTH':'1','B_WIDTH':'1','Y_WIDTH':'1','A_SIGNED':'0','B_SIGNED':'0'},
                attributes={},port_directions={'A':'input','B':'input','Y':'output'},connections={'A':a,'B':b,'Y':[next_bit]})
            next_bit+=1;return port
        if top!='UsbControl':
            bus_reset=reset_translate(base+'sie.bus_reset_o')
            bus_cell=module['cells'].get(mapped_q.get(bus_reset[0]))
            if not bus_cell or not re.fullmatch(r'gf180mcu_fd_sc_mcu7t5v0__dffrnq_[124]',bus_cell['type']):
                raise ValueError('Bus reset is not an identifiable registered zero-reset level')
            if bus_cell['connections']['CLK']!=clock:
                raise ValueError('Bus reset register clock differs from protocol cadence')
            bus_hold.append(reset_equal('bus_hold',bus_cell['connections']['D'],bus_cell['connections']['Q']))
            reset_checks.append(reset_equal('bus_root',bus_cell['connections']['RN'],root_reset))
            inverted=[next_bit];next_bit+=1;sie_reset=[next_bit];next_bit+=1
            model['cells']['$bus_reset_not']=dict(type='$not',parameters={'A_WIDTH':'1','Y_WIDTH':'1','A_SIGNED':'0'},attributes={},
                port_directions={'A':'input','Y':'output'},connections={'A':bus_reset,'Y':inverted})
            model['cells']['$sie_reset_and']=dict(type='$and',parameters={'A_WIDTH':'1','B_WIDTH':'1','Y_WIDTH':'1','A_SIGNED':'0','B_SIGNED':'0'},attributes={},
                port_directions={'A':'input','B':'input','Y':'output'},connections={'A':root_reset,'B':inverted,'Y':sie_reset})
        receipt['reset_groups']={}
        reset_fault_target=None
        for name in receipt['certified']:
            cell=module['cells'][name];pins=cell['connections']
            if 'RN' not in pins:
                if not re.fullmatch(r'gf180mcu_fd_sc_mcu7t5v0__dffq_[124]',cell['type']):
                    raise ValueError('Unsupported certified reset semantics')
                receipt['reset_groups'][name]='no async reset; writes only on enable'
                continue
            labels=mapped_names[pins['Q'][0]]
            origins={source_sie_group[label] for label in labels if label in source_sie_group}
            if len(origins)!=1:raise ValueError('Mixed reset ownership aliases')
            is_sie=next(iter(origins))
            expected=sie_reset if is_sie else root_reset
            if expected is None:raise ValueError('Unexpected SIE reset group')
            reset_checks.append(reset_equal(len(reset_checks),pins['RN'],expected))
            reset_fault_target=(name,reset_checks[-1])
            receipt['reset_groups'][name]='root & !registered_bus_reset' if is_sie else 'root'
        (output/'reset-cut.json').write_text(json.dumps({'modules':{top:model}}))
        prepare_reset=[f'read_liberty -ignore_miss_func {liberty}',f'read_json {output}/reset-cut.json',
            f'hierarchy -check -top {top}','flatten','proc','opt_clean','check -assert','techmap','opt']
        yosys('reset-cones','\n'.join(prepare_reset+['sat -set-def-inputs '+' '.join('-prove '+p+' 1' for p in reset_checks)+' -verify']))
        if reset_fault_target:
            pin_fault('wrong-certified-reset',reset_fault_target[0],'RN',reset_fault_target[1],['1'])
        if bus_hold:
            yosys('bus-reset-phase','\n'.join(prepare_reset+['sat -set-def-inputs -set certificate_enable 0 '+' '.join('-prove '+p+' 1' for p in bus_hold)+' -verify']))
            pin_fault('non-enabled-bus-reset',mapped_q[bus_reset[0]],'D',bus_hold[0],['1'],'-set certificate_enable 0')
        receipt.update(status='pass', negative_controls=['always-enabled', 'wrong-pin','wrong-certified-reset']+
            (['wrong-cadence-step','wrong-cadence-reset','non-enabled-bus-reset'] if top!='UsbControl' else []))
    except Exception as error:
        receipt['error'] = str(error)
    (output / 'result.json').write_text(json.dumps(receipt, indent=2) + '\n')
    if receipt['status'] != 'pass':
        raise ValueError(receipt.get('error', 'Enable certification failed'))
    return receipt


def _value_certificate(top, sources, mapped, liberty, output, cadence_receipt=None):
    """D48 conservative value invariant; no implicit reset exclusion.

    The local EN implication is stronger than a reachable-state value invariant
    for unreset registers: arbitrary Q/input values hold at every disabled edge,
    and there is no asynchronous state-changing pin. Resettable registers need
    an additional reset-inclusive invariant; the old D45 reset-cone check is
    not that invariant. Keep them full-rate until it exists.
    """
    receipt = _enable_certificate(top, sources, mapped, liberty, output, cadence_receipt)
    output = Path(output)
    receipt['status'] = 'pending-value-qualification'
    (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    module = json.loads(Path(mapped).read_text())['modules'][top]
    before = copy.deepcopy(receipt['certified'])
    retained = {}
    rejected = {}
    for name, pins in before.items():
        cell = module['cells'][name]
        if cell['type'].startswith('gf180mcu_fd_sc_mcu7t5v0__dffq_'):
            retained[name] = pins
        else:
            rejected[name] = 'Reset-inclusive value invariant not established; D45 enable/reset-cone proof alone is insufficient'
    receipt['previous_d45_certified'] = before
    receipt['certified'] = retained
    receipt['full_rate'] = sorted(set(receipt['full_rate']) | set(rejected))
    receipt['value_stability'] = dict(
        decision='D48/D49', status='conservative-subset',
        proof='All-state source EN implies common enable, mapped D equals Q when disabled, and certified cells have no asynchronous state-changing pin',
        reset_scope='No reset assertion/release masking; unreset certified state holds even when reset inputs change',
        rejected_previous=rejected,
        additional_phy='Not certified: retained PHY state has asynchronous reset or genuinely sample-rate updates; no reset-inclusive invariant is established')
    # A release-only enable on a real certified source register must fail the
    # same implication. This models an early write on release, not a weakened
    # monitor or an assumed reset phase. Existing negative controls still run.
    source = json.loads((output/'source.json').read_text())['modules'][top]
    cut = json.loads((output/'source-cut.json').read_text())
    chosen = next((i for i, row in enumerate(receipt['source_registers'])
                   if source['cells'][row['cell']]['type'] == '$dffe'), None)
    if chosen is not None:
        mutant = copy.deepcopy(cut)
        mutant_source = copy.deepcopy(source)
        root = 'reset_n' if top != 'Usb' else 'usbReset_n'
        actual = mutant_source['cells'][receipt['source_registers'][chosen]['cell']]
        actual['connections']['EN'] = source['ports'][root]['bits']
        (output/'early-reset-release-source.json').write_text(json.dumps({'modules':{top:mutant_source}}))
        mutant['modules'][top]['ports'][f'en_{chosen}']['bits'] = actual['connections']['EN']
        bm=mutant['modules'][top];q=actual['connections']['Q'];width=len(q)
        first=1+max(b for net in source['netnames'].values() for b in net['bits'] if isinstance(b,int))
        next_q=list(range(first,first+width));held=first+width
        bm['cells']['$release_fault_next']=dict(type='$mux',parameters={'WIDTH':format(width,'b')},attributes={},
            port_directions={'A':'input','B':'input','S':'input','Y':'output'},
            connections={'A':q,'B':actual['connections']['D'],'S':actual['connections']['EN'],'Y':next_q})
        bm['cells']['$release_fault_hold']=dict(type='$eq',parameters={'A_WIDTH':format(width,'b'),'B_WIDTH':format(width,'b'),
            'Y_WIDTH':'1','A_SIGNED':'0','B_SIGNED':'0'},attributes={},
            port_directions={'A':'input','B':'input','Y':'output'},connections={'A':q,'B':next_q,'Y':[held]})
        bm['ports']['release_value_hold']=dict(direction='output',bits=[held])
        model_path = output/'early-reset-release.json'
        model_path.write_text(json.dumps(mutant))
        script = output/'early-reset-release.ys'
        script.write_text('\n'.join([f'read_json {model_path}', f'hierarchy -top {top}',
            'opt_clean', 'check -assert', 'techmap', 'opt',
            f'sat -set-def-inputs -set certificate_enable 0 -set {root} 1 -prove release_value_hold 1 -verify'])+'\n')
        run = subprocess.run(['yosys','-Q','-T','-s',str(script)],capture_output=True,text=True,timeout=120)
        (output/'early-reset-release.log').write_text(run.stdout+run.stderr)
        if run.returncode != 1 or 'proof did fail' not in run.stdout+run.stderr:
            raise ValueError('Early reset-release enable fault escaped')
        receipt['negative_controls'].append('early-reset-release')
        # Value-level fault: mutate the actual prepared register to toggle
        # without CE, then check its extracted next value against its Q.
        bad_source = copy.deepcopy(source)
        actual = bad_source['cells'][receipt['source_registers'][chosen]['cell']]
        q = actual['connections']['Q'];width=len(q)
        first = 1+max(b for net in source['netnames'].values() for b in net['bits'] if isinstance(b,int))
        inverted=list(range(first,first+width));held=first+width
        invert=dict(type='$not',parameters={'A_WIDTH':format(width,'b'),'Y_WIDTH':format(width,'b'),'A_SIGNED':'0'},
            attributes={},port_directions={'A':'input','Y':'output'},connections={'A':q,'Y':inverted})
        actual['connections']['EN']=['1'];actual['connections']['D']=inverted
        bad_source['cells']['$fault_toggle']=invert
        (output/'non-enable-value-change-source.json').write_text(json.dumps({'modules':{top:bad_source}}))
        bad=copy.deepcopy(cut);bm=bad['modules'][top]
        bm['cells']['$fault_toggle']=invert
        bm['cells']['$fault_hold']=dict(type='$eq',parameters={'A_WIDTH':format(width,'b'),'B_WIDTH':format(width,'b'),
            'Y_WIDTH':'1','A_SIGNED':'0','B_SIGNED':'0'},attributes={},
            port_directions={'A':'input','B':'input','Y':'output'},connections={'A':actual['connections']['D'],'B':q,'Y':[held]})
        bm['ports']['mutated_value_hold']=dict(direction='output',bits=[held])
        p=output/'non-enable-value-change.json';p.write_text(json.dumps(bad))
        script=output/'non-enable-value-change.ys'
        script.write_text('\n'.join([f'read_json {p}',f'hierarchy -top {top}','opt_clean','check -assert','techmap','opt',
            'sat -set-def-inputs -set certificate_enable 0 -prove mutated_value_hold 1 -verify'])+'\n')
        run=subprocess.run(['yosys','-Q','-T','-s',str(script)],capture_output=True,text=True,timeout=120)
        (output/'non-enable-value-change.log').write_text(run.stdout+run.stderr)
        if run.returncode!=1 or 'proof did fail' not in run.stdout+run.stderr:
            raise ValueError('Non-enable value-change fault escaped')
        receipt['negative_controls'].append('non-enable-value-change')
    bind_pins(module, retained)
    if retained:
        faulty=copy.deepcopy(retained);first=next(iter(faulty))
        faulty[first]['capture']=first+'/CLK'
        try:bind_pins(module,faulty)
        except ValueError:receipt['value_stability']['wrong_retained_pin_rejected']=True
        else:raise ValueError('Wrong retained D48 pin escaped')
    receipt['status'] = 'pass'
    (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


def certify(top, sources, mapped, liberty, output, cadence_receipt=None, equivalence=None):
    try:
        receipt = _value_certificate(top, sources, mapped, liberty, output, cadence_receipt)
        receipt['status']='pending-reset-aware-qualification'
        (Path(output)/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
        from hw.ip.usb.formal.reset_certificate import extend
        receipt=extend(top,mapped,liberty,output,receipt,cadence_receipt)
        return pre_enable_certificate(top,sources,mapped,liberty,output,receipt,cadence_receipt,equivalence)
    except Exception as error:
        path = Path(output)/'result.json'
        if path.exists():
            receipt = json.loads(path.read_text())
            receipt.update(status='failed', error=str(error))
            path.write_text(json.dumps(receipt,indent=2)+'\n')
        raise


def pre_enable_certificate(top,sources,mapped,liberty,output,receipt,cadence,equivalence):
    """D58 P captures; D51 S launches remain single-cycle, including into P."""
    if top not in ('UsbEngine','Usb'):return receipt
    from hw.ip.usb.formal.preenable_equivalence import FLAGS
    from hw.ip.usb.formal.reset_certificate import Cut
    output=Path(output);prefix='engine.' if top=='Usb' else ''
    source=json.loads((output/'source.json').read_text())['modules'][top]
    if prefix+'cadence.preEnable' not in source['netnames']:return receipt
    if not equivalence or equivalence.get('status')!='pass' or equivalence.get('real_consumer_control')!='fault_rejected':raise ValueError('Missing D58 equivalence')
    role='usb' if top=='Usb' else 'engine'
    if equivalence['blocks'][role]['emission_sha256']['after']!={Path(p).name:sha(p) for p in sources}:
        raise ValueError('D58 equivalence emission mismatch')
    for name,expected in equivalence['production_source_sha256'].items():
        if sha(name)!=expected:raise ValueError('Stale equivalence source '+name)
    measured_cadence=[p for p in sources if Path(p).name=='UsbBitEnable.sv']
    if len(measured_cadence)!=1:raise ValueError('Missing full P cadence emission')
    expected_cadence=sha(measured_cadence[0])
    for role in ('preenable_early','preenable_late','preenable_reset','preenable_write'):
        c=cadence.get('cases',{}).get(role,{})
        if c.get('status')!='pass' or {j.get('result') for j in c.get('jobs',[])}!={'proved','covered','fault_rejected'}:
            raise ValueError('Missing D58 phase/reset proof '+role)
        if any(j['source_sha256'].get('UsbBitEnable.sv')!=expected_cadence for j in c['jobs'] if j['variant']!='corrupt'):
            raise ValueError('D58 phase proof uses a different cadence')
    mapped_module=json.loads(Path(mapped).read_text())['modules'][top]
    snames=aliases(source);mnames=aliases(mapped_module)
    flags={prefix+n for n in FLAGS};good=set();other=set();source_bits=[];selected=[]
    for name,c in source['cells'].items():
        if 'dff' not in c['type']:continue
        labels=set().union(*(snames.get(b,set()) for b in c['connections']['Q']))
        if any(n in flags for n,_ in labels):
            good.update(labels);source_bits.extend(c['connections']['Q']);selected.append(name)
        else:other.update(labels)
    if {n for n,_ in good}&flags!=flags or good&other:raise ValueError('Missing/mixed P source aliases')
    alias_bits={}
    for bit,labels in mnames.items():
        for label in labels:alias_bits.setdefault(label,set()).add(bit)
    def identity(name):
        values=[]
        for bit in source['netnames'][name]['bits']:
            candidates=set().union(*(alias_bits.get(a,set()) for a in snames[bit]))
            if len(candidates)!=1:raise ValueError('Missing/ambiguous P identity '+name)
            values.extend(candidates)
        return values
    found=set();mapped_selected=[]
    for name,c in mapped_module['cells'].items():
        if 'CLK' not in c['connections']:continue
        labels=mnames.get(c['connections']['Q'][0],set())
        if labels&good:
            if labels&other:raise ValueError('Mixed P mapped aliases')
            found.update(labels&good);mapped_selected.append(name)
    for bit in source_bits:
        if not snames[bit]&found:raise ValueError('Missing P source/mapped register binding')
    pins={n:dict(launch=n+'/Q',capture=n+'/D') for n in mapped_selected}
    bind_pins(mapped_module,pins)
    def prepare(mod,names,mapped_view):
        cut=Cut(mod)
        ident=identity if mapped_view else lambda n:source['netnames'][n]['bits']
        pre=ident(prefix+'cadence.preEnable');root=ident(prefix+'cadence.reset_n')
        count=ident(prefix+'cadence.count');clk=mod['ports']['usbClock' if top=='Usb' else 'clk']['bits']
        if len(pre)!=1 or len(count)!=2 or len(root)!=1:raise ValueError('Bad P cadence geometry')
        cut.m['ports']['p_enable']=dict(direction='output',bits=pre)
        strobe=[n for n,c in mod['cells'].items() if c['connections'].get('Q')==pre]
        if len(strobe)!=1:raise ValueError('Missing physical P strobe register')
        for n,c in list(mod['cells'].items()):
            is_ff=('CLK' in c['connections']) if mapped_view else ('dff' in c['type'])
            if not is_ff:continue
            q=c['connections']['Q'];cp=c['connections']
            if n in names or n==strobe[0]:
                if mapped_view:
                    bind_pins(mod,{n:dict(launch=n+'/Q',capture=n+'/D')})
                    if 'RN' not in cp or 'SETN' in cp:raise ValueError('P requires zero-reset FF')
                    cut.equal('reset',cp['RN'],root)
                    nxt=cp['D']
                else:
                    if c['type'] not in ('$adffe','$adff') or int(c['parameters']['ARST_VALUE'],2)!=0 or int(c['parameters']['CLK_POLARITY'],2)!=1:
                        raise ValueError('Unsupported P source state')
                    expected=root if int(c['parameters']['ARST_POLARITY'],2)==0 else cut.gate('$not',{'A':root})
                    cut.equal('reset',cp['ARST'],expected)
                    nxt=cp['D']
                    if 'EN' in cp:
                        if int(c['parameters']['EN_POLARITY'],2)!=1:raise ValueError('Inverted P enable')
                        nxt=cut.gate('$mux',{'A':q,'B':nxt,'S':cp['EN']},len(q))
                cut.equal('reset',cp['CLK'],clk)
                if n in names:cut.equal('normal',nxt,q)
                else:cut.equal('reset',nxt,cut.gate('$eq',{'A':count,'B':['0','1']}))
            cut.free(n,c)
        return cut
    def prove(name,cut,mapped_view=False,negative=False):
        path=output/(name+'.json');path.write_text(json.dumps({'modules':{top:cut.m}}))
        commands=([f'read_liberty -ignore_miss_func {liberty}'] if mapped_view else [])+[f'read_json {path}',f'hierarchy -check -top {top}','flatten','proc','check -assert','techmap','opt']
        for group in ('normal','reset'):
            if cut.checks[group]:commands.append('sat -set-def-inputs '+('-set p_enable 0 ' if group=='normal' else '')+' '.join('-prove '+p+' 1' for p in cut.checks[group])+' -verify')
        script=output/(name+'.ys');script.write_text('\n'.join(commands)+'\n')
        r=subprocess.run(['yosys','-Q','-T','-s',str(script)],capture_output=True,text=True,timeout=120)
        (output/(name+'.log')).write_text(r.stdout+r.stderr)
        if (r.returncode!=1 or 'proof did fail' not in r.stdout+r.stderr) if negative else r.returncode!=0:
            raise ValueError('D58 source/mapped proof failed '+name)
    prove('pre-source',prepare(source,selected,False))
    prove('pre-mapped',prepare(mapped_module,mapped_selected,True),True)
    mutant=copy.deepcopy(source);mutant['cells'][selected[0]]['connections']['EN']=['1']
    prove('pre-always-write',prepare(mutant,selected,False),negative=True)
    wrong_bits=set(identity(prefix+'control.outData'))
    wrong_register=next(n for n,c in mapped_module['cells'].items() if 'CLK' in c['connections'] and c['connections']['Q'][0] in wrong_bits)
    prove('pre-wrong-register',prepare(mapped_module,mapped_selected+[wrong_register],True),True,True)
    wrong=copy.deepcopy(pins);first=next(iter(wrong));wrong[first]['capture']=first+'/CLK'
    try:bind_pins(mapped_module,wrong)
    except ValueError:pass
    else:raise ValueError('Wrong P mapped pin accepted')
    receipt['pre_enable']=dict(status='pass',capture_pins=pins,source_registers=selected,
        allowed_launch_groups=['R','B','H'],single_cycle_launch_groups=['S'],
        setup=3,hold=2,budget_ns=37.5,
        proof='Actual source/mapped hold when P low, common reset and clock, P D=count==2; reset-safe R/B/H three-edge spacing composed with source-bound temporal proof and whole engine/wrapper equivalence',
        negative_controls=['always-write','wrong-capture-pin','wrong-register'],equivalence_sha256=hashlib.sha256(json.dumps(equivalence,sort_keys=True).encode()).hexdigest())
    (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt
