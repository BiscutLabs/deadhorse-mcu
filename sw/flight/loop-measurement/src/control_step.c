/* Inner flight-control loop: freestanding, no libc.  See REPORT.md. */
#include "control.h"

#ifdef PROFILE_STAGES
#define STAGE static __attribute__((noinline))   /* per-stage attribution build */
#else
#define STAGE static
#endif

/* ---------------------------------------------------------------- helpers */

static inline num biquad(const bq_coef_t *c, bq_state_t *z, num x)
{
    acc_t acc = P64(c->b0, x) + P64(c->b1, z->x1) + P64(c->b2, z->x2)
              - P64(c->a1, z->y1) - P64(c->a2, z->y2);
    num y = S30(acc);
    z->x2 = z->x1; z->x1 = x;
    z->y2 = z->y1; z->y1 = y;
    return y;
}

/* linear interpolation in a 17-entry table, x in [0,1] */
static inline num lut16(const num *t, num x)
{
    int i; num f;
    lut_split(x, &i, &f);
    if (i > 15) { i = 15; f = N(1.0); }
    return t[i] + MUL(t[i + 1] - t[i], f);
}

/* PID on rate: P on error, filtered D on measurement, clamped integrator
 * with conditional integration (anti-windup), feed-forward on setpoint.
 * Output is a normalised torque command in [-1, 1]. */
static inline num pid_axis(const pid_params_t *p, pid_state_t *s,
                           num sp, num meas)
{
    num err = sp - meas;
    num pterm = MUL(p->kp, err);

    num draw = MUL(p->kd_dt, s->prev - meas);       /* -Kd * d(meas)/dt */
    s->prev = meas;
    s->d_f += MUL(p->d_alpha, draw - s->d_f);

    /* integrate unless saturated in the direction of the error */
    if (!s->sat || (s->sat > 0) != (err > 0)) {
        s->i += MUL(p->ki_dt, err);
        s->i = CLAMP(s->i, -p->imax, p->imax);
    }

    num out = pterm + s->i + s->d_f + MUL(p->kff, sp);
    if (out > N(1.0))       { out = N(1.0);  s->sat = 1; }
    else if (out < -N(1.0)) { out = -N(1.0); s->sat = -1; }
    else                    { s->sat = 0; }
    return out;
}

/* ------------------------------------------------------------------ stages */

/* 1. raw int16 -> engineering units, bias subtraction */
STAGE void stage_imu_scale(const inputs_t *in, const state_t *s,
                           num g[3], num a[3])
{
    for (int i = 0; i < 3; i++) {
        g[i] = GYRO_FROM_RAW((int32_t)in->gyro[i] - s->p.gyro_bias[i], s->p.gyro_scale);
        a[i] = ACCEL_FROM_RAW((int32_t)in->accel[i] - s->p.accel_bias[i], s->p.accel_scale);
    }
}

/* 2. gyro: notch -> low-pass biquads; accel: first-order low-pass */
STAGE void stage_filters(state_t *s, num g[3], num a[3])
{
    for (int i = 0; i < 3; i++) {
        num y = biquad(&s->p.notch, &s->notch[i], g[i]);
        g[i]  = biquad(&s->p.lpf, &s->lpf[i], y);
        s->acc_f[i] += MUL(s->p.accel_alpha, a[i] - s->acc_f[i]);
        a[i] = s->acc_f[i];
    }
}

