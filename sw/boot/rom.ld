ENTRY(_start)
MEMORY { ROM (rx) : ORIGIN = 0x80, LENGTH = 0xff80
         GLOBALS (rw) : ORIGIN = 0x20003a80, LENGTH = 0x380 }
SECTIONS {
 .text : { KEEP(*(.text.start)) *(.text*) *(.rodata*) } > ROM
 .data : { *(.data*) *(.sdata*) } > GLOBALS
 .bss (NOLOAD) : { . = ALIGN(4); __bss_start = .; *(.bss*) *(.sbss*) *(COMMON) . = ALIGN(4); __bss_end = .; } > GLOBALS
 /DISCARD/ : { *(.comment) *(.riscv.attributes) *(.eh_frame*) }
 ASSERT(SIZEOF(.data)==0,"ROM globals must be zero-initialized")
 ASSERT(__bss_end<=0x20003e00,"ROM globals overflow")
}
