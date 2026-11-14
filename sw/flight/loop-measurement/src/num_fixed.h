/* Fixed-point backend.
 *  num : Q16.16 (rad/s, g, normalised commands, ...)
 *  qf  : Q2.30  (quaternion components, unit vectors, filter coefficients)
 *  64-bit intermediates are used for every product (mul + mulh on RV32IM).
 */
#ifndef NUM_FIXED_H
#define NUM_FIXED_H
#include <stdint.h>

typedef int32_t num;
typedef int32_t qf;
typedef int64_t acc_t;
typedef int32_t gscale_t;      /* gyro scale: rad/s per LSB in Q24 */

#define N(x)  ((num)((x) * 65536.0 + ((x) >= 0 ? 0.5 : -0.5)))
#define Q(x)  ((qf)((x) * 1073741824.0 + ((x) >= 0 ? 0.5 : -0.5)))
#define GSCALE(x) ((gscale_t)((x) * 16777216.0 + 0.5))
#define INT2N(i)  ((num)(i) * 65536)
#define N2INT(x)  (((x) + 32768) >> 16)

/* single products */
#define MUL(a, b)    ((num)(((int64_t)(a) * (b)) >> 16))   /* num*num -> num */
#define QMUL(a, b)   ((qf)(((int64_t)(a) * (b)) >> 30))    /* qf*qf  -> qf  */
#define MULNQ(n, q)  ((qf)(((int64_t)(n) * (q)) >> 16))    /* num*qf -> qf  */
/* 64-bit accumulate: P64() products, then shift once */
#define P64(a, b)    ((int64_t)(a) * (b))
#define S30(acc)     ((int32_t)((acc) >> 30))
#define S16(acc)     ((int32_t)((acc) >> 16))

#define NTOQ(n)      ((qf)((n) * 16384))     /* Q16 -> Q30 (|n| < 2) */
#define QTON(q)      ((num)((q) >> 14))      /* Q30 -> Q16 */
#define DBL(x)       ((x) + (x))
#define HALFQ(x)     ((x) >> 1)

/* raw sensor scaling */
#define GYRO_FROM_RAW(r, sc)  ((num)(((int32_t)(r) * (sc)) >> 8))   /* Q24 -> Q16 */
#define ACCEL_FROM_RAW(r, sc) ((num)((int32_t)(r) * (sc)))           /* sc in Q16 g/LSB */

/* scenario inputs are stored as integers */
#define FROM_Q16(i)  ((num)(i))
#define FROM_Q30(i)  ((qf)(i))

/* Q16 ratios with 32-bit hardware divide.
 * RATIO_BIG : a up to ~900, b >= ~16 (airspeed-squared ratio)
 * RATIO_UNIT: 0 <= a <= 1.0, b > 0 (mixer scaling) */
#define RATIO_BIG(a, b)   ((num)((((uint32_t)(a)) << 5) / ((uint32_t)(b) >> 11)))
#define RATIO_UNIT(a, b)  ((num)(((((uint32_t)(a)) << 15) / (uint32_t)(b)) << 1))

/* split x in [0,1] Q16 into 16-segment table index + Q16 fraction */
static inline void lut_split(num x, int *i, num *f)
{
    *i = x >> 12;
    *f = (x & 0xFFF) << 4;
}

/* 1/sqrt(x), x in [0.25, 4], Q16 -> Q16.  Range-reduce to [0.5,2),
 * linear initial guess, two Newton-Raphson steps (~0.4% worst case). */
static inline num invsqrt_wide(num x)
{
    int sh = 0;
    if (x < N(0.5)) { x <<= 2; sh = 1; }
    else if (x >= N(2.0)) { x >>= 2; sh = -1; }
    num y = N(1.4142) - MUL(N(0.4714), x - N(0.5));
    num t;
    t = N(1.5) - (MUL(x, MUL(y, y)) >> 1);
    y = MUL(y, t);
    t = N(1.5) - (MUL(x, MUL(y, y)) >> 1);
    y = MUL(y, t);
    if (sh > 0) y <<= 1; else if (sh < 0) y >>= 1;
    return y;
}
#endif
