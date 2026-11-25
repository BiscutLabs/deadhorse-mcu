# T43 physical-base choices

User-approved2026-11-25 as D109: gf180mcu_fd_io and the current sixteen1024x8 plus
four512x8 SRAM inventory. Approval does not establish physical qualification.
Independent contract review supports the options below. Approval requirements are in the
[brief](../plan/tasks/T43-wafer-space-physical-base.md).

## Verified upstream and current design

Execution query `git ls-remote https://github.com/wafer-space/gf180mcu-project-template.git
refs/heads/main` on2026-11-25 returned
`d99f6e1ba14e549e80d5d83e113fbd82ed37ed5c`. Its Makefile selects PDK
`792ef67037d74c8c51811eab3ce23cf793491296`; flake.lock selects LibreLane
`99148a9c1e648cdfdb9d7b772481af32e0dfbe8b`. These are observed repository values,
not physical qualification. Active project PDK pins remain unchanged so far.

The pinned slot declares3932x5122um die and core corners(442,442),(3490,4680).
Estimated rectangular core area is3048x4238/1e6=12.917424mm2;12.92mm2 is the
existing rounded planning budget. Pad inventory is40 bidirectional,12 ordinary
input,2 analog, plus dedicated clock/reset. Counting soc.yaml's simultaneous
functions gives40/12 digital demand, zero digital spares and2 unassigned analog
pads. BOOT_MODE shares GPIO1; AON GPIO/SPI reuse the approved muxed pad groups.
This is logical inventory, not placed pad fit.

## Pad library: recommend gf180mcu_fd_io

| Choice | Supply contract | Relevance |
| --- | --- | --- |
| `gf180mcu_fd_io` (recommended) | Core and IO rails connected; both nominal3.3V | Matches the approved common supply and powered retained RAM; template default |
| `gf180mcu_ocd_io` | Separate core/IO rails, DVDD>=VDD | Supports mixed supply voltages; no present requirement uses that capability |

This recommendation follows the pinned
[template library comparison](https://github.com/wafer-space/gf180mcu-project-template/tree/d99f6e1ba14e549e80d5d83e113fbd82ed37ed5c#pad---io-pad-libraries)
and the [OCD source](https://github.com/RTimothyEdwards/gf180mcu_ocd_io).
Both candidate PDK libraries contain3.3V characterization: TT3.30V, SS2.97V,
FF3.63V. These pad corners differ from standard-cell SS3.00V/FF3.60V; a core
Liberty corner must not be substituted for a pad corner.

The foundry bidirectional cell provides drive/slew and input-mode controls,
but [its control specification](https://gf180mcu-pdk.readthedocs.io/en/latest/IPs/IO/gf180mcu_fd_io/digital.html)
disallows simultaneous input/output enable. The adapter must explicitly preserve
the required GPIO/I2C/USB readback behavior using legal control states; it must
not silently tie both enables high. That wiring still requires scoped tests and
review. Neither pad choice establishes USB electrical compliance: pad capacitance,
edge rates, output impedance, differential thresholds, ESD and board resistors
remain qualification work. USB VBUS is an already-conditioned digital input,
not an approved direct5V connection. Approval here selects the library only.

## SRAM inventory: retain current sixteen1024x8 plus four512x8

The original request for twenty1024x8 instances predates PLAN05's watcher sizing.
Current production has16KiB main and2KiB retained RAM: sixteen1024x8 main macros
and four512x8 retained macros. Recommend configuring that exact inventory, with
no capacity or controller change. All RAM remains powered. Native orientation
is required until symmetry/rotation is qualified; do not copy the template's
rotated example placement into this design.

The candidate PDK's24 comparable production SRAM views (GDS, LEF, SPICE,
functional/blackbox Verilog and five Liberty corners for each size) are byte-
identical to the existing efdbf734 lock, measured by the T43 comparison command.
No SRAM-view replacement is needed. Retain the existing authenticated SRAM
materializer as the single design source; use matching PDK bytes only for the
unmodified upstream example. Existing SRAM physical qualification debt remains.

## Remaining physical boundary

LF oscillator and POR/brownout have behavioral models but no physical LEF/layout
or characterized footprints. The approved0.10/0.15mm2 allowances are assumptions,
not implementable macro views. A digital/SRAM floorplan experiment must preserve
these sockets and disclose the missing analog placement qualification. T38 and
the later analog brief retain physical signoff.

The unmodified template's own flow retains its documented Magic-DRC policy and
CUP exclusion; completing it is toolchain evidence, not a claim of all foundry
checks passing. No aggregate fast/full CI is planned for T43.
