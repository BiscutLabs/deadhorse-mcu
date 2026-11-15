"""One-time, byte-preserving import from explicitly pinned repository checkouts."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
IBEX = '38c070939183cc10940b66c8e9e04eeca6b65470'
RVF = 'c992aa61fdfe0846c5ed90324c596202a1c69b76'


def main():
    upstream = ROOT / 'build/t10/upstream/ibex'
    out = ROOT / 'hw/vendor/ibex_ref'
    source_list = []
    for line in (upstream / 'dv/uvm/core_ibex/ibex_dv.f').read_text().split('// Core DV files')[0].splitlines():
        if line.startswith('${'):
            name = line.split()[0].replace('${PRJ_DIR}/', '').replace('${LOWRISC_IP_DIR}/', 'vendor/lowrisc_ip/')
            if 'tracer' not in name and 'top_tracing' not in name:
                source_list.append(name)
    extra = ['LICENSE', 'CREDITS.md', 'ibex_configs.yaml', 'ibex_core.core', 'ibex_top.core',
             'doc/03_reference/rvfi.rst', 'doc/03_reference/verification.rst',
             'vendor/lowrisc_ip.lock.hjson', 'vendor/lowrisc_ip/dv/sv/dv_utils/dv_fcov_macros.svh',
             'vendor/lowrisc_ip/dv/sv/dv_utils/dv_macros.svh']
    extra += [p.relative_to(upstream).as_posix() for p in
              (upstream / 'vendor/lowrisc_ip/ip/prim/rtl').glob('*.svh')]
    extra += ['vendor/lowrisc_ip/ip/prim/rtl/prim_flop_macros.sv']
    extra += [p.relative_to(upstream).as_posix() for p in (upstream / 'rtl').glob('*.svh')]
    manifest = dict(schema=1, reference_only=True, top='ibex_top',
                    sources=source_list,
                    include_dirs=['vendor/lowrisc_ip/ip/prim/rtl', 'vendor/lowrisc_ip/dv/sv/dv_utils', 'rtl'],
                    defines=['RVFI', 'SYNTHESIS'], files={})
    sets = [('ibex', IBEX, 'https://github.com/lowRISC/ibex.git', upstream, '', set(source_list + extra))]
    rfroot = ROOT / 'build/t10/upstream/riscv-formal'
    rffiles = ['COPYING']
    for directory in ('checks', 'insns'):
        rffiles += [p.relative_to(rfroot).as_posix() for p in (rfroot / directory).iterdir() if p.is_file()]
    sets.append(('riscv-formal', RVF, 'https://github.com/YosysHQ/riscv-formal.git', rfroot, 'riscv-formal/', rffiles))
    manifest['upstreams'] = {}
    for label, revision, url, checkout, prefix, files in sets:
        actual = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != revision:
            raise RuntimeError(f'{label}: checkout does not match pin')
        manifest['upstreams'][label] = dict(url=url, revision=revision)
        for name in sorted(files):
            data = subprocess.check_output(['git', '-C', str(checkout), 'show', f'{revision}:{name}'])
            target = out / (prefix + name)
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.read_bytes() != data:
                raise RuntimeError(f'Refusing to overwrite changed vendor file: {target}')
            target.write_bytes(data)
            manifest['files'][prefix + name] = dict(upstream=label, original_path=name,
                                                   sha256=hashlib.sha256(data).hexdigest())
    (out / 'ibex_ref.lock.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Imported {len(manifest["files"])} pinned files unchanged')


if __name__ == '__main__':
    main()
