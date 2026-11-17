"""Arithmetic/scenario oracle independent of the event scheduler."""
from dataclasses import asdict
from math import ceil
from collections import deque
from .flash import FlashBus, PROFILES


def expected_cycles(profile, command, size=0):
    # Closed-form phase arithmetic; no call to the model phase/beat engine.
    spec = next(c for c in profile.commands if c.name==command)
    result = ceil(spec.opcode_bits/spec.opcode_lanes) + profile.cs_gap_cycles
    if command != 'wren':
        result += ceil(spec.address_bits/spec.address_lanes)
    if command == 'read':
        result += ceil(spec.mode_bits/spec.mode_lanes) + spec.dummy_cycles
    if command in ('read','program'):
        result += ceil(8*size/spec.data_lanes)
    return result


def check_trace(profile, trace):
    previous_end = 0
    log_ready = 0
    write_enabled = False
    for event in trace:
        assert event['start'] >= previous_end, 'FLASH simultaneous chip selects'
        assert event['cs'] == ('log' if event['owner']=='log' else 'boot'), 'FLASH incorrect chip select'
        assert event['opcode']==next(c.opcode for c in profile.commands if c.name==event['command']), 'FLASH wrong command opcode'
        duration = expected_cycles(profile, event['command'], event['size'])
        assert event['end']-event['start'] == duration, 'FLASH phase/busy duration mismatch'
        previous_end = event['end']
        if event['owner'] == 'log':
            assert event['start'] >= log_ready, 'FLASH command while log device busy'
            if event['command'] == 'wren':
                write_enabled = True
            else:
                assert write_enabled, 'FLASH missing write enable'
                write_enabled = False
                if event['command'] == 'program':
                    assert 0 < event['size'] <= profile.max_burst, 'FLASH unbounded burst'
                    assert event['address']//profile.page_bytes == (event['address']+event['size']-1)//profile.page_bytes, 'FLASH crossed program page'
                busy_us = profile.program_busy_us if event['command']=='program' else profile.erase_busy_us
                log_ready = event['end'] + ceil(busy_us*profile.sclk_hz/1000000)


def interference(profile, fault=None):
    program = expected_cycles(profile,'program',profile.max_burst)
    wren = expected_cycles(profile,'wren')
    own_read = expected_cycles(profile,'read',64)
    worst = 0
    checked = {}
    # Every possible SCLK arrival edge of WREN, maximum PROGRAM and ERASE.
    # WREN's final edge is the next command's first edge, covered there.
    for command,duration,start,edges in (('program',program,wren,program+1),
            ('wren',wren,0,wren),
            ('erase',expected_cycles(profile,'erase'),wren,expected_cycles(profile,'erase')+1)):
        for offset in range(edges):
            model = FlashBus(profile, fault=fault)
            model.log(0,profile.max_burst,erase=command=='erase')
            arrival = start+offset
            model.advance(arrival)
            token = model.read(0x1234,64)
            model.advance(arrival+program+own_read+1)
            assert token in model.read_done, 'FLASH XIP blocked by write busy'
            observed = model.read_done[token]-arrival
            assert observed == max(0,duration-offset)+own_read, 'FLASH XIP interference mismatch'
            check_trace(profile,model.trace)
            worst = max(worst,observed)
        checked[command] = edges
    return dict(arrival_edges_checked=checked, measured_model_max_response_cycles=worst,
                estimated_bound_cycles=program+own_read,
                bound_arithmetic=f'{program} maximum in-flight log transfer + {own_read} own 64-byte read',
                estimated_bound_us=(program+own_read)*1000000/profile.sclk_hz)


