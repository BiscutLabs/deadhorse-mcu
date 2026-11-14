/* Single-precision float backend: same code structure, soft-float on RV32IM. */
#ifndef NUM_FLOAT_H
#define NUM_FLOAT_H
#include <stdint.h>

typedef float num;
typedef float qf;
typedef float acc_t;
typedef float gscale_t;

#define N(x)  ((float)(x))
#define Q(x)  ((float)(x))
#define GSCALE(x) ((float)(x))
#define INT2N(i)  ((float)(i))
#define N2INT(x)  ((int32_t)((x) + 0.5f))

#define MUL(a, b)    ((a) * (b))
#define QMUL(a, b)   ((a) * (b))
#define MULNQ(n, q)  ((n) * (q))
#define P64(a, b)    ((a) * (b))
#define S30(acc)     (acc)
#define S16(acc)     (acc)

#define NTOQ(n)      (n)
#define QTON(q)      (q)
#define DBL(x)       ((x) + (x))
#define HALFQ(x)     ((x) * 0.5f)

#define GYRO_FROM_RAW(r, sc)  ((float)(int32_t)(r) * (sc))
#define ACCEL_FROM_RAW(r, sc) ((float)(int32_t)(r) * (sc))

#define FROM_Q16(i)  ((float)(i) * (1.0f / 65536.0f))
#define FROM_Q30(i)  ((float)(i) * (1.0f / 1073741824.0f))

#define RATIO_BIG(a, b)   ((a) / (b))
#define RATIO_UNIT(a, b)  ((a) / (b))

static inline void lut_split(num x, int *i, num *f)
{
    float t = x * 16.0f;
    int k = (int)t;
    *i = k;
    *f = t - (float)k;
}

/* classic bit-hack initial guess + two Newton steps */
static inline num invsqrt_wide(num x)
{
    union { float f; uint32_t u; } c;
    c.f = x;
    c.u = 0x5f3759dfu - (c.u >> 1);
    float y = c.f;
    y = y * (1.5f - 0.5f * x * y * y);
    y = y * (1.5f - 0.5f * x * y * y);
    return y;
}
#endif
