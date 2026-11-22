#include "adc_convert.h"
bool adc_probe(uint16_t code, uint32_t numerator, uint32_t denominator,
               int32_t offset, uint32_t *out) {
    bool valid = dh_adc_convert(code, numerator, denominator, offset, out);
#ifdef ADC_TEST_CORRUPT
    if (valid) *out ^= 1u;
#endif
    return valid;
}