def boundaries_and_boot(profile, fault=None):
    model = FlashBus(profile,fault=fault)
    model.log(profile.page_bytes-6,profile.page_bytes*2+20)
    model.advance(profile.sclk_hz)
    check_trace(profile,model.trace)
    programs = [e for e in model.trace if e['command']=='program']
    assert sum(e['size'] for e in programs)==profile.page_bytes*2+20, 'FLASH lost program bytes'
    cursor = profile.page_bytes-6
    for event in programs:
        assert event['address']==cursor, 'FLASH program address/order'
        cursor += event['size']
    assert model.completed==1, 'FLASH program never committed'
    # Boot population is an assumed synthetic full-SRAM load, not firmware size.
    boot = FlashBus(profile)
    expected = 0
    total = 16384+3072
    for address in range(0,total,profile.max_burst):
        size = min(profile.max_burst,total-address)
        token = boot.read(address,size,'boot')
        expected += expected_cycles(profile,'read',size)
        boot.advance(expected)
        assert boot.read_done[token]==expected, 'FLASH boot time mismatch'
    for size in (4,16,64,profile.max_burst):
        token = boot.read(profile.page_bytes-1,size)
        expected += expected_cycles(profile,'read',size)
        boot.advance(expected)
        assert boot.read_done[token]==expected, 'FLASH read crossing page mismatch'
    check_trace(profile,boot.trace)
    return dict(assumed_boot_bytes=total, measured_model_boot_cycles=sum(e['end']-e['start'] for e in boot.trace if e['owner']=='boot'),
                estimated_boot_cycles=(total//profile.max_burst)*expected_cycles(profile,'read',profile.max_burst),
                program_chunks=[e['size'] for e in programs])


def logging(profile, seconds=600, erase=False, fault=None):
    model = FlashBus(profile,queue_records=8,fault=fault)
    tick_per_record = profile.sclk_hz//1000
    assert tick_per_record*1000 == profile.sclk_hz
    staging = 0
    batches = 0
    dropped = 0
    if erase:
        model.log(0,erase=True)
    max_xip = 0
    # Producer calls never advance modeled time: SRAM staging/enqueue cannot wait
    # on a flash write. CPU execution cost remains outside this organization model.
    for record in range(seconds*1000):
        when = record*tick_per_record
        model.advance(when)
        staging += 64
        if staging==256:
            before = model.now
            if not model.log(batches*256,256):
                dropped += 4
            assert model.now==before, 'FLASH logging producer blocked'
            batches += 1
            staging = 0
        if record%1000==0:
            token = model.read(0x10000+(record%256),64)
            deadline = when+expected_cycles(profile,'program',profile.max_burst)+expected_cycles(profile,'read',64)
            model.advance(deadline)
            assert token in model.read_done, 'FLASH XIP blocked by write busy'
            max_xip = max(max_xip,model.read_done[token]-when)
    model.advance(seconds*profile.sclk_hz + profile.sclk_hz)
    check_trace(profile,model.trace)
    assert model.max_queue<=8 and model.dropped*4==dropped, 'FLASH queue/drop accounting'
    assert model.accepted==model.completed, 'FLASH accepted batch not committed'
    programs = [e for e in model.trace if e['command']=='program']
    assert len(programs)==batches-model.dropped, 'FLASH duplicate/lost accepted batch'
    # Independent deterministic queue recurrence, in cycles. The one-second
    # erase stress has its sole read between WREN and ERASE; normal-flight reads
    # occur during idle/device-busy time and do not extend page service.
    page_service = expected_cycles(profile,'wren')+expected_cycles(profile,'program',256)+ceil(profile.program_busy_us*profile.sclk_hz/1000000)
    finishes = deque()
    if erase:
        finishes.append(expected_cycles(profile,'wren')+expected_cycles(profile,'read',64)+
                        expected_cycles(profile,'erase')+ceil(profile.erase_busy_us*profile.sclk_hz/1000000))
    oracle_drops = 0
    for index in range(batches):
        arrival = (4*index+3)*tick_per_record
        while finishes and finishes[0]<=arrival:
            finishes.popleft()
        if len(finishes)==8:
            oracle_drops += 4
        else:
            finishes.append(max(arrival,finishes[-1] if finishes else arrival)+page_service)
    assert dropped==oracle_drops, 'FLASH independent queue recurrence mismatch'
    if not erase:
        # Independent recurrence: every 4ms a page; worst service includes one
        # 64-byte XIP read plus WREN, program wire time, and 3ms device busy.
        service = expected_cycles(profile,'read',64)+expected_cycles(profile,'wren')+expected_cycles(profile,'program',256)+ceil(profile.program_busy_us*profile.sclk_hz/1000000)
        period = 4*tick_per_record
        assert service<period, 'FLASH assumed service cannot sustain input'
        assert dropped==0 and len(programs)==seconds*250, 'FLASH sustained logging mismatch'
    else:
        assert dropped>0, 'FLASH overflow stress never filled queue'
    return dict(assumed_seconds=seconds, input_records=seconds*1000,
                assumed_xip_reads_per_second=1, assumed_xip_read_bytes=64,
                assumed_final_drain_seconds=1,
                measured_model_last_program_durable_cycle=max(e['end'] for e in programs)+ceil(profile.program_busy_us*profile.sclk_hz/1000000),
                measured_model_committed_bytes=len(programs)*256,
                measured_model_dropped_records=dropped,
                measured_model_max_queue_batches=model.max_queue,
                measured_model_max_xip_cycles=max_xip,
                queue_bytes=8*256, staging_bytes=256,
                estimated_page_service_cycles=page_service,
                estimated_page_service_us=page_service*1000000/profile.sclk_hz,
                estimated_payload_capacity_bytes_per_second=256*profile.sclk_hz/page_service,
                estimated_service_with_one_xip_read_per_page_cycles=page_service+expected_cycles(profile,'read',64),
                storage_policy='erase stress' if erase else 'pre-erased logging region; no in-flight erases')


def run_flash():
    rows = []
    for profile in PROFILES:
        rows.append(dict(profile=asdict(profile), provenance='assumed; no flash part selected; SCLK independent of CPU clock',
                         interference=interference(profile), boundaries=boundaries_and_boot(profile),
                         flight=logging(profile), erase_stress=logging(profile,seconds=1,erase=True)))
    rejected = []
    for fault, scenario, reason in (
            ('omit_dummy',interference,'FLASH XIP interference mismatch'),
            ('unbounded_burst',boundaries_and_boot,'FLASH unbounded burst'),
            ('held_bus',interference,'FLASH XIP blocked by write busy')):
        try:
            scenario(PROFILES[0],fault)
        except AssertionError as exc:
            assert str(exc)==reason, str(exc)
            rejected.append(dict(fault=fault,detection=str(exc)))
        else:
            raise AssertionError('Surviving flash negative control: '+fault)
    return dict(status='pass',profiles=rows,negative_controls=rejected,
                capacity=dict(provenance='estimated from assumed 64-byte records at 1kHz for 600 seconds',
                              arithmetic='64 * 1000 * 600 = 38400000 bytes; 40 * 2**20 = 41943040 bytes',
                              input_bytes=38400000, allowance_bytes=41943040, headroom_bytes=3543040,
                              caveat='Metadata, erase reserve, bad sectors and actual part capacity remain unqualified'),
                qualification='Model experiment; not RTL proof, flash-part selection, board SCLK qualification or silicon measurement')
