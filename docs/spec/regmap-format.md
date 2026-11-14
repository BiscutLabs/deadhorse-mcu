# Register-map description format

Draft v0.1, 2026-11-13. Proposed; not yet implemented. This is the input
format for the generator built in task T05. One description per block is the
single source for the RTL decode, the C header and the documentation.

## File

`hw/ip/<block>/<block>.regmap.yaml`. UTF-8 YAML, a single mapping.

```yaml
block: actuator            # lower snake case; must equal the directory name
description: Nine-channel actuator output block
data_width: 32             # only 32 is supported
address_width: 8           # bits of byte address decoded inside the block
registers:
  - name: ctrl             # lower snake case, unique in the block
    offset: 0x00           # byte offset, multiple of 4, unique
    description: Global control
    fields:
      - name: enable
        bits: 0            # a single bit, or [msb, lsb]
        access: rw
        reset: 0
        description: Enable the output generators
      - name: tick_div
        bits: [15, 8]
        access: rw
        reset: 5
  - name: commit
    offset: 0x04
    fields:
      - name: go
        bits: 0
        access: w1p        # write 1 pulses for one cycle; reads 0
  - name: value            # an array of identical registers
    offset: 0x40
    count: 9               # value0 .. value8 at 0x40, 0x44, ...
    fields:
      - name: v
        bits: [15, 0]
        access: rw
        reset: 0
```

## Field access types

| `access` | Software read | Software write | Hardware port generated |
| --- | --- | --- | --- |
| `rw` | Stored value | Stores, honouring byte strobes | `<reg>_<field>_q` output |
| `ro` | Hardware value | Ignored | `<reg>_<field>_d` input |
| `w1c` | Stored value | Writing 1 clears the bit | `<reg>_<field>_set` input (set wins over clear), `_q` output |
| `w1p` | 0 | Writing 1 gives a one-cycle pulse | `<reg>_<field>_pulse` output |
| `rwh` | Stored value | Stores | `_q` output, plus `_d` and `_we` inputs for hardware update (hardware wins) |
| `wo` | 0 | Not stored | `<reg>_<field>_wdata` output and a one-cycle `<reg>_<field>_we` pulse |

## Rules the generator must enforce

Each violation is a named error and a non-zero exit.

| Error | Condition |
| --- | --- |
| `REGMAP_NAME` | A block, register or field name is not lower snake case, or is a SystemVerilog or C keyword |
| `REGMAP_OFFSET_ALIGN` | An offset is not a multiple of 4 |
| `REGMAP_OFFSET_RANGE` | An offset, or the end of an array, does not fit in `address_width` |
| `REGMAP_OVERLAP_REG` | Two registers, including array elements, share an offset |
| `REGMAP_OVERLAP_FIELD` | Two fields of one register share a bit |
| `REGMAP_BITS` | A bit index is outside 0 to 31, or msb is less than lsb |
| `REGMAP_RESET` | A reset value does not fit the field, or is given for `ro`, `w1p` or `wo` |
| `REGMAP_ACCESS` | An unknown access type |
| `REGMAP_DUP` | A duplicate register name, or a duplicate field name within a register |
| `REGMAP_UNKNOWN_KEY` | Any YAML key not defined here |

## Generated bus port

The clocked reference uses this port. One transaction may be outstanding.

| Signal | Direction | Width | Meaning |
| --- | --- | ---: | --- |
| `clk`, `rst_n` | in | 1 | Clock; asynchronous active-low reset |
| `req_valid` | in | 1 | Request offered |
| `req_ready` | out | 1 | Request accepted this cycle |
| `req_write` | in | 1 | 1 = write |
| `req_addr` | in | `address_width` | Byte address; bits 1:0 must be 0 |
| `req_wdata` | in | 32 | Write data |
| `req_wstrb` | in | 4 | Byte strobes |
| `rsp_valid` | out | 1 | Response offered |
| `rsp_ready` | in | 1 | Response accepted this cycle |
| `rsp_rdata` | out | 32 | Read data; 0 on a write or an error |
| `rsp_error` | out | 1 | Decode or access error |

Behaviour:

- A request is accepted when `req_valid && req_ready`. Exactly one response
  follows each accepted request. `req_ready` is low while a response is
  pending.
- Unmapped offset, or misaligned address: `rsp_error` = 1, no state change.
- A read of a register returns 0 in unmapped bits.
- A write with a strobe bit clear leaves that byte of every `rw` field
  unchanged. `w1c` and `w1p` act only on bytes whose strobe is set.
- All stored fields reset to their `reset` value (0 if absent) on `rst_n`.

## Generated files

Written under `build/regmap/<block>/`, never committed.

| File | Contents |
| --- | --- |
| `<block>_regs.sv` | One module `<block>_regs` with the bus port and the hardware ports above. Plain SystemVerilog without interfaces, packages or structs, so that yosys, sv2v and Icarus all read it |
| `<block>_regs.h` | `#define` offsets, masks and shifts, prefixed `DH_<BLOCK>_` |
| `<block>_regs.md` | A register table for the documentation |
| `<block>_regs.json` | The validated description, with array elements expanded, for the reference model |
