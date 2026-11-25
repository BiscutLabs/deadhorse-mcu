ENTRY(_start)
MEMORY {
  program (rx) : ORIGIN = 0x30000000, LENGTH = 1024
  data (rw) : ORIGIN = 0x30000400, LENGTH = 1024
}
SECTIONS {
  .text : { *(.start) *(.text*) } > program
  .rodata : { *(.rodata*) } > program
  .data : { *(.data*) } > data
  .bss (NOLOAD) : {
    . = ALIGN(4); __bss_start = .;
    *(.bss*) *(COMMON)
    . = ALIGN(4); __bss_end = .;
  } > data
  __stack_top = ORIGIN(data) + LENGTH(data);
  /DISCARD/ : { *(.comment) *(.riscv.attributes) }
}
