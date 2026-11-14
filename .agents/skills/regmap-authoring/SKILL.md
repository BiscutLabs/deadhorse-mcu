---
name: "regmap-authoring"
description: "Use when describing a Deadhorse MCU peripheral's registers in the project's register-map YAML format, choosing field access types, or reviewing a register description."
---

# Register-map authoring (Deadhorse)

One register description per block is the single source for the block's
register hardware, the C header, the documentation table and the reference
model. Decode is never hand-written. The format is specified in
`docs/spec/regmap-format.md`; that document wins over this skill. A worked
example is the actuator block: `docs/spec/actuator-block.md`.

## File

`hw/ip/<block>/<block>.regmap.yaml`

```yaml
block: actuator            # lower snake case; equals the directory name
description: Nine-channel actuator output block
data_width: 32             # only 32
address_width: 8           # bits of byte address decoded in the block
registers:
  - name: ctrl
    offset: 0x00           # byte offset, multiple of 4, unique
    description: Global control
    fields:
      - name: enable
        bits: 0            # one bit, or [msb, lsb]
        access: rw
        reset: 0
      - name: tick_div
        bits: [15, 8]
        access: rw
        reset: 5
  - name: value            # array: value0 .. value8 at 0x80, 0x84, ...
    offset: 0x80
    count: 9
    fields:
      - name: v
        bits: [15, 0]
        access: rw
        reset: 0
```

## Choosing the access type

| The field is... | Use | Software sees | Hardware gets |
| --- | --- | --- | --- |
| A setting software owns | `rw` | Reads back what it wrote | The stored value |
| A status hardware owns | `ro` | The live hardware value | Drives the value in |
| A sticky event or error flag | `w1c` | Set by hardware; writing 1 clears | A set input; set wins over a simultaneous clear |
| A command: start, commit, flush | `w1p` | Reads 0 | A one-cycle pulse |
| A value both sides update, such as a counter software can preload | `rwh` | The stored value | The value, plus a hardware write port; hardware wins |
| A write-only value hardware interprets, such as a key | `wo` | Reads 0 | The written data and a one-cycle write strobe |

If none fits, stop and ask. Do not invent an access type or a YAML key:
unknown keys are errors.

## Design rules for a good register map

1. **Write the table in the block's spec first,** then transcribe it. The
   YAML and the spec table must agree line for line.
2. **One purpose per register.** Do not mix command bits (`w1p`) with
   settings (`rw`) in one register: a read-modify-write of the settings
   would otherwise have to care about the command bits.
3. **Group for atomic use.** Values that must change together go through
   shadow registers and one commit pulse, as the actuator block does. Do not
   rely on software writing several registers fast enough.
4. **Status that software must not miss is `w1c`,** not `ro`. A live `ro`
   bit can change between two reads.
5. **Dangerous actions need a key.** Arming, unlocking or erasing takes a
   `wo` register compared against a constant in hardware, with a `w1c`
   status bit for a wrong key.
6. **Reset values are safe values:** outputs disabled, interrupts masked,
   peripherals idle.
7. **Leave gaps.** Start arrays on round offsets and leave room after
   registers likely to grow. Offsets are forever once firmware uses them.
8. **Reserved bits read 0** and are not given names. Do not define a field
   until it does something.
9. **Fields that cross a byte boundary** are fine, but remember byte strobes:
   a write with a strobe clear leaves that byte of an `rw` field unchanged.
10. **Name things for firmware.** Names become `DH_<BLOCK>_<REG>_<FIELD>`
    macros. Lower snake case, no SystemVerilog or C keywords.

## Before running the generator, check by hand

| Check | Generator error if wrong |
| --- | --- |
| Names are lower snake case and not keywords | `REGMAP_NAME` |
| Offsets are multiples of 4 | `REGMAP_OFFSET_ALIGN` |
| Every offset, and the end of every array, fits `address_width` | `REGMAP_OFFSET_RANGE` |
| No two registers, counting array elements, share an offset | `REGMAP_OVERLAP_REG` |
| No two fields of a register share a bit | `REGMAP_OVERLAP_FIELD` |
| Bit indices are 0 to 31 and msb is at least lsb | `REGMAP_BITS` |
| Reset values fit their field; none on `ro`, `w1p` or `wo` | `REGMAP_RESET` |
| Access types are from the table above | `REGMAP_ACCESS` |
| No duplicate register names, or field names within a register | `REGMAP_DUP` |
| No YAML key outside the format | `REGMAP_UNKNOWN_KEY` |

A quick arithmetic check for arrays: the last element is at
`offset + 4 * (count - 1)`. For the actuator block, `value8` is at
`0x80 + 32 = 0xA0`.

## Bus behaviour to keep in mind

- One transaction may be outstanding; each accepted request gets exactly
  one response.
- An unmapped or misaligned address returns an error and changes nothing.
- Unmapped bits of a mapped register read 0.

## After generating

- Generated files go under `build/regmap/<block>/` and are never committed.
- Read the generated documentation table against the spec table.
- The generated register block comes with generated formal properties and a
  reference model; run both before connecting the block's own logic.

## Stop and ask

- The peripheral needs behaviour no access type provides.
- Two requirements conflict, such as a field both software and hardware
  must win.
- An existing register's offset or meaning would have to change after
  firmware has used it.

## Status of this skill

The format is a project draft and the generator had not been built when this
was written. Check the current `docs/spec/regmap-format.md` before relying
on any detail here.