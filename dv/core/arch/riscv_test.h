/* Deadhorse port of the riscv-tests test-environment macro interface.
 * Test bodies/macros remain byte-identical to the pinned upstream source.
 * Machine-mode bare-metal execution; no privileged test setup is required.
 */
#ifndef DEADHORSE_RISCV_TEST_H
#define DEADHORSE_RISCV_TEST_H
#define RVTEST_RV32U
#define RVTEST_RV64U
#define TESTNUM x3
#define RVTEST_CODE_BEGIN \
 .section .text.start; .globl _start; .option norvc; _start: j test_entry; \
 .section .text; test_entry:; \
 .irp reg,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31; \
 addi x\reg,x0,0; .endr
#define RVTEST_CODE_END
#define RVTEST_PASS li t0,0x100000; li t1,0x5555; sw t1,0(t0); 987: j 987b
#define RVTEST_FAIL li t0,0x100000; li t1,0x3333; sw t1,0(t0); 988: j 988b
#define RVTEST_DATA_BEGIN .balign 16; .globl begin_signature; begin_signature:
#define RVTEST_DATA_END .balign 16; .globl end_signature; end_signature:
#endif