/* 3. Mahony quaternion complementary filter */
STAGE void stage_estimator(state_t *s, const num g[3], const num a[3])
{
    num gc[3] = { g[0], g[1], g[2] };
    qf q0 = s->q[0], q1 = s->q[1], q2 = s->q[2], q3 = s->q[3];

    num a2 = MUL(a[0], a[0]) + MUL(a[1], a[1]) + MUL(a[2], a[2]);
    if (a2 > N(0.25) && a2 < N(4.0)) {          /* accel plausible (0.5..2 g) */
        num inv = invsqrt_wide(a2);
        qf ax = NTOQ(MUL(a[0], inv));
        qf ay = NTOQ(MUL(a[1], inv));
        qf az = NTOQ(MUL(a[2], inv));
        /* estimated gravity direction in body frame */
        qf vx = DBL(S30(P64(q1, q3) - P64(q0, q2)));
        qf vy = DBL(S30(P64(q0, q1) + P64(q2, q3)));
        qf vz = S30(P64(q0, q0) - P64(q1, q1) - P64(q2, q2) + P64(q3, q3));
        /* error = measured x estimated */
        num ex = QTON(S30(P64(ay, vz) - P64(az, vy)));
        num ey = QTON(S30(P64(az, vx) - P64(ax, vz)));
        num ez = QTON(S30(P64(ax, vy) - P64(ay, vx)));
        /* integral feedback with clamp, then proportional */
        s->mah_i[0] = CLAMP(s->mah_i[0] + MUL(s->p.mah_ki_dt, ex), -s->p.mah_imax, s->p.mah_imax);
        s->mah_i[1] = CLAMP(s->mah_i[1] + MUL(s->p.mah_ki_dt, ey), -s->p.mah_imax, s->p.mah_imax);
        s->mah_i[2] = CLAMP(s->mah_i[2] + MUL(s->p.mah_ki_dt, ez), -s->p.mah_imax, s->p.mah_imax);
        gc[0] += MUL(s->p.mah_kp, ex) + s->mah_i[0];
        gc[1] += MUL(s->p.mah_kp, ey) + s->mah_i[1];
        gc[2] += MUL(s->p.mah_kp, ez) + s->mah_i[2];
    }

    /* integrate q' = 0.5 * q (x) (0, w), first order */
    qf hx = MULNQ(gc[0], s->p.half_dt);
    qf hy = MULNQ(gc[1], s->p.half_dt);
    qf hz = MULNQ(gc[2], s->p.half_dt);
    qf n0 = q0 + S30(-P64(q1, hx) - P64(q2, hy) - P64(q3, hz));
    qf n1 = q1 + S30( P64(q0, hx) + P64(q2, hz) - P64(q3, hy));
    qf n2 = q2 + S30( P64(q0, hy) - P64(q1, hz) + P64(q3, hx));
    qf n3 = q3 + S30( P64(q0, hz) + P64(q1, hy) - P64(q2, hx));

    /* renormalise: |q| ~ 1 so one Newton step from y0 = 1 is enough */
    qf nn = S30(P64(n0, n0) + P64(n1, n1) + P64(n2, n2) + P64(n3, n3));
    qf k = Q(1.5) - HALFQ(nn);
    s->q[0] = QMUL(n0, k);
    s->q[1] = QMUL(n1, k);
    s->q[2] = QMUL(n2, k);
    s->q[3] = QMUL(n3, k);
}

/* 4. attitude P loop: quaternion error -> body-rate setpoint */
STAGE void stage_attitude(const state_t *s, const inputs_t *in, num sp[3])
{
    qf a0 = s->q[0], a1 = s->q[1], a2 = s->q[2], a3 = s->q[3];
    qf b0 = in->att_cmd[0], b1 = in->att_cmd[1], b2 = in->att_cmd[2], b3 = in->att_cmd[3];
    /* qe = conj(q) (x) q_cmd */
    qf w  = S30(P64(a0, b0) + P64(a1, b1) + P64(a2, b2) + P64(a3, b3));
    qf e[3];
    e[0] = S30(P64(a0, b1) - P64(a1, b0) - P64(a2, b3) + P64(a3, b2));
    e[1] = S30(P64(a0, b2) - P64(a2, b0) - P64(a3, b1) + P64(a1, b3));
    e[2] = S30(P64(a0, b3) - P64(a3, b0) - P64(a1, b2) + P64(a2, b1));
    if (w < 0) { e[0] = -e[0]; e[1] = -e[1]; e[2] = -e[2]; }   /* shortest path */
    for (int i = 0; i < 3; i++) {
        num kp = s->p.att_kp_h[i] + MUL(s->p.att_kp_fw[i] - s->p.att_kp_h[i], in->trans);
        num r = in->rate_ff[i] + MUL(kp, QTON(e[i]));
        sp[i] = CLAMP(r, -s->p.rate_max[i], s->p.rate_max[i]);
    }
}

