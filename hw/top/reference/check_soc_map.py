"""T20 description validation; no SoC RTL or acceptance claim."""
from pathlib import Path
import argparse
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
import yaml
from hw.regmap.regmap import UniqueLoader, load as load_regmap

# Independent logical-function inventory from the reviewed T20 pin contract.
# Keeping this closed prevents a smaller/omitted interface from faking a fit.
PIN_CONTRACT = {
    'osc_in': (1, 'input'), 'osc_en': (1, 'output'),
    'aon_clk_in': (1, 'input'), 'aon_clk_sel': (1, 'input'), 'por_bypass': (1, 'input'),
    'uart_tx': (3, 'output'), 'uart_rx': (3, 'input'),
    'spi_sclk': (1, 'output'), 'spi_mosi': (1, 'output'),
    'spi_miso': (1, 'input'), 'spi_cs_n': (2, 'output'), 'imu_drdy': (1, 'input'),
    'i2c_host': (2, 'open_drain'), 'aon_extra': (3, 'bidirectional'),
    'qspi_sclk': (1, 'output'), 'qspi_dq': (4, 'bidirectional'), 'qspi_cs_n': (2, 'output'),
    'actuator': (9, 'output'), 'usb_data': (2, 'bidirectional'),
    'usb_vbus': (1, 'input'), 'usb_pullup': (1, 'output'),
    'jtag_tck': (1, 'input'), 'jtag_tms': (1, 'input'), 'jtag_tdi': (1, 'input'),
    'jtag_tdo': (1, 'output'), 'gpio': (3, 'bidirectional'), 'timer': (4, 'bidirectional'),
}


def check(ok, message):
    if not ok:
        raise ValueError(message)


def keys(value, required, optional=()):
    check(isinstance(value, dict), 'Expected mapping')
    check(set(required) <= set(value) <= set(required) | set(optional), 'Missing or unknown keys')


def number(value, low, high):
    return type(value) is int and low <= value <= high


def name(value):
    check(isinstance(value, str) and re.fullmatch(r'[a-z][a-z0-9_]*', value), 'Invalid name')


