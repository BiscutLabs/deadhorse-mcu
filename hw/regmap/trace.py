"""Prepare deterministic cycle stimulus/expectations before RTL simulation."""
import argparse
import json
from pathlib import Path
import random

try:
    from .model import RegModel
except ImportError:
    from model import RegModel


def generate(path, output, seed, requests=2200):
    description = json.loads(Path(path).read_text())
    rng = random.Random(seed)
    model = RegModel(description)
    widths = {}
    for _, field, key in model.fields:
        for suffix in ('_d', '_we', '_set'):
            if key + suffix in model.inputs:
                widths[key + suffix] = 1 if suffix == '_we' else field['width']
    pending, rdata, error, accepted = False, 0, False, 0
    rows = []

    def cycle(valid=0, write=0, addr=0, data=0, strb=0, ready=0, reset_n=1, hw=None):
        nonlocal pending, rdata, error, accepted
        inputs = {k: rng.getrandbits(w) for k, w in widths.items()} if hw is None else hw
        model.drive(inputs)
        if not reset_n:
            model.reset()
            pending, rdata, error = False, 0, False
        elif valid and not pending:
            rdata, error = model.request(bool(write), addr, data, strb)
            pending = True
            accepted += 1
        else:
            model.idle()
            if pending and ready:
                pending = False
        rows.append(dict(inputs=dict(reset_n=reset_n, req_valid=valid, req_write=write, req_addr=addr,
                                     req_wdata=data, req_wstrb=strb, rsp_ready=ready, hw=inputs),
                         expected=dict(req_ready=int(not pending), rsp_valid=int(pending),
                                       rsp_rdata=rdata, rsp_error=int(error), hw=model.outputs())))

    def transfer(write, addr, data, strb):
        assert not pending
        cycle(1, write, addr, data, strb, rng.randrange(2))
        for _ in range(rng.randrange(4)):
            # Requests and live status change under backpressure; no second
            # command may be accepted and the captured response must not change.
            cycle(1, 1, addr, rng.getrandbits(32), rng.randrange(16), 0)
        cycle(1, 1, addr, rng.getrandbits(32), 15, 1)
        assert not pending

    cycle(reset_n=0)
    # Exercise every mask at every mapped address, with both zero and nonzero
    # payloads. These include read-ignore-strobes, gaps, and shared-byte commands.
    for reg in description['registers']:
        for mask in range(16):
            for data in (0, 0xFFFFFFFF):
                transfer(1, int(reg['offset']), data, mask)
            transfer(0, int(reg['offset']), 0, mask)
    addresses = [int(r['offset']) for r in description['registers']]
    for index in range(requests):
        if index % 97 == 0:
            cycle(1, 1, rng.choice(addresses), rng.getrandbits(32), 15)
            cycle(reset_n=0)  # Cancel a pending response, even while stalled.
            cycle(reset_n=0)
            cycle()
        address = rng.choice(addresses) if rng.randrange(4) else rng.getrandbits(description['address_width'])
        transfer(rng.randrange(2), address, rng.getrandbits(32), rng.randrange(16))
    cycle()
    result = dict(seed=seed, random_requests=requests, accepted_requests=accepted, cycles=rows)
    Path(output).write_text(json.dumps(result, separators=(',', ':')) + '\n')
    # A changed expectation, not changed stimulus: the same checker must fail.
    rows[1]['expected']['rsp_rdata'] ^= 1
    Path(output).with_suffix('.wrong.json').write_text(json.dumps(result, separators=(',', ':')) + '\n')
    print(f'PASS trace: seed={seed} random_requests={requests} accepted={accepted} cycles={len(rows)}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('description')
    parser.add_argument('output')
    parser.add_argument('--seed', type=int, required=True)
    args = parser.parse_args()
    generate(args.description, args.output, args.seed)
