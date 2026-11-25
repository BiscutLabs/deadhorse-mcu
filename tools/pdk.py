"""Authenticated active GF180 views; historical receipts retain their old inputs."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / 'phys/gf180-ws-1x1/pdk-lock.json'


def root():
    path = (ROOT / json.loads(LOCK.read_text())['root']).resolve()
    path.relative_to(ROOT / 'build')
    return path


def view(relative):
    path = (root() / relative).resolve()
    path.relative_to(root())
    expected = json.loads(LOCK.read_text())['files'][path.name]
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError('PDK view hash mismatch: ' + str(path))
    return path


def liberty(corner='ss_125C_3v00'):
    name = 'gf180mcu_fd_sc_mcu7t5v0'
    return view(f'libs.ref/{name}/lib/{name}__{corner}.lib')


def models():
    return [view('libs.ref/gf180mcu_fd_sc_mcu7t5v0/verilog/' + name)
            for name in ('gf180mcu_fd_sc_mcu7t5v0.v', 'primitives.v')]
