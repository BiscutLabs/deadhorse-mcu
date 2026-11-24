"""Audit the digital threshold endpoint; no analog timing is substituted."""


def threshold_driver(module, bits, mapped=False):
    if len(bits) != 2 or bits[1] != '0' or type(bits[0]) is not int:
        raise ValueError('Threshold must be one live bit and a constant zero MSB')
    if module['netnames']['digital.subsystem.powerReset.threshold']['bits'] != bits:
        raise ValueError('Threshold is not the production power/reset output')
    drivers=[]
    for name, cell in module['cells'].items():
        for pin, values in cell['connections'].items():
            if cell['port_directions'][pin] == 'output' and bits[0] in values:
                drivers.append((name,cell,pin))
    if len(drivers) != 1:
        raise ValueError('Missing or ambiguous threshold driver')
    name,cell,pin=drivers[0]
    if pin != 'Q' or cell['connections']['Q'] != [bits[0]]:
        raise ValueError('Threshold is not directly registered')
    allowed=('gf180mcu_fd_sc_mcu7t5v0__dffrnq_1',) if mapped else ('$adff','$adffe','$aldff')
    if cell['type'] not in allowed:
        raise ValueError('Unapproved threshold storage '+cell['type'])
    if cell['type'] == '$aldff':
        # The pinned slang frontend can represent an async clear as async
        # load with constant-zero data before opt_dff normalizes the cell.
        parameters=cell.get('parameters',{})
        if (cell['connections'].get('AD') != ['0'] or
                any(parameters.get(p) != '0'*31+'1'
                    for p in ('WIDTH','CLK_POLARITY','ALOAD_POLARITY')) or
                any(len(cell['connections'].get(p,[])) != 1
                    for p in ('CLK','D','Q','ALOAD')) or
                type(cell['connections']['ALOAD'][0]) is not int):
            raise ValueError('Threshold async load is not a positive-edge constant-zero clear')
    clock=cell['connections']['CLK']
    aon=module['netnames']['digital.subsystem.powerReset.clk']['bits']
    if clock != aon:
        raise ValueError('Threshold register has the wrong clock')
    return dict(register=name,output_pin=pin,clock_bits=clock,
                registered_bits=bits[:1],reserved_bits=bits[1:],
                scope='Digital endpoint only; D85 analog behavior remains T34')
