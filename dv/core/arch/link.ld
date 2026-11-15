OUTPUT_ARCH(riscv)
ENTRY(_start)
SECTIONS {
  .text 0x80000080 : { *(.text.start) *(.text*) }
  .rodata : { *(.rodata*) }
  .data : { *(.data*) }
  .bss : { *(.bss*) *(COMMON) }
}
