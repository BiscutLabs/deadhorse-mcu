OUTPUT_ARCH(riscv)
ENTRY(_start)
SECTIONS
{
    . = 0x80000000;
    .text : { *(.text.start) *(.text .text.*) }
    .rodata : { *(.rodata .rodata.* .srodata .srodata.*) }
    .data : { *(.data .data.* .sdata .sdata.*) }
    .bss : { *(.bss .bss.* .sbss .sbss.* COMMON) }
    _end = .;
    _stack_top = 0x80000000 + 0x300000;
    /DISCARD/ : { *(.comment) *(.riscv.attributes) *(.eh_frame*) }
}
