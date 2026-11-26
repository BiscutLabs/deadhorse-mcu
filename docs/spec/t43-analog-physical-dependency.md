# T43 physical smoke dependency

Historical dependency, resolved geometrically by D111. Reproducible sources
under `analog/physical/` now generate actual LF/POR GDS and layout-derived
LEF. The final T43 checkpoint includes both macros and all SRAMs in connected
floorplan/padring/PDN checks. Electrical qualification is still separate and
open; the original reuse gaps below explain why source import alone was
insufficient. See [T43 results](../plan/tasks/reports/T43.md).

The logical production top instantiates `LfRcMacro` and `PorBrownoutMacro` with
the existing T34 interfaces. Their supply pins attach to VDD/VSS. LF enable,
trim and test retain their hardware defaults; POR retains the live threshold
selector and its supply-reset/brownout outputs. The approved pad-readback change
does not alter these interfaces.

At the original logical-binding checkpoint neither macro had physical LEF/GDS.
The pinned RISCay source at `4671317186003740ceb61360ba08c59bbdf10136`
is the reuse starting point, not a missing repository. Its
`analog/gf180-lf-osc` supplies a SPICE circuit, generator and characterization
scripts, explicitly without layout or extracted parasitics. Its historical
reported nominal frequency is 7.7307 Hz, not the current assumed 32 kHz target.
It requires an independent POR startup input and the HRES process option.
`analog/gf180-clock-reset` supplies a supply-monitor circuit, not a qualified
implementation of the current POR/brownout threshold and release contract.
Reusing these sources still requires circuit adaptation, physical layout,
extraction and qualification; copying the existing sources cannot provide
truthful placement abstracts. See [analog characterization](../../analog/characterization.md).

The current template PDK's extracted-device configuration is another concrete
adaptation requirement: `gf180mcuD.tech` selects `ppolyf_u_1k`, whereas the
RISCay candidates use the 3 kOhm/square option. The official
[wafer.space technology page](https://wafer.space/technology) advertises
high-resistance poly but does not specify that value. The
[PDK HRES rules](https://gf180mcu-pdk.readthedocs.io/en/latest/physical_verification/design_manual/drm_10_03.html)
describe its additional mask. Neither statement establishes that the existing
3 kOhm circuit may be fabricated unchanged in the selected process. Retarget
and recharacterize against the actual selected device option before layout;
do not silently mix a 3 kOhm SPICE model with a 1 kOhm extracted device.
The 0.10 mm2 LF and 0.15 mm2 POR budget rows are assumed allowances, not layouts.
Independent review confirmed that the complete T43 floorplan/macro-fit/PDN
acceptance therefore cannot be claimed with the available inputs.

Logical elaboration and pad boot simulation can use the existing named digital
analog-model fixture. Complete physical validation requires actual macro views
and supply/placement requirements from the analog implementation work. Do not
delete those instances, tie their outputs, substitute external-clock/reset pins,
or invent abstract dimensions to make a physical flow pass.

Proposed handoff: preserve the verified logical pad binding and PDK measurements;
leave T43 physical acceptance open until those macro views exist. Partial digital
floorplanning, if separately requested, must name the omitted analog scope and
cannot satisfy complete chip-fit or PDN acceptance. T38 full P&R stays unstarted.
