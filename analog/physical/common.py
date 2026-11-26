"""Shared authentication and receipts for D111 layout generation."""
import atexit
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Evidence:
    def __init__(self, output, script, pdk=None):
        self.output = Path(output)
        self.started = time.monotonic()
        self.data = dict(status='incomplete_or_failed', command=sys.argv,
                         inputs={}, tools={}, scope='Development views, not analog qualification')
        self.add_inputs([Path(__file__), Path(script)])
        executable = Path(sys.executable).resolve()
        self.data['tools']['interpreter'] = dict(path=str(executable),
                                                 sha256=sha(executable),
                                                 version=sys.version)
        # Record native extension identities as well as the Python launcher.
        for name, module in list(sys.modules.items()):
            path = getattr(module, '__file__', None)
            if path and name.split('.')[0] in ('pya', 'klayout', 'odb'):
                path = Path(path).resolve()
                if path.is_file():
                    self.data['tools'][name] = dict(path=str(path), sha256=sha(path))
        atexit.register(self.write)
        if pdk is not None:
            self.authenticate_magic(Path(pdk))

    def add_inputs(self, paths):
        for path in paths:
            path = Path(path).resolve()
            digest = sha(path)
            assert self.data['inputs'].get(str(path), digest) == digest, path
            self.data['inputs'][str(path)] = digest

    def authenticate_magic(self, pdk):
        lock_path = ROOT / 'analog/physical/inputs.lock.json'
        library_path = ROOT / 'analog/physical/library-inputs.lock.json'
        self.add_inputs([lock_path, library_path])
        lock = json.loads(lock_path.read_text())
        library = json.loads(library_path.read_text())
        assert library['revision'] == lock['pdk_revision']
        for name, expected in library['files'].items():
            path = pdk / name
            assert sha(path) == expected, ('Unpinned PDK input', name)
            self.add_inputs([path])
        tree = Path(lock['magic_store_path'])
        files = {str(p.relative_to(tree)): sha(p)
                 for p in sorted(tree.rglob('*')) if p.is_file()}
        digest = hashlib.sha256(json.dumps(files, sort_keys=True,
                                         separators=(',', ':')).encode()).hexdigest()
        assert digest == lock['magic_output_tree_sha256'], 'Unpinned Magic tree'
        self.magic = tree / 'bin/magic'
        assert sha(self.magic) == lock['magic_executable_sha256']
        self.data['tools']['magic'] = dict(path=str(self.magic), files=files,
                                           tree_sha256=digest)
        for name, expected in lock['initialization_sha256'].items():
            assert sha(pdk / 'libs.tech/magic' / name) == expected, name
        assert sha(pdk / 'libs.tech/magic/gf180mcuD.tech') == lock['original_tech_sha256']

    def finish(self, status='generated_requires_checks'):
        # Detect a changing input during generation rather than blessing it.
        for name, expected in self.data['inputs'].items():
            assert sha(name) == expected, ('Input changed during run', name)
        self.data['status'] = status

    def write(self):
        if not self.output.exists():
            return
        self.data['seconds'] = time.monotonic() - self.started
        self.data['artifacts'] = {
            str(p.relative_to(self.output)): sha(p)
            for p in sorted(self.output.rglob('*'))
            if p.is_file() and p.name != 'provenance.json'}
        (self.output / 'provenance.json').write_text(
            json.dumps(self.data, indent=2) + '\n')


def lf_port_bindings(mapped):
    names = dict(source=('input', 'clock'), power_n=('input', 'init_n'),
                 enable=('input', 'enable'), ready=('output', 'ready'))
    assert set(mapped['ports']) == set(names), 'Unexpected readiness interface'
    bindings = {'0': 'vss', '1': 'vdd'}
    for name, (direction, net) in names.items():
        port = mapped['ports'][name]
        assert port['direction'] == direction and len(port['bits']) == 1, name
        bit = port['bits'][0]
        assert isinstance(bit, int) and bit not in bindings, (name, bit)
        bindings[bit] = net
    return bindings


def spice_ports(text, top, expected):
    logical = []
    for line in text.splitlines():
        if line.startswith('+'):
            assert logical
            logical[-1] += ' ' + line[1:]
        else:
            logical.append(line)
    headers = [line.split()[2:] for line in logical
               if line.lower().startswith('.subckt ' + top.lower() + ' ')]
    assert len(headers) == 1
    assert len(headers[0]) == len(expected) and set(headers[0]) == set(expected)
    return headers[0]