def validate(data):
    keys(data, ('schema', 'name', 'clocks', 'resets', 'masters', 'regions', 'interrupts', 'pins', 'pin_budget', 'groups', 'fabrics', 'flight_io', 'general_timers', 'aon_io', 'lite_interrupts', 'pad_mux', 'retained_layout', 'dma', 'pinmux', 'watchdog', 'boot_control', 'osc_ctrl', 'power_reset', 'qspi', 'qspi_xip', 'sram'))
    check(data['sram'] == dict(lock='hw/vendor/gf180_sram/gf180_sram.lock.json',
        performance_sram=dict(macro='gf180mcu_ocd_ip_sram__sram1024x8m8wm1',banks=4, lanes=4, rows=1024, accessible_words=4096),
        retained_sram=dict(macro='gf180mcu_ocd_ip_sram__sram512x8m8wm1',banks=1, lanes=4, rows=512, accessible_words=512),
        bist=dict(dmi_base=0x70, dmi_words=16, regmap='hw/ip/sram/sram.regmap.yaml',
                  admission='acknowledged_ndmreset')), 'SRAM physical/test binding differs from T35/PLAN05')
    check(type(data['schema']) is int and data['schema'] == 1, 'Unsupported schema')
    name(data['name'])
    check(isinstance(data['clocks'], dict) and data['clocks'], 'Missing clocks')
    for n, c in data['clocks'].items():
        name(n); keys(c, ('hz', 'source'))
        expected = {'main': ('osc_in_div6', [8000000]),
                    'aon': ('lf_rc_or_reset_strap', [32000]),
                    'usb': ('osc_in', [48000000]),
                    'tck': ('external_test_input', [100000])}
        check(n in expected and (c['source'], c['hz']) == expected[n], 'Clock source/rate differs from D78 contract')
        check(isinstance(c['hz'], list) and c['hz'] and
              all(number(h, 1, 100000000) for h in c['hz']), 'Invalid frequency')
    check(isinstance(data['resets'], list) and data['resets'], 'Missing resets')
    for n in data['resets']: name(n)
    check(len(set(data['resets'])) == len(data['resets']), 'Duplicate reset')
    check(set(data['resets']) == {'cold', 'warm', 'debug', 'usb_transport'}, 'T41 reset cohorts differ')
    check(isinstance(data['masters'], dict) and data['masters'], 'Missing masters')
    origins = set()
    for n, m in data['masters'].items():
        name(n); keys(m, ('origin', 'implementation'))
        check(number(m['origin'], 0, 7) and m['origin'] not in origins, 'Duplicate/invalid origin')
        origins.add(m['origin'])
        check(m['implementation'] in ('real', 'test_standin', 'inactive'), 'Invalid master kind')
    check(data['masters'].get('lite', {}).get('implementation') == 'real', 'Production requires real lite hart')
    check(isinstance(data['regions'], list) and data['regions'], 'Missing regions')
    seen = set()
    for r in data['regions']:
        keys(r, ('name', 'base', 'size', 'home', 'domains', 'kind', 'reset'), ('regmap',))
        name(r['name']); check(r['name'] not in seen, 'Duplicate region'); seen.add(r['name'])
        check(number(r['base'], 0, 0xffffffff) and number(r['size'], 4, 1 << 32), 'Invalid range')
        check(r['base'] % 4 == 0 and r['size'] % 4 == 0 and
              r['base'] + r['size'] <= 1 << 32, 'Unaligned/wrapped range')
        check(isinstance(r['home'], str) and r['home'], 'Invalid home')
        check(isinstance(r['domains'], list) and r['domains'], 'Missing domains')
        check(all(d in data['clocks'] for d in r['domains']) and
              len(set(r['domains'])) == len(r['domains']), 'Invalid domains')
        check(r['reset'] in data['resets'], 'Unknown reset')
        check(r['kind'] in ('model', 'stub', 'real', 'local_pair', 'optional_usb', 'reserved', 'container'), 'Invalid kind')
        check(r['kind'] not in ('real', 'local_pair', 'optional_usb') or 'regmap' in r,
              'Implemented register target requires regmap')
        if 'regmap' in r:
            check(isinstance(r['regmap'], str), 'Invalid regmap path')
            path = (ROOT / r['regmap']).resolve()
            check(path.is_relative_to(ROOT / 'hw/ip'), 'Regmap outside IP tree')
            regs = load_regmap(path)
            check((1 << regs['address_width']) <= r['size'], 'Regmap exceeds window')
            check(r['base'] % (1 << regs['address_width']) == 0, 'Regmap base alignment')
    for i, a in enumerate(data['regions']):
        for b in data['regions'][:i]:
            if set(a['domains']) & set(b['domains']):
                check(a['base'] + a['size'] <= b['base'] or
                      b['base'] + b['size'] <= a['base'], 'Overlapping regions')
    if 'groups' in data or 'fabrics' in data:
        check('groups' in data and 'fabrics' in data, 'Incomplete fabric configuration')
        check(isinstance(data['groups'], dict) and isinstance(data['fabrics'], dict),
              'Fabric configuration must be mappings')
        regions = {r['name']: r for r in data['regions']}
        apertures = dict(regions)
        for n, g in data['groups'].items():
            name(n); keys(g, ('base', 'size', 'members'))
            check(n not in apertures, 'Duplicate group/endpoint')
            check(number(g['base'], 0, 0xffffffff) and number(g['size'], 4, 1 << 32)
                  and g['size'] & (g['size'] - 1) == 0 and g['base'] % g['size'] == 0
                  and g['base'] + g['size'] <= 1 << 32, 'Invalid group aperture')
            check(isinstance(g['members'], list) and 1 <= len(g['members']) <= 8
                  and all(isinstance(m, str) for m in g['members'])
                  and len(set(g['members'])) == len(g['members']), 'Invalid group members')
            for member in g['members']:
                check(member in regions, 'Unknown group member')
                r = regions[member]
                check(g['base'] <= r['base'] and r['base'] + r['size'] <= g['base'] + g['size'],
                      'Group does not contain member')
            apertures[n] = g
        check(set(data['fabrics']) == {'main', 'aon'}, 'Missing domain fabric')
        for members in data['fabrics'].values():
            check(isinstance(members, list) and 1 <= len(members) <= 8
                  and all(isinstance(m, str) for m in members)
                  and len(set(members)) == len(members), 'Invalid fabric targets')
            ranges = []
            for member in members:
                check(member in apertures, 'Unknown fabric target')
                r = apertures[member]
                size = 1 << (r['size'] - 1).bit_length()
                check(r['base'] % size == 0 and r['base'] + size <= 0xffffffff,
                      'Unaligned fabric aperture or sentinel mapped')
                for base, span in ranges:
                    check(r['base'] + size <= base or base + span <= r['base'], 'Fabric apertures overlap')
                ranges.append((r['base'], size))
    if 'watchdog' in data:
        p=data['watchdog']
        keys(p, ('parent','offset','size','count','clock','reset','owners','regmap'))
        check(all(type(p[n]) is int for n in ('offset','size','count')), 'Invalid watchdog range')
        check(p == dict(parent='power_reset_timer', offset=256, size=256, count=2,
                        clock='aon', reset='warm', owners=['performance','lite'],
                        regmap='hw/ip/watchdog/watchdog.regmap.yaml'), 'Watchdog binding differs from D70 contract')
        parent=next((r for r in data['regions'] if r['name']==p['parent']),None)
        check(parent is not None and parent['home']=='aon' and p['offset']+p['count']*p['size']<=parent['size'],
              'Watchdog exceeds AON parent')
        check('flight_io' in data, 'Watchdog requires AON timer metadata')
        regs=load_regmap(ROOT/p['regmap'])
        check(1 << regs['address_width'] == p['size'], 'Watchdog regmap width differs')
    if 'boot_control' in data:
        p=data['boot_control']
        keys(p, ('parent','offset','size','clock','reset','owner','regmap'))
        check(all(type(p[n]) is int for n in ('offset','size')), 'Invalid boot control range')
        check(p == dict(parent='power_reset_timer', offset=768, size=256, clock='aon',
                        reset='warm', owner='performance', regmap='hw/ip/boot_control/boot_control.regmap.yaml'),
              'Boot control binding differs from contract')
        check('watchdog' in data, 'Boot control requires the AON service fabric')
        parent=next((r for r in data['regions'] if r['name']==p['parent']),None)
        check(parent is not None and parent['home']=='aon' and p['offset']+p['size']<=parent['size'],
              'Boot control exceeds AON parent')
        check(1 << load_regmap(ROOT/p['regmap'])['address_width'] == p['size'], 'Boot control regmap width differs')
    if 'osc_ctrl' in data:
        p = data['osc_ctrl']
        check(p == dict(parent='power_reset_timer', offset=1024, size=256, clock='aon',
                        reset='warm', owner='performance', regmap='hw/ip/osc_ctrl/osc_ctrl.regmap.yaml'),
              'Oscillator controller binding differs from PLAN04')
        check(1 << load_regmap(ROOT / p['regmap'])['address_width'] == p['size'],
              'Oscillator controller regmap width differs')
    if 'power_reset' in data:
        p = data['power_reset']
        check(p == dict(parent='power_reset_timer', offset=1280, size=256, clock='aon',
                        reset='warm', owner='performance', regmap='hw/ip/power_reset/power_reset.regmap.yaml'),
              'Power/reset controller binding differs from T33')
        check('osc_ctrl' in data and 'watchdog' in data, 'Power/reset requires production causes and clock control')
        parent = next(r for r in data['regions'] if r['name'] == p['parent'])
        check(p['offset'] + p['size'] <= parent['size'], 'Power/reset exceeds AON parent')
        check(1 << load_regmap(ROOT / p['regmap'])['address_width'] == p['size'],
              'Power/reset regmap width differs')
    if 'qspi' in data:
        p=data['qspi']
        check(p==dict(region='qspi_control',clock='main',reset='warm',reset_owner='performance',
                      owners=['performance'],regmap='hw/ip/qspi/qspi.regmap.yaml'), 'QSPI binding differs')
        region=next((r for r in data['regions'] if r['name']==p['region']),None)
        check(region is not None and region['home']=='main' and region['base']==0x40013000 and
              region['size']==1 << load_regmap(ROOT/p['regmap'])['address_width'], 'QSPI aperture differs')
    if 'qspi_xip' in data:
        p=data['qspi_xip']
        check(p==dict(region='xip',control='qspi_control',clock='main',reset='warm',
                      owner='performance',regmap='hw/ip/qspi_xip/qspi_xip.regmap.yaml'), 'XIP binding differs')
        check('qspi' in data, 'XIP requires QSPI')
        region=next((r for r in data['regions'] if r['name']==p['region']),None)
        check(region is not None and region['base']==0x10000000 and region['size']==0x10000000,
              'XIP aperture differs')
        base=load_regmap(ROOT/data['qspi']['regmap']);extra=load_regmap(ROOT/p['regmap'])
        check(base['address_width']==extra['address_width'], 'XIP register width differs')
        check(not ({r['offset'] for r in base['registers']} & {r['offset'] for r in extra['registers']}),
              'XIP registers overlap commands')
    if 'pinmux' in data:
        p = data['pinmux']
        keys(p, ('parent','offset','size','clock','reset','owner','regmap','sources','channels','timer_channels','timer_pads'))
        check(type(p['offset']) is int and type(p['size']) is int and
              isinstance(p['channels'], list) and all(type(n) is int for n in p['channels']), 'Invalid pinmux subwindow/channel')
        check(p == dict(parent='gpio_pinmux', offset=512, size=256, clock='main', reset='warm',
                        owner='performance', regmap='hw/ip/pinmux/pinmux.regmap.yaml',
                        sources=['disconnected','gpio','timer_compare','pwm'], channels=[0,1,2],
                        timer_channels=list(range(12)), timer_pads=dict(actuator=9,timer=4)),
              'Pinmux binding differs from contract')
        check('flight_io' in data and 'general_timers' in data, 'Pinmux requires GPIO/timer/PWM metadata')
        parent = next((r for r in data['regions'] if r['name']==p['parent']), None)
        check(parent is not None and parent['home']=='main' and p['offset']+p['size']<=parent['size'], 'Pinmux exceeds parent')
        regs=load_regmap(ROOT/p['regmap'])
        check(1 << regs['address_width'] == p['size'], 'Pinmux regmap width differs')
    if 'dma' in data:
        p = data['dma']
        keys(p, ('parent', 'offset', 'size', 'clock', 'reset', 'owner', 'memory', 'regmap'))
        check(type(p['offset']) is int and type(p['size']) is int, 'Invalid DMA subwindow')
        check(p == dict(parent='dma', offset=0, size=256, clock='main', reset='warm',
                        owner='performance', memory='performance_sram', regmap='hw/ip/dma/dma.regmap.yaml'),
              'DMA binding differs from contract')
        check('general_timers' in data, 'DMA profile requires PWM metadata')
        parent = next((r for r in data['regions'] if r['name'] == 'dma'), None)
        check(parent is not None and parent['home'] == 'main' and parent['size'] >= p['size'],
              'DMA exceeds parent')
        regs = load_regmap(ROOT / p['regmap'])
        check(1 << regs['address_width'] == p['size'], 'DMA regmap width differs')
    if 'general_timers' in data:
        p = data['general_timers']
        keys(p, ('parent', 'offset', 'size', 'clock', 'reset', 'owner', 'regmap'))
        check(type(p['offset']) is int and type(p['size']) is int, 'Invalid PWM subwindow')
        check(p == dict(parent='general_timers', offset=0, size=1024, clock='main',
                        reset='warm', owner='performance', regmap='hw/ip/timers/timers.regmap.yaml'),
              'PWM binding differs from contract')
        parent = next((r for r in data['regions'] if r['name'] == p['parent']), None)
        check(parent is not None, 'Missing PWM parent')
        check(parent['home'] == 'main' and parent['size'] >= p['size'], 'PWM exceeds parent')
        regs = load_regmap(ROOT / p['regmap'])
        check(1 << regs['address_width'] == p['size'], 'PWM regmap width differs')
    if 'flight_io' in data:
        profile = data['flight_io']
        keys(profile, ('gpio', 'aon_timer'))
        expected = {'gpio': ('gpio_pinmux', 0, 'main', 'performance'),
                    'aon_timer': ('power_reset_timer', 0, 'aon', 'lite')}
        parents = {r['name']: r for r in data['regions']}
        spans = []
        for n, p in profile.items():
            keys(p, ('parent', 'offset', 'size', 'clock', 'owner', 'regmap'))
            check((p['parent'], p['offset'], p['clock'], p['owner']) == expected[n],
                  'Flight I/O binding differs from contract')
            check(type(p['offset']) is int and type(p['size']) is int and p['size'] == 256,
                  'Invalid flight I/O subwindow')
            parent = parents[p['parent']]
            check(p['offset'] + p['size'] <= parent['size'] and p['clock'] in parent['domains'],
                  'Flight I/O exceeds parent')
            check(p['regmap'] == f'hw/ip/{n}/{n}.regmap.yaml', 'Flight I/O regmap differs')
            regs = load_regmap(ROOT / p['regmap'])
            check(1 << regs['address_width'] == p['size'], 'Flight I/O regmap width differs')
            base = parent['base'] + p['offset']
            check(base % p['size'] == 0, 'Flight I/O misaligned')
            for other, end in spans:
                check(base + p['size'] <= other or end <= base, 'Flight I/O overlap')
            spans.append((base, base + p['size']))
    check(data['retained_layout']==dict(program_bytes=1024,data_bytes=1024,writer='performance',write_condition='boot_held_reset'), 'Retained program authority differs')
    retained=next(r for r in data['regions'] if r['name']=='retained_sram')
    check(retained['size']==2048, 'Retained capacity differs from measured E5 choice')
    check(data['fabrics']['main']==['serial','mailbox','general_timers','gateway','retained_sram','power_reset_timer','future_bridge'] and
          data['fabrics']['aon']==['retained_sram','power_reset_timer','mailbox','aon_io','future_bridge'], 'PLAN05 fabric ownership differs')
    for r in data['regions']:
        if r['home'] in ('main','main/usb/aon'):
            check(r['domains']==['main'], 'Lite access to main peripheral remains')
    check(set(data['aon_io'])=={'aon_spi','aon_gpio'}, 'AON service inventory differs')
    for n,base in [('aon_spi',0x40020000),('aon_gpio',0x40020100)]:
        check(data['aon_io'][n]==dict(region=n,clock='aon',reset='warm',owner='lite',regmap=f'hw/ip/{n}/{n}.regmap.yaml'), 'AON peripheral binding differs')
        r=next(r for r in data['regions'] if r['name']==n)
        check(r['base']==base and r['size']==256 and r['home']=='aon' and r['domains']==['aon'], 'AON service aperture differs')
    check(data['lite_interrupts']==dict(aon_spi=0,aon_gpio=1,power_reset_timer=2,mailbox=3), 'Lite IRQ sources differ')
    check(data['pad_mux']==dict(aon_gpio=['gpio0','gpio1','gpio2','aon_extra0','aon_extra1','aon_extra2'],
          aon_spi=dict(sclk=0,mosi=1,miso=2,cs_n=3),radio_gpio=[4,5],
          boot_mode=dict(pad='gpio1',strap='reset_sampled',normal=0,recovery=1)), 'AON pad multiplexing differs')
    check(isinstance(data['interrupts'], dict), 'Invalid interrupts')
    indices = list(data['interrupts'].values())
    check(all(number(i, 0, 14) for i in indices) and len(set(indices)) == len(indices), 'Invalid/duplicate interrupt')
    check(set(data['interrupts']) <= seen | {'timer1','timer2'}, 'Interrupt source missing')
    check(all(data['interrupts'].get(n)==i for n,i in [('general_timers',10),('timer1',12),('timer2',13)]), 'General timer interrupts differ')
    check(isinstance(data['pins'], dict) and data['pins'], 'Missing pins')
    for n, p in data['pins'].items():
        name(n); keys(p, ('width', 'direction', 'clock', 'safe'), ('pad_class', 'strap'))
        check(p.get('strap') == {'aon_clk_sel': 'reset_sampled', 'por_bypass': 'static_powered'}.get(n),
              'Strap contract differs from D84')
        check(p.get('pad_class') == ('dedicated_clock' if n == 'osc_in' else None),
              'Only OSC_IN uses the dedicated clock pad')
        # 'inactive' has no sampling domain: inputs ignored, outputs tied off.
        check(number(p['width'], 1, 32) and
              (p['clock'] in data['clocks'] or p['clock'] == 'inactive'), 'Invalid pin width/clock')
        safe = {'input': 'input', 'output': 'disabled', 'bidirectional': 'disabled', 'open_drain': 'released'}
        check(p['direction'] in safe and p['safe'] == ('high' if n == 'osc_en' else safe[p['direction']]), 'Unsafe pin default')
    keys(data['pin_budget'], ('bidirectional', 'input_only'))
    check(data['pin_budget'] == {'bidirectional': 40, 'input_only': 12}, 'Nominal slot capacity differs')
    for kind, used in pin_usage(data).items():
        check(used <= data['pin_budget'][kind], f'Pin budget exceeded: {kind}')
    check(set(data['pins']) == set(PIN_CONTRACT), 'Logical pin function inventory differs')
    for n, (width, direction) in PIN_CONTRACT.items():
        p = data['pins'][n]
        check((p['width'], p['direction']) == (width, direction), f'Logical pin contract differs: {n}')
    return data


