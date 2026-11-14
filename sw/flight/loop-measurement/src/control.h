/* Flightory Stallion VTOL inner loop (tilt-rotor tricopter + fixed wing).
 * One source, two numeric backends: fixed point (default) or -DNUM_FLOAT. */
#ifndef CONTROL_H
#define CONTROL_H
#include <stdint.h>
#ifdef NUM_FLOAT
#include "num_float.h"
#else
#include "num_fixed.h"
#endif

#define CLAMP(x, lo, hi) ((x) < (lo) ? (lo) : ((x) > (hi) ? (hi) : (x)))

#define LUT_N 17   /* 16 segments */

typedef struct { qf b0, b1, b2, a1, a2; } bq_coef_t;
typedef struct { num x1, x2, y1, y2; } bq_state_t;
typedef struct { num kp, ki_dt, kd_dt, kff, imax, d_alpha; } pid_params_t;
typedef struct { num i, d_f, prev; int32_t sat; } pid_state_t;

/* Tunable parameters (live in RAM, set at init, so the compiler cannot
 * constant-fold them). */
typedef struct {
    int16_t gyro_bias[3], accel_bias[3];
    gscale_t gyro_scale;
    num accel_scale, accel_alpha;
    bq_coef_t notch, lpf;
    num mah_kp, mah_ki_dt, mah_imax;
    qf  half_dt;
    num att_kp_h[3], att_kp_fw[3], rate_max[3];
    pid_params_t hov[3], fw[3];
    num fw_vref2, fw_v2_min, fw_scale_min, fw_scale_max;
    num fw_gain[4], fw_trim[4];
    num front_share, rear_share, mix_roll, mix_pitch, yaw_tilt_gain;
    num thr_min, thr_max, fw_thrust_gain;
    num sec_lut[LUT_N], tilt_lut[LUT_N];
    num dshot_span;
    int32_t dshot_min, dshot_max;
    num servo_gain[6];
    int16_t servo_off[6], servo_lo[6], servo_hi[6];
} params_t;

typedef struct {
    params_t p;
    bq_state_t notch[3], lpf[3];
    num acc_f[3];
    qf  q[4];
    num mah_i[3];
    pid_state_t hov[3], fw[3];
} state_t;

typedef struct {
    int16_t gyro[3], accel[3];  /* raw IMU counts, body axes */
    num airspeed;               /* m/s */
    num thrust;                 /* collective (hover) / throttle (FW), 0..1 */
    num trans;                  /* 0 = hover, 1 = fixed wing */
    qf  att_cmd[4];             /* commanded attitude w,x,y,z */
    num rate_ff[3];             /* rate feed-forward, rad/s */
} inputs_t;

/* motor[0..2]: front-left, front-right, rear  (DShot 48..2047)
 * servo[0..5]: tilt-L, tilt-R, aileron-L, aileron-R, elevator, rudder (us) */
typedef struct { uint16_t motor[3]; uint16_t servo[6]; } outputs_t;

void ctrl_init(state_t *s);
void control_step(const inputs_t *in, state_t *s, outputs_t *out);
#endif
