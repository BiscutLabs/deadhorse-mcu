"""Pinned LibreLane chip steps that retain the original graph for T38 audits.

Only physical optimization policy changes: suppress pin swapping and protect
original inverters during CTS inverter replication. All limits remain upstream.
"""
import hashlib
import json
import os
from pathlib import Path
import re

import librelane
from librelane.flows import Flow
from librelane.steps import Step, openroad
from librelane.__main__ import cli

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = Path(librelane.__file__).resolve().parent / 'scripts/openroad'
PINNED = {
    'cts.tcl': '436f4f89f290f14cc2c982907af79a8a79f9f56b64e9bfe83ff63636ce6608d5',
    'rsz_timing_postcts.tcl': 'ced0c9fff47b7f778aefec4083d4a49465ea2f91758f27463d00c7ed7e6dc0d1',
    'rsz_timing_postgrt.tcl': '17a7b1f4a7bce58cd2e33f6b7fc4a9a822a3332cee8901216184897e437ddec3',
    'common/resizer.tcl': '3a18e9571c3ff083b1e419a1dbf821fc4207c4a697f38352dfb39ff5195c869c',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wrapper(step, upstream, body, additional=None):
    hashes = {str(SCRIPTS / name): sha(SCRIPTS / name) for name in PINNED}
    assert all(hashes[str(SCRIPTS / name)] == digest for name, digest in PINNED.items())
    path = Path(step.step_dir) / 't38-preserve.tcl'
    path.write_text(body + f'\nsource {{{SCRIPTS / upstream}}}\n')
    receipt = dict(upstream_sha256=hashes, wrapper_sha256=sha(path),
                   source_sha256=sha(Path(__file__)), additional=additional)
    (path.parent / 't38-preserve.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return str(path)


TIMING = '''rename repair_timing t38_original_repair_timing
proc repair_timing {args} {
    puts "T38_PRESERVE repair_timing: adding -skip_pin_swap"
    return [uplevel 1 [list t38_original_repair_timing {*}$args -skip_pin_swap]]
}
'''


@Step.factory.register()
class PreservedCTS(openroad.CTS):
    id = 'T38.CTS'

    def get_script_path(self):
        mapped = Path(os.environ.get('CHIP_PRESERVE_MAP', str(ROOT / 'build/t38/map07/physical.json'))).resolve()
        mapped.relative_to(ROOT / 'build')
        receipt_path = mapped.parent / 'result.json'
        receipt = json.loads(receipt_path.read_text())
        assert receipt['status'] == 'pass'
        assert sha(mapped) == receipt['artifact_sha256']['physical.json']
        cells = json.loads(mapped.read_text())['modules']['chip_top']['cells']
        rows = []
        for name, cell in sorted(cells.items()):
            match = re.fullmatch(r'(gf180mcu_fd_sc_mcu7t5v0__(?:inv|clkinv))_(1|2|4|8|16)', cell['type'])
            if match:
                assert not any(c in name for c in '{}\\\n')
                rows.append('{' + name + ' ' + match[1] + '}')
        assert rows
        body = 'set t38_original_inverters {' + ' '.join(rows) + '}\n' + '''
rename repair_clock_inverters t38_original_repair_clock_inverters
proc repair_clock_inverters {args} {
    global t38_original_inverters
    set saved [list]
    set block [ord::get_db_block]
    try {
        foreach row $t38_original_inverters {
            lassign $row name family
            set inst [$block findInst $name]
            if {$inst eq "NULL"} {error "Missing original inverter: $name"}
            set master [[$inst getMaster] getName]
            if {![regexp "^${family}_(1|2|4|8|16)$" $master]} {
                error "Changed original inverter family: $name $master"
            }
            lappend saved [list $inst [$inst isDoNotTouch]]
            $inst setDoNotTouch true
        }
        puts "T38_PRESERVE repair_clock_inverters: protected [llength $saved] original inverters"
        return [uplevel 1 [list t38_original_repair_clock_inverters {*}$args]]
    } finally {
        foreach row $saved {
            lassign $row inst prior
            $inst setDoNotTouch $prior
        }
    }
}
'''
        return wrapper(self, 'cts.tcl', body,
                       dict(map_sha256=sha(mapped), receipt_sha256=sha(receipt_path), inverters=len(rows)))


@Step.factory.register()
class PreservedPostCTS(openroad.ResizerTimingPostCTS):
    id = 'T38.ResizerTimingPostCTS'

    def get_script_path(self):
        return wrapper(self, 'rsz_timing_postcts.tcl', TIMING)


@Step.factory.register()
class PreservedPostGRT(openroad.ResizerTimingPostGRT):
    id = 'T38.ResizerTimingPostGRT'

    def get_script_path(self):
        return wrapper(self, 'rsz_timing_postgrt.tcl', TIMING)


@Flow.factory.register('T38Chip')
class T38Chip(Flow.factory.get('Chip').Substitute({
    'OpenROAD.CTS': PreservedCTS,
    'OpenROAD.ResizerTimingPostCTS': PreservedPostCTS,
    'OpenROAD.ResizerTimingPostGRT': PreservedPostGRT,
})):
    pass


if __name__ == '__main__':
    # The pinned CLI snapshots registered flows when imported, before the
    # decorators above run. Refresh only that option's existing choice list.
    import click
    option = next(p for p in cli.params if p.name == 'flow_name')
    option.type = click.Choice(Flow.factory.list(), case_sensitive=False)
    cli()
