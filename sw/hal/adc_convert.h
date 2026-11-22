#ifndef DEADHORSE_ADC_CONVERT_H
#define DEADHORSE_ADC_CONVERT_H

#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>

/* Caller supplies board calibration. Match floor(code * n / d) + offset,
 * modulo 2^32. Invalid arguments leave *out unchanged. No MMIO access. */
static inline bool dh_adc_convert(uint16_t code, uint32_t numerator,
                                  uint32_t denominator, int32_t offset,
                                  uint32_t *out) {
    if (code > 4095u || denominator == 0u || out == NULL) return false;
    uint64_t quotient = (uint64_t)code * numerator / denominator;
    *out = (uint32_t)quotient + (uint32_t)offset;
    return true;
}

#endif
