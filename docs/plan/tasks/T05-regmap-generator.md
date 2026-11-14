# T05 Register-map generator

## Goal

Build the tooling that turns one register description per block into the
Chisel register block, the C header, the documentation table and a JSON
model, as specified in
[../../spec/regmap-format.md](../../spec/regmap-format.md).

## Why

RISCay decodes its registers in a hand-written module. Deadhorse has many
more peripherals and two cores reading the same registers; a single source
prevents the RTL, firmware and documents from disagreeing.

## Read first

- [../../../AGENTS.md](../../../AGENTS.md)
- [../../spec/regmap-format.md](../../spec/regmap-format.md), all of it. It
  is the specification. Where this brief and the spec differ, stop and ask.
- [../../spec/actuator-block.md](../../spec/actuator-block.md), the
  "Registers" table. It is your first real input.
- `hw/lib/src/main/scala/deadhorse/lib/Hello.scala` and its spec and
  emitter from T07, for the house style and the simulation harness.

## Inputs

- T01 and T07 complete, with the Chisel toolchain environment loaded.
- Python 3.10 or later, `pip install pyyaml`, Icarus Verilog.

## Split of work

| Part | Language | Why |
| --- | --- | --- |
| Validation, JSON, C header, documentation | Python, `hw/regmap/regmap.py` | No hardware; runs without the Chisel toolchain |
| Register block hardware | Chisel, `deadhorse.lib.RegBlock` | Deadhorse RTL is Chisel (decision D16) |
| Reference model | Python, `hw/regmap/model.py` | Independent of the hardware generator |

## May change

New files under `hw/regmap/`, `hw/lib/src/main/scala/deadhorse/lib/`
(`RegBlock.scala`, `RegBus.scala`), `hw/lib/src/test/scala/deadhorse/lib/`
(`RegBlockSpec.scala`), `hw/ip/actuator/` (`actuator.regmap.yaml`,
`README.md`, `src/main/scala/.gitkeep`), `tools/ci.py`, and your report.

## Steps

1. **Python front end** `hw/regmap/regmap.py`:

   ```
   python3 hw/regmap/regmap.py <file.regmap.yaml> --out build/regmap/<block>
   ```

   It validates the description, reports the first violation as
   `ERROR_NAME: message` on standard error with exit status 1, and otherwise
   writes `<block>_regs.json`, `<block>_regs.h` and `<block>_regs.md`.
   Implement every row of the spec's error table. Unknown keys are errors.
2. **Header.** For each register `DH_<BLOCK>_<REG>_OFFSET`; for each field
   `_<FIELD>_SHIFT` and `_<FIELD>_MASK` (mask already shifted). Include
   guards. Array registers expand to `<NAME>0`, `<NAME>1`, and so on.
3. **Chisel bus bundle** `RegBus`: the request and response signals in the
   spec's "Bus port" table, as one `Bundle` with a target and an initiator
   view.
4. **Chisel register block** `RegBlock(json: os.Path or String)`: a `Module`
   that reads the validated JSON at elaboration and builds the registers,
   the decode and one hardware-side port per field as the spec's access
   table defines. Port names follow the spec. It must not re-validate or
   reinterpret the YAML; the JSON is its only input.
5. **Reference model** `hw/regmap/model.py`: a Python class built from the
   same JSON with `request(write, addr, wdata, wstrb) -> (rdata, error)` and
   methods to drive the hardware-side inputs and read the outputs. It
   implements the spec's behaviour rules independently. Do not port the
   Chisel logic into it or the reverse.
6. **Actuator description** `hw/ip/actuator/actuator.regmap.yaml`
   transcribed from the actuator spec's register table. The `mode`, `value`
   and `fs_value` registers are arrays of nine.
7. **Tests.**
   - `hw/regmap/test_regmap.py` (`unittest`): one test per error name, each
     with a minimal description that triggers only that error; header
     contents for the actuator description.
   - `RegBlockSpec.scala`: for the actuator description and for a second
     description you write that uses every access type, emit SystemVerilog
     for `RegBlock`, then drive at least 2,000 random bus requests and random
     hardware-side inputs and compare every response and every hardware
     output with the Python model's answers. Generate the stimulus and the
     expected results with the Python model ahead of the simulation and read
     them as a file. Fixed seed, printed.
   - One **negative control**: run the same comparison against a
     deliberately wrong expectation file (for example, two byte strobes
     swapped in the model) and assert the spec fails. A test that cannot
     fail proves nothing.
8. **CI.** `tools/ci.py` always runs `test_regmap.py`; the Chisel spec runs
   with the rest of `hw/test` when the toolchain is configured.

## Acceptance checks

```sh
python3 -m unittest hw/regmap/test_regmap.py -v
python3 hw/regmap/regmap.py hw/ip/actuator/actuator.regmap.yaml --out build/regmap/actuator
ls build/regmap/actuator      # actuator_regs.json .h .md
grep "DH_ACTUATOR_VALUE8_OFFSET" build/regmap/actuator/actuator_regs.h       # value 0xA0
python3 tools/sbt.py "hw/testOnly deadhorse.lib.RegBlockSpec"                # passes, includes the negative control
git status --short | grep -c "build/"                                        # 0
python3 tools/ci.py                                                          # PASS
```

## Stop and ask

- The spec is ambiguous or contradicts itself. Quote the two passages.
- The actuator table cannot be expressed in the format. Say which row. Do
  not extend the format on your own.
- You want a new access type or a new YAML key.
- Reading JSON at elaboration needs a library that is not already on the
  classpath (T07). Name it and wait.

## Out of scope

The actuator block's logic (pulse generators, failsafe), bus bridges, and
connecting anything to a core.
