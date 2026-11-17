"""Discrete-event shared flash bus experiment, not a controller or part model."""
from collections import deque
from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class Command:
    name: str
    opcode: int
    opcode_bits: int = 8
    opcode_lanes: int = 1
    address_bits: int = 0
    address_lanes: int = 1
    mode_bits: int = 0
    mode_lanes: int = 1
    data_lanes: int = 1
    dummy_cycles: int = 0


SERIAL_COMMANDS = (Command('wren',0x06), Command('read',0x0c,address_bits=32,dummy_cycles=8),
                   Command('program',0x12,address_bits=32), Command('erase',0xdc,address_bits=32))
QUAD_COMMANDS = (Command('wren',0x06),
                 Command('read',0xec,address_bits=32,address_lanes=4,mode_bits=8,mode_lanes=4,data_lanes=4,dummy_cycles=6),
                 Command('program',0x12,address_bits=32), Command('erase',0xdc,address_bits=32))


@dataclass(frozen=True)
class Profile:
    name: str
    sclk_hz: int
    commands: tuple = SERIAL_COMMANDS
    cs_gap_cycles: int = 2
    max_burst: int = 256
    page_bytes: int = 256
    program_busy_us: int = 3000
    erase_busy_us: int = 400000

    def __post_init__(self):
        if (self.sclk_hz <= 0 or self.max_burst <= 0 or self.page_bytes <= 0 or
                min(self.cs_gap_cycles,self.program_busy_us,self.erase_busy_us) < 0 or
                {c.name for c in self.commands}!={'wren','read','program','erase'} or len(self.commands)!=4):
            raise ValueError('Invalid flash profile')
        for c in self.commands:
            if (c.opcode_bits<=0 or not 0<=c.opcode<2**c.opcode_bits or
                    min(c.address_bits,c.mode_bits,c.dummy_cycles)<0 or
                    any(w not in (1,2,4) for w in (c.opcode_lanes,c.address_lanes,c.mode_lanes,c.data_lanes))):
                raise ValueError('Invalid flash command')

    def command(self,name):
        return next(c for c in self.commands if c.name==name)


PROFILES = (
    Profile('assumed-spi-12MHz', 12000000),
    Profile('assumed-quad-24MHz', 24000000, commands=QUAD_COMMANDS),
)


@dataclass(frozen=True)
class Transfer:
    owner: str
    command: str
    address: int = 0
    size: int = 0
    tag: int = 0


def phases(profile, transfer, fault=None):
    command = profile.command(transfer.command)
    result = [('opcode', command.opcode_bits, command.opcode_lanes)]
    if transfer.command in ('read', 'program', 'erase'):
        result.append(('address', command.address_bits, command.address_lanes))
    if transfer.command == 'read':
        result.append(('mode', command.mode_bits, command.mode_lanes))
        result.append(('dummy', 0 if fault == 'omit_dummy' else command.dummy_cycles, 1))
    if transfer.command in ('read', 'program'):
        result.append(('data', transfer.size*8, command.data_lanes))
    result.append(('cs_gap', profile.cs_gap_cycles, 1))
    return result


def wire_cycles(profile, transfer, fault=None):
    # Count physical lane beats rather than reusing the arithmetic oracle.
    count = 0
    for _, bits, lanes in phases(profile, transfer, fault):
        while bits > 0:
            bits -= lanes
            count += 1
    return count


class FlashBus:
    """Priority boot/XIP reads; nonpreemptive bounded logging transactions.

    One outstanding read is the latency contract. Logs are queued as complete
    batches, dropped atomically on full. Program/erase busy is per logging chip;
    the shared bus is released. Conservative fixed waits of the assumed maximum
    program/erase times replace polling; a part must qualify these upper bounds.
    """
    def __init__(self, profile, queue_records=8, fault=None):
        if queue_records < 1:
            raise ValueError('Empty logging queue')
        self.profile, self.queue_records, self.fault = profile, queue_records, fault
        self.now = 0
        self.busy_until = 0
        self.logs = deque()
        self.reads = deque()
        self.active = None
        self.trace = []
        self.read_done = {}
        self.dropped = self.accepted = self.completed = 0
        self.max_queue = 0
        self.next_tag = 0

    def read(self, address, size, owner='xip'):
        if owner not in ('boot','xip') or size < 1 or size > self.profile.max_burst:
            raise ValueError('Read must be one bounded boot/XIP burst')
        if address < 0 or address + size > 2**self.profile.command('read').address_bits:
            raise ValueError('Read outside flash address space')
        if self.reads or (self.active and self.active[1].owner != 'log'):
            raise ValueError('One outstanding priority read')
        self.next_tag += 1
        self.reads.append(Transfer(owner, 'read', address, size, self.next_tag))
        return self.next_tag

    def log(self, address, size=64, erase=False):
        if address < 0 or size < 1 or address + size > 2**self.profile.command('program').address_bits:
            raise ValueError('Log outside flash address space')
        if len(self.logs) == self.queue_records:
            self.dropped += 1
            return False
        commands = deque()
        if erase:
            commands.extend((Transfer('log','wren'), Transfer('log','erase',address)))
        else:
            remaining = size
            while remaining:
                chunk = remaining if self.fault == 'unbounded_burst' else min(
                    remaining, self.profile.max_burst, self.profile.page_bytes-address%self.profile.page_bytes)
                commands.extend((Transfer('log','wren'), Transfer('log','program',address,chunk)))
                remaining -= chunk
                address += chunk
        self.logs.append(commands)
        self.accepted += 1
        self.max_queue = max(self.max_queue, len(self.logs))
        return True

    def advance(self, end):
        if end < self.now:
            raise ValueError('Time cannot reverse')
        while True:
            if self.active is not None:
                finish, transfer = self.active
                if finish > end:
                    self.now = end
                    return
                self.now = finish
                self.active = None
                if transfer.owner != 'log':
                    self.read_done[transfer.tag] = finish
                elif transfer.command in ('program','erase'):
                    us = self.profile.program_busy_us if transfer.command == 'program' else self.profile.erase_busy_us
                    self.busy_until = finish + (us*self.profile.sclk_hz + 999999)//1000000
            if self.logs and not self.logs[0] and self.now >= self.busy_until:
                self.logs.popleft()
                self.completed += 1
            if self.reads:
                transfer = self.reads.popleft()
            elif self.logs and self.now >= self.busy_until:
                transfer = self.logs[0].popleft()
            else:
                if self.logs and self.busy_until <= end:
                    self.now = self.busy_until
                    continue
                self.now = end
                return
            duration = wire_cycles(self.profile, transfer, self.fault)
            if self.fault == 'held_bus' and transfer.command in ('program','erase'):
                us = self.profile.program_busy_us if transfer.command == 'program' else self.profile.erase_busy_us
                duration += (us*self.profile.sclk_hz + 999999)//1000000
            self.trace.append(dict(start=self.now, end=self.now+duration,
                                   cs='log' if transfer.owner == 'log' else 'boot',
                                   opcode=self.profile.command(transfer.command).opcode,
                                   **asdict(transfer)))
            self.active = (self.now+duration, transfer)
            if self.now == end:
                return