def pin_usage(data):
    # Output/open-drain/bidirectional functions require output-capable pads.
    # Physical pad groups count once; pad_mux separately validates alternate uses.
    return {
        'bidirectional': sum(p['width'] for p in data['pins'].values() if p['direction'] != 'input'),
        'input_only': sum(p['width'] for p in data['pins'].values()
                          if p['direction'] == 'input' and p.get('pad_class') != 'dedicated_clock'),
    }


def contract_rows(text):
    rows = []
    for line in text.splitlines():
        fields = [x.strip() for x in line.split('|')]
        if len(fields) == 7 and re.fullmatch(r'0x[0-9a-f]+', fields[2]):
            rows.append((fields[1], int(fields[2], 16), int(fields[3], 16), fields[4]))
    return rows


def check_contract(data, text):
    text = text.split("## Appendix: historical profile contracts", 1)[0]
    actual = [(r['name'], r['base'], r['size'], r['home']) for r in data['regions']]
    check(contract_rows(text) == actual, 'Contract address table differs')
    irq_rows = []
    for line in text.splitlines():
        fields = [x.strip() for x in line.split('|')]
        if len(fields) == 5 and fields[2].isdigit():
            irq_rows.append((fields[1], int(fields[2])))
    check(sorted(irq_rows) == sorted(data['interrupts'].items()), 'Contract interrupt table differs')


