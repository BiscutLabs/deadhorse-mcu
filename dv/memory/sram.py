"""Organization experiment only: word banks, no macro/RTL implementation."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Request:
    address: int
    write: bool = False
    data: int = 0
    mask: int = 15


class BankedWords:
    """One credit; completion after latency edges, then held until consumed.

    Contiguous banks and zero-initialized storage are modeling assumptions.
    Responses are (error, data); writes and invalid accesses return zero.
    """
    def __init__(self, size, banks, latency, fault=None):
        if size <= 0 or banks <= 0 or size % (4*banks) or latency < 1:
            raise ValueError('Invalid SRAM configuration')
        self.size, self.latency, self.fault = size, latency, fault
        self.words = [[0]*(size//(4*banks)) for _ in range(banks)]
        self.now = 0
        self.pending = None
        self.response = None

    def issue(self, request):
        if self.pending is not None or self.response is not None:
            return False
        if request.mask not in range(16) or not 0 <= request.data < 2**32:
            raise ValueError('Invalid payload')
        self.pending = (self.now + self.latency - (self.fault == 'early_completion'), request)
        return True

    def tick(self, ready=False):
        consumed = self.response if ready else None
        if ready:
            self.response = None
        self.now += 1
        if self.pending is not None and self.now >= self.pending[0]:
            _, req = self.pending
            self.pending = None
            if req.address < 0 or req.address % 4 or req.address + 4 > self.size:
                self.response = (True, 0)
            else:
                bank, row = divmod(req.address//4, len(self.words[0]))
                if self.fault == 'bank_alias':
                    bank = 0
                word = self.words[bank][row]
                if req.write:
                    for lane in range(4):
                        if req.mask & (1 << lane) or self.fault == 'masked_overwrite':
                            source = 3-lane if self.fault == 'swapped_byte' else lane
                            byte = (req.data >> (8*source)) & 255
                            word = (word & ~(255 << (8*lane))) | (byte << (8*lane))
                    self.words[bank][row] = word
                self.response = (False, 0 if req.write else word)
        return consumed
