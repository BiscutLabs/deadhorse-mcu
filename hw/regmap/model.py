"""Specification model: individual field bits, with no hardware decode machinery."""
import json
from pathlib import Path


class RegModel:
    def __init__(self, description):
        if isinstance(description, (str, Path)):
            description = json.loads(Path(description).read_text())
        self.description = description
        self.registers = {int(r['offset']): r for r in description['registers']}
        self.fields = [(r, f, r['name'] + '_' + f['name'])
                       for r in description['registers'] for f in r['fields']]
        self.inputs = {}
        for _, field, key in self.fields:
            if field['access'] in ('ro', 'rwh'):
                self.inputs[key + '_d'] = 0
            if field['access'] == 'rwh':
                self.inputs[key + '_we'] = 0
            if field['access'] == 'w1c':
                self.inputs[key + '_set'] = 0
        self.reset()

    def reset(self):
        self.bits = {key: [bool(field.get('reset', 0) & (1 << bit)) for bit in range(field['width'])]
                     for _, field, key in self.fields if field['access'] in ('rw', 'rwh', 'w1c')}
        self.transient = {}
        self._clear_pulses()

    def _clear_pulses(self):
        for _, field, key in self.fields:
            if field['access'] == 'w1p':
                self.transient[key + '_pulse'] = 0
            if field['access'] == 'wo':
                self.transient[key + '_we'] = 0
                self.transient[key + '_wdata'] = 0

    def drive(self, values):
        for key, value in values.items():
            if key not in self.inputs:
                raise KeyError(key)
            self.inputs[key] = value

    def outputs(self):
        values = dict(self.transient)
        for key, bits in self.bits.items():
            values[key + '_q'] = sum(1 << n for n, bit in enumerate(bits) if bit)
        return values

    def _edge(self, write=False, register=None, data=0, lanes=0):
        self._clear_pulses()
        for reg, field, key in self.fields:
            access = field['access']
            enabled = write and reg is register
            selected = [enabled and bool(lanes & (1 << (bit // 8)))
                        for bit in range(field['lsb'], field['msb'] + 1)]
            supplied = [bool(data & (1 << bit)) for bit in range(field['lsb'], field['msb'] + 1)]
            if access in ('rw', 'rwh', 'w1c'):
                for n in range(field['width']):
                    if selected[n]:
                        if access == 'w1c':
                            if supplied[n]:
                                self.bits[key][n] = False
                        else:
                            self.bits[key][n] = supplied[n]
                    # Hardware precedence is applied after software effects.
                    if access == 'w1c' and self.inputs[key + '_set'] & (1 << n):
                        self.bits[key][n] = True
                    if access == 'rwh' and self.inputs[key + '_we']:
                        self.bits[key][n] = bool(self.inputs[key + '_d'] & (1 << n))
            elif access == 'w1p':
                self.transient[key + '_pulse'] = sum(1 << n for n in range(field['width'])
                                                     if selected[n] and supplied[n])
            elif access == 'wo' and any(selected):
                self.transient[key + '_we'] = 1
                self.transient[key + '_wdata'] = sum(1 << n for n, bit in enumerate(supplied) if bit)

    def idle(self):
        self._edge()

    def request(self, write, addr, wdata, wstrb):
        register = self.registers.get(addr)
        error = register is None or addr % 4 != 0
        if write and not error:
            for field in register['fields']:
                if field['access'] == 'wo':
                    covered = [bool(wstrb & (1 << (bit // 8)))
                               for bit in range(field['lsb'], field['msb'] + 1)]
                    if any(covered) and not all(covered):
                        error = True
        read = 0
        if not write and not error:
            for field in register['fields']:
                key = register['name'] + '_' + field['name']
                if field['access'] == 'ro':
                    value = self.inputs[key + '_d'] & ((1 << field['width']) - 1)
                elif field['access'] in ('rw', 'rwh', 'w1c'):
                    value = sum(1 << n for n, bit in enumerate(self.bits[key]) if bit)
                else:
                    value = 0
                read |= value << field['lsb']
        self._edge(write and not error, register, wdata, wstrb)
        return read, bool(error)