def dma_endpoints(data):
    """Resolve protocol register addresses from the authoritative register maps."""
    regions = {r['name']: r for r in data['regions']}
    maps = {n: load_regmap(ROOT / f'hw/ip/{n}/{n}.regmap.yaml') for n in ('uart', 'spi_host', 'timers')}
    def register(block, name):
        return next(r for r in maps[block]['registers'] if r['name'] == name)
    def address(block, instance, name):
        offset = register(block, name)['offset']
        check(offset % 4 == 0 and offset + 4 <= regions[instance]['size'], 'DMA endpoint outside aligned register aperture')
        return regions[instance]['base'] + offset
    def field(block, reg, name, access, width):
        f = next(f for f in register(block, reg)['fields'] if f['name'] == name)
        check((f['access'], f['lsb'], f['width']) == (access, 0, width), 'DMA endpoint data contract differs')
    def pulse(block, reg, field):
        f = next(f for f in register(block, reg)['fields'] if f['name'] == field)
        check(f['access'] == 'w1p', 'DMA completion requires a pulse register')
        return 1 << f['lsb']
    result = dict(data=[], command=[], command_value=[], period=[], pending=address('timers', 'general_timers', 'pending'))
    for block, instance in [('uart', f'uart{i}') for i in range(3)] + [('spi_host', 'spi_host')]:
        field(block, 'tx_data', 'value', 'wo', 8)
        field(block, 'rx_data', 'value', 'ro', 8)
        for receive in (False, True):
            result['data'].append(address(block, instance, 'rx_data' if receive else 'tx_data'))
            result['command'].append(address(block, instance, 'command'))
            result['command_value'].append(pulse(block, 'command', 'rx_pop') if receive else 0)
    for i in range(9):
        field('timers', f'compare{i}', 'value', 'rw', 17)
        field('timers', f'period{i//4}', 'value', 'rw', 16)
        result['data'].append(address('timers', 'general_timers', f'compare{i}'))
        result['period'].append(address('timers', 'general_timers', f'period{i//4}'))
        result['command'].append(address('timers', 'general_timers', 'apply'))
        result['command_value'].append(pulse('timers', 'apply', 'channels') << i)
    field('timers', 'pending', 'channels', 'ro', 12)
    field('timers', 'apply', 'channels', 'w1p', 12)
    return result


