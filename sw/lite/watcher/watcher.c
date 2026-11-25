/* SPDX-License-Identifier: Apache-2.0
 * PLAN05 reference radio watcher. Protocol/addresses: README.md.
 */
#include <stdint.h>
#include "crc16.h"
#define REG(a) (*(volatile uint32_t *)(a))
#define SPI 0x40020000u
#define GPIO 0x40020100u
#define MAIL 0x40001000u
volatile uint32_t accepted, rejected;

void watcher(void) {
  uint8_t packet[8];
  REG(GPIO + 32) = 15; /* AON owns shared pads; enable SPI alternates */
  REG(GPIO + 4) = 1u << 5; /* radio power on */
  REG(GPIO + 8) = 1u << 5;
  REG(GPIO + 16) = 1u << 4; /* radio IRQ edge capture */
  REG(SPI) = 1; /* enabled, mode 0 */
  REG(SPI + 16) = 1; /* half-period: one AON edge */
  REG(SPI + 20) = sizeof packet;
  /* WFI wakes on individually enabled MEIP even with global MIE clear.
   * Handle the sticky GPIO event synchronously, without nested traps. */
  __asm__ volatile("li t0, 2048; csrw mie, t0; csrci mstatus, 8" ::: "t0");
  for (;;) {
    while (!(REG(GPIO + 12) & (1u << 4))) __asm__ volatile("wfi");
    REG(GPIO + 20) = 1u << 4;
    for (unsigned i = 0; i < sizeof packet; ++i) REG(SPI + 8) = 0;
    REG(SPI + 24) = 1;
    while (REG(SPI + 4) & 1) { }
    for (unsigned i = 0; i < sizeof packet; ++i) packet[i] = REG(SPI + 12);
    /* Only this fixed address/command may be accepted. Fold its CRC at
     * compile time, but keep the explicit prefix checks below: for an
     * accepted prefix this is identical; every other prefix is rejected. */
    uint32_t crc = crc_byte(crc_byte(crc_byte(0xffff, 0x48), 0x44), 1);
    for (unsigned i = 3; i < 6; ++i) crc = crc_byte(crc, packet[i]);
    if (packet[0] == 0x48 && packet[1] == 0x44 && packet[2] == 1 &&
        crc == ((uint32_t)packet[6] << 8 | packet[7])) {
      /* No oscillator request here: only the peer mailbox wakes main. */
      while (!(REG(MAIL + 12) & 1)) { }
      REG(MAIL) =
#ifdef WATCHER_BAD_PAYLOAD
                  0x56000000u | /* verification-only fault */
#else
                  0x57000000u |
#endif
                  ((uint32_t)packet[3] << 16) |
                  ((uint32_t)packet[4] << 8) | packet[5];
      REG(MAIL + 4) = 1;
      ++accepted;
    } else {
      ++rejected;
    }
    REG(SPI + 28) = 1;
  }
}
