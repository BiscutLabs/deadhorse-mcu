ENTRY(_start)
SECTIONS {
  . = 0x80000000;
  .text : { KEEP(*(.text.start)) *(.text .text.*) }
  .rodata : { *(.rodata .rodata.* .srodata .srodata.*) }
  .data : { *(.data .data.* .sdata .sdata.*) }
  .bss (NOLOAD) : { . = ALIGN(16); __bss_start = .; *(.bss .bss.* .sbss .sbss.* COMMON) __bss_end = .; }
  /* QEMU execution space, deliberately NOT the analytical MCU allocation. */
  __stack_bottom = 0x80070000;
  __stack_top = 0x80080000;
}