def emit(data, output):
    output = output.resolve()
    check(output.is_relative_to(ROOT / 'build'), 'Output must be under build')
    output.mkdir(parents=True, exist_ok=True)
    for filename in ('soc.h', 'SocMap.scala', 'soc-map.md', 'soc.json'):
        path = output / filename
        check(not path.is_symlink() and path.resolve().parent == output,
              'Output file must not be a symlink or escape its directory')
    header = ['/* T20 provisional generated map; not a frozen ABI. */', '#pragma once']
    scala = ['package deadhorse.top', '', 'object SocMap {',
             '  final case class Region(name: String, base: BigInt, size: BigInt)',
             '  val regions = Seq(']
    markdown = ['| Endpoint | Base | Size | Home |', '| --- | --- | --- | --- |']
    for r in data['regions']:
        n = r['name'].upper()
        header += [f'#define DH_SOC_{n}_BASE 0x{r["base"]:08x}u', f'#define DH_SOC_{n}_SIZE 0x{r["size"]:x}u']
        scala.append(f'    Region("{r["name"]}", BigInt("{r["base"]:x}",16), BigInt("{r["size"]:x}",16)),')
        markdown.append(f'| {r["name"]} | 0x{r["base"]:08x} | 0x{r["size"]:x} | {r["home"]} |')
    scala[-1] = scala[-1].removesuffix(',')
    scala += ['  )', '  val fastInterrupts = Map(']
    for n, i in data['interrupts'].items():
        header.append(f'#define DH_SOC_{n.upper()}_FAST_IRQ {i}u')
        scala.append(f'    "{n}" -> {i},')
    if data['interrupts']: scala[-1] = scala[-1].removesuffix(',')
    scala += ['  )', '  val flightIo = Seq(']
    if 'flight_io' in data:
        parents = {r['name']: r for r in data['regions']}
        markdown += ['', 'Production I/O services:', '',
                     '| Service | Base | Size | Clock |', '| --- | --- | --- | --- |']
        for n, p in data['flight_io'].items():
            base = parents[p['parent']]['base'] + p['offset']
            header += [f'#define DH_SOC_IO_{n.upper()}_BASE 0x{base:08x}u',
                       f'#define DH_SOC_IO_{n.upper()}_SIZE 0x{p["size"]:x}u']
            scala.append(f'    Region("{n}", BigInt("{base:x}",16), BigInt("{p["size"]:x}",16)),')
            markdown.append(f'| {n} | 0x{base:08x} | 0x{p["size"]:x} | {p["clock"]} |')
        scala[-1] = scala[-1].removesuffix(',')
    scala += ['  )', '}']
    if 'general_timers' in data:
        p = data['general_timers']; parent = next(r for r in data['regions'] if r['name'] == p['parent'])
        header += [f'#define DH_SOC_TIMERS_BASE 0x{parent["base"] + p["offset"]:08x}u',
                   f'#define DH_SOC_TIMERS_SIZE 0x{p["size"]:x}u']
        markdown += ['', 'Production timer outputs disable immediately on shared warm reset;',
                     'watchdog output-disable is connected.']
    if 'dma' in data:
        p = data['dma']; parent = next(r for r in data['regions'] if r['name'] == p['parent'])
        header += [f'#define DH_SOC_DMA_REG_SIZE 0x{p["size"]:x}u']
        markdown += ['', 'Production DMA: four finite-count channels, performance SRAM, UART/SPI bytes and PWM words;',
                     'shared warm reset. Endpoint addresses are derived from the peripheral register maps.']
    if 'pinmux' in data:
        p=data['pinmux'];parent=next(r for r in data['regions'] if r['name']==p['parent'])
        header += [f'#define DH_SOC_PINMUX_BASE 0x{parent["base"]+p["offset"]:08x}u',
                   f'#define DH_SOC_PINMUX_SIZE 0x{p["size"]:x}u']
        header += [f'#define DH_SOC_PINMUX_{name.upper()} {i}u' for i,name in enumerate(p['sources'])]
        markdown += ['', 'Production GPIO output alternatives, same-index channels0..2: '+', '.join(p['sources'])+'.',
                     'Input/wake and dedicated interfaces unchanged; physical map remains provisional.']
    markdown += ['', 'Provisional simultaneous logical pin demand; not physical fit.', '',
                 '| Pad class | Used | Nominal capacity |', '| --- | --- | --- |']
    for kind, used in pin_usage(data).items():
        markdown.append(f'| {kind} | {used} | {data["pin_budget"][kind]} |')
    for n, p in data['pins'].items():
        header.append(f'#define DH_SOC_PIN_{n.upper()}_WIDTH {p["width"]}u')
    for filename, lines in [('soc.h', header), ('SocMap.scala', scala), ('soc-map.md', markdown)]:
        (output / filename).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    serialized = dict(data)
    if 'dma' in data:
        serialized['dma_endpoints'] = dma_endpoints(data)
    (output / 'soc.json').write_text(json.dumps(serialized, indent=2) + '\n', encoding='utf-8')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', type=Path, default=Path(__file__).with_name('soc.yaml'))
    p.add_argument('--output', type=Path, default=ROOT / 'build/t20/map')
    args = p.parse_args()
    data = validate(yaml.load(args.config.read_text(encoding='utf-8'), Loader=UniqueLoader))
    check_contract(data, (ROOT / 'docs/spec/soc.md').read_text(encoding='utf-8'))
    emit(data, args.output)
    print(f'PASS provisional SoC map: {len(data["regions"])} regions; not RTL or pin-fit acceptance')
    print(f'Estimated simultaneous pin demand: {pin_usage(data)}; nominal capacities {data["pin_budget"]}')


if __name__ == '__main__':
    main()
