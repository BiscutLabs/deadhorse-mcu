/* Parameter initialisation (not part of the measured loop).
 * Everything is a compile-time constant template copied into RAM at start,
 * so the control loop sees the parameters as ordinary run-time data. */
#include "control.h"

#define PID(kp, ki, kd, kff, imax, da) \
    { N(kp), N((ki) * 0.001), N((kd) / 0.001), N(kff), N(imax), N(da) }

static const state_t init_state = {
    .p = {
        .gyro_bias = { 12, 12, 12 },
        .accel_bias = { 0, 0, 0 },
        .gyro_scale = GSCALE(0.0010642),        /* 1/16.4 LSB per dps, in rad/s */
        .accel_scale = N(1.0 / 2048.0),         /* g per LSB (+-16 g) */
        .accel_alpha = N(0.1115),               /* ~20 Hz at 1 kHz */
#include "params_gen.inc"
        .mah_kp = N(2.0), .mah_ki_dt = N(0.3 * 0.001), .mah_imax = N(0.1),
        .half_dt = Q(0.5 * 0.001),
        .att_kp_h  = { N(6.0), N(6.0), N(3.0) },
        .att_kp_fw = { N(3.0), N(3.0), N(1.0) },
        .rate_max  = { N(6.0), N(6.0), N(2.0) },
        .hov = { PID(0.12, 0.25, 0.002, 0.04, 0.3, 0.2),
                 PID(0.12, 0.25, 0.002, 0.04, 0.3, 0.2),
                 PID(0.20, 0.25, 0.0,   0.04, 0.3, 0.2) },
        .fw  = { PID(0.08, 0.15, 0.001, 0.10, 0.4, 0.2),
                 PID(0.08, 0.15, 0.001, 0.10, 0.4, 0.2),
                 PID(0.08, 0.15, 0.001, 0.10, 0.4, 0.2) },
        .fw_vref2 = N(18.0 * 18.0), .fw_v2_min = N(36.0),
        .fw_scale_min = N(0.4), .fw_scale_max = N(2.5),
        .fw_gain = { N(1.0), N(-1.0), N(1.0), N(1.0) },
        .fw_trim = { N(0.02), N(-0.02), N(0.05), N(0.0) },
        .front_share = N(0.36), .rear_share = N(0.28),
        .mix_roll = N(0.25), .mix_pitch = N(0.25), .yaw_tilt_gain = N(0.15),
        .thr_min = N(0.06), .thr_max = N(1.0), .fw_thrust_gain = N(1.0),
        .dshot_span = N(1999.0), .dshot_min = 48, .dshot_max = 2047,
        /* tilt servos: 0..1 -> 1000..2000 us (R mirrored); surfaces 1500 +- 450 us */
        .servo_gain = { N(1000.0), N(-1000.0), N(450.0), N(450.0), N(450.0), N(450.0) },
        .servo_off  = { 1000, 2000, 1500, 1500, 1500, 1500 },
        .servo_lo   = { 900, 900, 900, 900, 900, 900 },
        .servo_hi   = { 2100, 2100, 2100, 2100, 2100, 2100 },
    },
    .q = { Q(1.0), Q(0.0), Q(0.0), Q(0.0) },
};

void ctrl_init(state_t *s)
{
    const char *src = (const char *)&init_state;
    char *dst = (char *)s;
    for (unsigned i = 0; i < sizeof *s; i++) dst[i] = src[i];
}
