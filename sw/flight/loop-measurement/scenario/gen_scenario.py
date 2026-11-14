#!/usr/bin/env python3
"""Deterministic test scenario generator: 3 modes x NITER iterations at 1 kHz.
A simple kinematic 'truth' attitude follows moving commands with a first-order
lag; IMU samples are derived from it + bias + white noise + 150 Hz vibration.
Events: command steps (saturate PID/mixer), accel shocks (>2 g, estimator
correction gated), airspeed dips (low-airspeed gain clamp)."""
import math, random, sys
NITER = int(sys.argv[2]) if len(sys.argv) > 2 else 2000
DT = 0.001
D2R = math.pi/180

def qmul(a, b):
    return (a[0]*b[0]-a[1]*b[1]-a[2]*b[2]-a[3]*b[3],
            a[0]*b[1]+a[1]*b[0]+a[2]*b[3]-a[3]*b[2],
            a[0]*b[2]-a[1]*b[3]+a[2]*b[0]+a[3]*b[1],
            a[0]*b[3]+a[1]*b[2]-a[2]*b[1]+a[3]*b[0])
def qconj(a): return (a[0], -a[1], -a[2], -a[3])
def eul2q(r, p, y):
    cr, sr, cp, sp, cy, sy = math.cos(r/2), math.sin(r/2), math.cos(p/2), math.sin(p/2), math.cos(y/2), math.sin(y/2)
    return (cr*cp*cy+sr*sp*sy, sr*cp*cy-cr*sp*sy, cr*sp*cy+sr*cp*sy, cr*cp*sy-sr*sp*cy)
def gravity_body(q):  # same convention as the estimator (reads +1 on z when level)
    q0, q1, q2, q3 = q
    return (2*(q1*q3-q0*q2), 2*(q0*q1+q2*q3), q0*q0-q1*q1-q2*q2+q3*q3)
def clip16(v): return max(-32768, min(32767, int(round(v))))

TRUTH = []
def gen_mode(mode, seed):
    rnd = random.Random(seed)
    roll_a, pitch_a = {0: (18, 15), 1: (35, 12), 2: (22, 12)}[mode]
    eul_t = [0.0, 0.0, 0.0]
    q_prev = eul2q(0, 0, 0)
    rows = []
    step_until, step_val = -1, (0, 0)
    shock_until = -1
    gbias = [12 + rnd.uniform(-3, 3) for _ in range(3)]
    for k in range(NITER):
        t = k*DT
        # --- commands
        cr = roll_a*math.sin(2*math.pi*0.7*t) + 4*math.sin(2*math.pi*2.3*t)
        cp = pitch_a*math.sin(2*math.pi*0.45*t + 1.0) + 3*math.sin(2*math.pi*1.9*t)
        cy = (20*t) if mode == 0 else 5*math.sin(2*math.pi*0.2*t)
        if k % 400 == 250:
            step_until = k + (200 if (k // 400) % 3 == 2 else 60)   # every 3rd step is long (integrator windup)
            step_val = (rnd.choice((-1, 1))*70, rnd.choice((-1, 1))*45)
        stepping = k < step_until
        if stepping: cr, cp = cr + step_val[0], cp + step_val[1]
        cmd_e = [cr*D2R, cp*D2R, cy*D2R]
        # --- truth follows command with lag (tau 0.12 s)
        a = DT/0.12
        for i in range(3): eul_t[i] += a*(cmd_e[i]-eul_t[i])
        q_true = eul2q(*eul_t)
        dq = qmul(qconj(q_prev), q_true)
        sgn = -1 if dq[0] < 0 else 1
        w_true = [2*sgn*dq[i+1]/DT for i in range(3)]
        q_prev = q_true
        # --- IMU
        if k % 333 == 100: shock_until = k + 3
        g = gravity_body(q_true)
        vib = math.sin(2*math.pi*150*t)
        bias_dist = 160 if 1100 <= k < 1500 else 0   # thermal bias excursion (Mahony integrator clamp)
        gyro = [clip16(w_true[i]/(D2R/16.4) + gbias[i] + bias_dist + rnd.gauss(0, 3) + 25*vib*(1, .7, .5)[i]) for i in range(3)]
        acc_scale = 1.0 + (2.5 if k < shock_until else 0.0)
        if k % 333 in (200, 201, 202): acc_scale = 0.2    # free-fall-like: accel rejected (low side)
        accel = [clip16((g[i]*acc_scale)*2048 + rnd.gauss(0, 12) + 60*vib*(.6, .8, 1)[i] + (rnd.gauss(0, 400) if k < shock_until else 0)) for i in range(3)]
        # --- other inputs
        if mode == 0:
            airspeed, trans = 1.5 + 0.5*math.sin(t), 0.0
            thrust = 0.50 + 0.06*math.sin(2*math.pi*0.3*t)
        elif mode == 1:
            airspeed = 19 + 4*math.sin(2*math.pi*0.25*t) + rnd.gauss(0, .2)
            if (k % 700) in range(450, 520): airspeed = 4.0   # stall-ish dip
            if (k % 700) in range(100, 160): airspeed = 31.0  # gust/dive: gain scaling hits lower clamp
            trans = 1.0
            thrust = 0.55 + 0.10*math.sin(2*math.pi*0.2*t)
        else:
            ph = (k % 1000)/1000.0
            trans = 0.15 + 0.7*(1-abs(2*ph-1))                # triangle 0.15..0.85
            airspeed = 3 + 15*trans + rnd.gauss(0, .2)
            thrust = 0.55 + 0.05*math.sin(2*math.pi*0.3*t)
        if stepping and (k - (step_until-60)) < 40: thrust = min(0.99, thrust + 0.45)  # forces mixer saturation
        qc = eul2q(*cmd_e)
        if 1500 <= k < 1560: qc = tuple(-c for c in qc)      # same attitude, opposite quaternion sign (w<0 path)
        ff = [0.3*(cmd_e[i]-eul_t[i])/0.12*0.2 for i in range(3)]   # small rate feed-forward
        TRUTH.append(q_true)
        rows.append((gyro, accel, int(round(airspeed*65536)), int(round(thrust*65536)),
                     int(round(trans*65536)), [int(round(c*(1 << 30))) for c in qc],
                     [int(round(f*65536)) for f in ff]))
    return rows

with open(sys.argv[1], "w") as f:
    f.write('#include "scenario.h"\n')
    f.write(f"const scen_t scen[3][SCEN_N] = {{\n")
    for mode in range(3):
        f.write("{\n")
        for (gy, ac, av, th, tr, qc, ff) in gen_mode(mode, 1234+mode):
            f.write("{{%d,%d,%d},{%d,%d,%d},%d,%d,%d,{%d,%d,%d,%d},{%d,%d,%d}},\n" % (*gy, *ac, av, th, tr, *qc, *ff))
        f.write("},\n")
    f.write("};\n")
with open(sys.argv[1].rsplit("/", 1)[0] + "/scenario.h", "w") as f:
    f.write(f"""#ifndef SCENARIO_H
#define SCENARIO_H
#include <stdint.h>
#define SCEN_N {NITER}
typedef struct {{ int16_t gyro[3], accel[3]; int32_t airspeed, thrust, trans, att[4], ff[3]; }} scen_t;
extern const scen_t scen[3][SCEN_N];
#endif
""")

with open(sys.argv[1].rsplit("/", 1)[0] + "/truth.txt", "w") as f:   # validation only, not compiled
    for q in TRUTH: f.write("%.9f %.9f %.9f %.9f\n" % q)