/* 5. hover rate PID, 3 axes */
STAGE void stage_rate_hover(state_t *s, const num sp[3], const num g[3], num tq[3])
{
    for (int i = 0; i < 3; i++)
        tq[i] = pid_axis(&s->p.hov[i], &s->hov[i], sp[i], g[i]);
}

/* 6. hover mixer: tilt-rotor tricopter -> 3 motors + 2 tilts.
 *   roll  : front-left/front-right differential thrust
 *   pitch : front pair vs rear motor (collective-preserving)
 *   yaw   : differential front tilt
 * Front thrust compensated by 1/cos(tilt). Desaturation keeps roll/pitch
 * authority: scale the differential if it does not fit, then shift collective. */
STAGE void stage_hover_mix(const state_t *s, const inputs_t *in, const num tq[3],
                           num tilt_base, num mot[3], num tilt[2])
{
    const params_t *p = &s->p;
    num yaw_d = MUL(tq[2], p->yaw_tilt_gain);
    tilt[0] = CLAMP(tilt_base + yaw_d, N(0.0), N(1.0));
    tilt[1] = CLAMP(tilt_base - yaw_d, N(0.0), N(1.0));

    num rr = MUL(tq[0], p->mix_roll);
    num pp = MUL(tq[1], p->mix_pitch);
    num tf = MUL(in->thrust, p->front_share);
    num tr = MUL(in->thrust, p->rear_share);
    num m0 = MUL(tf + rr + pp, lut16(p->sec_lut, tilt[0]));
    num m1 = MUL(tf - rr + pp, lut16(p->sec_lut, tilt[1]));
    num m2 = tr - DBL(pp);

    num hi = m0, lo = m0;
    if (m1 > hi) hi = m1; else if (m1 < lo) lo = m1;
    if (m2 > hi) hi = m2; else if (m2 < lo) lo = m2;

    num avail = p->thr_max - p->thr_min;
    num span = hi - lo;
    if (span > avail) {                         /* differential alone does not fit */
        num sc = RATIO_UNIT(avail, span);
        num mean = MUL(m0 + m1 + m2, N(1.0 / 3.0));
        m0 = mean + MUL(m0 - mean, sc);
        m1 = mean + MUL(m1 - mean, sc);
        m2 = mean + MUL(m2 - mean, sc);
        hi = mean + MUL(hi - mean, sc);
        lo = mean + MUL(lo - mean, sc);
    }
    num d = N(0.0);
    if (hi > p->thr_max)      d = p->thr_max - hi;   /* give up collective first */
    else if (lo < p->thr_min) d = p->thr_min - lo;
    mot[0] = m0 + d; mot[1] = m1 + d; mot[2] = m2 + d;
}

/* 7. fixed-wing controller: rate PID x3, airspeed gain scaling, surface mix */
STAGE void stage_fw(state_t *s, const inputs_t *in, const num sp[3],
                    const num g[3], num surf[4])
{
    static const uint8_t src[4] = { 0, 0, 1, 2 };   /* ail-L, ail-R <- roll; elev <- pitch; rud <- yaw */
    const params_t *p = &s->p;
    num v2 = MUL(in->airspeed, in->airspeed);
    num sc;
    if (v2 < p->fw_v2_min) sc = p->fw_scale_max;
    else sc = CLAMP(RATIO_BIG(p->fw_vref2, v2), p->fw_scale_min, p->fw_scale_max);

    num cmd[3];
    for (int i = 0; i < 3; i++) {
        num u = pid_axis(&p->fw[i], &s->fw[i], sp[i], g[i]);
        cmd[i] = CLAMP(MUL(u, sc), -N(1.0), N(1.0));
    }
    for (int k = 0; k < 4; k++) {
        num v = p->fw_trim[k] + MUL(p->fw_gain[k], cmd[src[k]]);
        surf[k] = CLAMP(v, -N(1.0), N(1.0));
    }
}

