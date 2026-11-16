# ID selector priority analysis

Status: single-qualifier formal-analysis normalization approved and verified. The approved
CSR normalization is implemented and qualified separately. The original ID
comparison failure is retained as historical evidence. Accepted qualification
uses the explicitly approved analysis model, not the old optimized reference.

Accepted root receipts: `build/t11/id2/leaves/id_stage`, all configured cases
at `build/t11/id2/leaves`, and top reference-copy proof/faults at
`build/t11/id2/top_reference_copy`. Independent accepted review and reruns are
under `build/t11/id2/independent-review`. No input assumptions were added.

## Counterexample and scope

`IbexIdStage` instantiates the translated decoder and controller, retains the
reference intermediate registers, branch bookkeeping and first/multicycle FSM,
and preserves the pinned two-stage behavior. Reference line 809 is a
`unique case (1'b1)` with procedural priority LSU, mult/div, branch, jump, then
multicycle ALU.

The original failed proof at `build/t11/id1/equiv` supplies FENCE.I
(`instr_rdata_i=0x02f0100f`) and DIV in the independent ALU copy
(`instr_rdata_alu_i=0x02004033`). The reference's parallel unique-case lowering
permits a jump side effect; procedural priority suppresses it while mult/div
stalls. The first differing output is `perf_jump_o`. The Chisel priority chain
matches the source's case order; no input assumption was introduced.

The counterexample violates the reference's duplicate-instruction and unique
multicycle-enable assertions. The integrated IF writes both instruction copies
from the same source with the same enable, so intended valid traffic cannot
produce it. However, current arbitrary-state induction preserves distinct
payload state bits and does not establish that reachable-state invariant.
Assuming equal copies in the standalone proof would narrow its input domain.

The proposed resolution removes only `unique ` at line 809 in a generated
formal-analysis copy. Every case arm/default, port, state/output obligation,
input combination and negative control stays. Vendor and production RTL stay
unchanged. This would explicitly change the analysis model to source priority,
as already approved for the two CSR selectors; that approval does not yet cover
the additional ID selector.

An alternative is an integrated reachable-state proof with a separately proved
IF invariant and a revised standalone acceptance contract. It needs additional
proof machinery and an explicit acceptance decision. Silently changing Chisel
to a parallel completion would not preserve unrestricted source priority.

Pinned source SHA-256:
`077a8a4035b9330c32c23bf68a45fff00f69dca322582cdbdc53ff77fdab3e21`.
Trial normalized SHA-256:
`ed6b27180db1bc58810118a00b06a505bd71b498b393b12e22a77dd346b16ac8`.

## Measurements and review

Base `a5323044dfe4f7a8ddb8aee5ad75c2ce12ed06bb` plus working changes;
commands run through `python tools/env/run.py run --`:

```text
python3 tools/sbt.py "hw/runMain deadhorse.perf_core.EmitLeaves build/t11/id1/emit"
[success] Total time: 14 s
python3 dv/core/equiv.py --module ibex_id_stage --candidate build/t11/id1/emit/id_stage/ibex_id_stage.sv --replace ibex_decoder=build/t11/id1/emit/id_stage/ibex_decoder.sv --replace ibex_controller=build/t11/id1/emit/id_stage/ibex_controller.sv --self-check --output build/t11/id1/equiv
FAILED equivalence: ibex_id_stage
python3 scratch/check_id_priority.py
PROVED equivalence: ibex_id_stage
['output', 'reset-value', 'next-state']
python3 tools/sbt.py "hw/testOnly deadhorse.perf_core.IdStageSpec"
Tests: succeeded 2, failed 0; All tests passed.
python3 tools/timing/check.py --top ibex_id_stage --source build/t11/id1/emit/id_stage/ibex_id_stage.sv --source build/t11/id1/emit/id_stage/ibex_decoder.sv --source build/t11/id1/emit/id_stage/ibex_controller.sv --clock clk_i --output build/t11/id1/timing
PASS ibex_id_stage: 24.466211 ns, budget 24.960000 ns; electrical violations 0
```

The trial proves 15 state elements without environmental assumptions and rejects
all three faults. Timing measures **29215.9168 um2** cell area, unchanged
assumed **24.96 ns** budget, GF180 SS/125C/3.0V, ideal clock/no wire delay.
These are mapped block measurements, not whole-core or post-layout signoff.
The behavioral tests check instruction operand selection, write suppression,
multiply completion, load request/response/address increment, taken/untaken
branches, jumps, CSR routing, intermediate-word order/enables and conflicting
copy priority. The corrupt-operand control is rejected.

Independent reviewer `csr_review` reproduced the original failure, then freshly
elaborated both sides for the trial at `build/t11/id1/independent-priority`,
verified byte-for-byte reversal, and reproduced proof/faults, both tests and
timing. They recommend this precise proposal for approval. They also checked
the remaining `ibex_core`/`ibex_top` sources: no additional `case (1'b1)` or
unique-if selectors; core's remaining unique case has disjoint literal values.

After approval, enforce the pinned hash/one exact location/reversal, include
normalization identity and explicit defaults in success/fault receipts, use
fresh emission, qualify ID/core/top routes, and obtain independent review.
Until then this trial is not an accepted proof baseline. The configured leaf
gate includes the original ID comparison and therefore remains unresolved.
