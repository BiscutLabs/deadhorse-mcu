/* SPDX-License-Identifier: Apache-2.0 */
#ifndef WATCHER_CRC16_H
#define WATCHER_CRC16_H
#include <stdint.h>

/* Eight MSB-first 0x1021 polynomial steps factored into shifts/XORs.
 * Keep intermediates word-sized on RV32E; truncate only the final remainder.
 * test_crc.c checks every 16-bit remainder and every input byte against an
 * independent bit-at-a-time implementation, not another table expansion.
 */
static inline __attribute__((always_inline)) uint32_t crc_byte(uint32_t crc, uint8_t byte) {
  uint32_t t = ((crc >> 8) ^ byte) & 255u;
  t ^= t >> 4;
  return ((crc << 8) ^ (t << 12) ^ (t << 5) ^ t) & 65535u;
}
#endif