/* 8a. transition: tilt schedule vs transition variable */
STAGE num stage_tilt_sched(const state_t *s, num trans)
{
    return lut16(s->p.tilt_lut, CLAMP(trans, N(0.0), N(1.0)));
}

/* 8b. transition: blend hover and fixed-wing outputs */
STAGE void stage_blend(const state_t *s, const inputs_t *in, num tilt_base,
                       const num mot_h[3], const num tilt_h[2], const num surf_fw[4],
                       num mot[3], num tilt[2], num surf[4])
{
    num wf = in->trans, wh = N(1.0) - wf;
    num fwthr = MUL(in->thrust, s->p.fw_thrust_gain);
    num mf = MUL(wf, fwthr);
    mot[0] = MUL(wh, mot_h[0]) + mf;
    mot[1] = MUL(wh, mot_h[1]) + mf;
    mot[2] = MUL(wh, mot_h[2]);                 /* rear motor fades out */
    tilt[0] = tilt_base + MUL(wh, tilt_h[0] - tilt_base);   /* yaw-diff fades out */
    tilt[1] = tilt_base + MUL(wh, tilt_h[1] - tilt_base);
    for (int k = 0; k < 4; k++) surf[k] = MUL(wf, surf_fw[k]);
}

/* 9. output scaling: 3x DShot (48..2047), 6x servo pulse width in us */
STAGE void stage_output(const state_t *s, const num mot[3], const num tilt[2],
                        const num surf[4], outputs_t *out)
{
    const params_t *p = &s->p;
    for (int i = 0; i < 3; i++) {
        num x = CLAMP(mot[i], N(0.0), N(1.0));
        int32_t v = p->dshot_min + N2INT(MUL(x, p->dshot_span));
        out->motor[i] = (uint16_t)CLAMP(v, p->dshot_min, p->dshot_max);
    }
    num val[6] = { tilt[0], tilt[1], surf[0], surf[1], surf[2], surf[3] };
    for (int i = 0; i < 6; i++) {
        int32_t us = p->servo_off[i] + N2INT(MUL(val[i], p->servo_gain[i]));
        out->servo[i] = (uint16_t)CLAMP(us, (int32_t)p->servo_lo[i], (int32_t)p->servo_hi[i]);
    }
}

/* ------------------------------------------------------------- top level */

void control_step(const inputs_t *in, state_t *s, outputs_t *out)
{
    num g[3], a[3], sp[3];
    num tq_h[3] = { N(0.0), N(0.0), N(0.0) };
    num mot_h[3] = { N(0.0), N(0.0), N(0.0) };
    num tilt_h[2] = { N(0.0), N(0.0) };
    num surf_fw[4] = { N(0.0), N(0.0), N(0.0), N(0.0) };
    num mot[3], tilt[2], surf[4];

    stage_imu_scale(in, s, g, a);
    stage_filters(s, g, a);
    stage_estimator(s, g, a);
    stage_attitude(s, in, sp);

    num tilt_base = stage_tilt_sched(s, in->trans);
    if (in->trans < N(1.0)) {                   /* hover controller active */
        stage_rate_hover(s, sp, g, tq_h);
        stage_hover_mix(s, in, tq_h, tilt_base, mot_h, tilt_h);
    }
    if (in->trans > N(0.0))                     /* fixed-wing controller active */
        stage_fw(s, in, sp, g, surf_fw);

    stage_blend(s, in, tilt_base, mot_h, tilt_h, surf_fw, mot, tilt, surf);
    stage_output(s, mot, tilt, surf, out);
}
