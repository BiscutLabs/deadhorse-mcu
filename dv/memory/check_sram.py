"""Independent byte dictionary oracle; never inspects bank implementation."""
import random
from .sram import BankedWords, Request

SEED = 0x53330017


class ByteOracle:
    def __init__(self, size):
        self.size, self.bytes = size, {}

    def access(self, req):
        if req.address not in range(0, self.size, 4):
            return (True, 0)
        if req.write:
            for offset, byte in enumerate(req.data.to_bytes(4, 'little')):
                if req.mask & (2**offset):
                    self.bytes[req.address+offset] = byte
            return (False, 0)
        return (False, int.from_bytes(bytes(self.bytes.get(req.address+i, 0) for i in range(4)), 'little'))


def check_configuration(size, banks, latency, fault=None):
    dut, reference = BankedWords(size, banks, latency, fault), ByteOracle(size)
    rng = random.Random(SEED)
    transactions = 0
    def transaction(req):
        nonlocal transactions
        assert dut.issue(req), 'SRAM acceptance'
        assert not dut.issue(Request(0)), 'SRAM duplicate credit'
        expected = reference.access(req)
        for edge in range(1, latency+1):
            dut.tick()
            assert dut.response == (expected if edge == latency else None), 'SRAM completion/data mismatch'
        for _ in range(rng.randrange(4)):
            assert not dut.issue(Request(0)), 'SRAM response backpressure'
            dut.tick()
            assert dut.response == expected, 'SRAM unstable response'
        assert dut.tick(ready=True) == expected and dut.response is None, 'SRAM consume'
        transactions += 1

    bank_bytes = size//banks
    addresses = sorted({0, size-4} | {p for b in range(1, banks) for p in (b*bank_bytes-4,b*bank_bytes)})
    # Unique sentinels straddle every bank, then revisit all to expose aliasing.
    for n, address in enumerate(addresses):
        transaction(Request(address, True, (n+1)*0x01020304 & 0xffffffff))
    for address in addresses:
        transaction(Request(address))
    for mask in range(16):
        for address in addresses:
            transaction(Request(address, True, 0xa9c3517e))
            transaction(Request(address, True, 0x173b6de2, mask))
            transaction(Request(address))
    for _ in range(160):
        address = rng.randrange(size//4)*4
        transaction(Request(address, True, rng.getrandbits(32), rng.randrange(16)))
        transaction(Request(address))
    for address in (-4, -1, 1, 2, 3, size-1, size, size+4, 2**32):
        transaction(Request(address, True, 0xffffffff))
        transaction(Request(address))
    for address in addresses:
        transaction(Request(address))
    return dict(size_bytes=size, banks=banks, assumed_latency_edges=latency,
                transactions=transactions, masks=list(range(16)))


def run_sram():
    configurations = [check_configuration(size,banks,latency)
        for size,banks in ((16384,1),(16384,4),(16384,16),(3072,1),(3072,3),(3072,12))
        for latency in (1,2,5)]
    rejected = []
    for fault in ('bank_alias','swapped_byte','masked_overwrite','early_completion'):
        try:
            check_configuration(3072,3,2,fault)
        except AssertionError as exc:
            assert str(exc) == 'SRAM completion/data mismatch', str(exc)
            rejected.append(dict(fault=fault, detection=str(exc)))
        else:
            raise AssertionError('Surviving SRAM negative control: '+fault)
    return dict(status='pass', seed=SEED, configurations=configurations,
                negative_controls=rejected,
                qualification='Measured model behavior only; no SRAM hardware, timing, area or power validation')
