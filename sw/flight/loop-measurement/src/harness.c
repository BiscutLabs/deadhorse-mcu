/* Test harness: drives control_step for 3 modes over the scenario.
 * Target build: MMIO markers read by tools/rvsim.  Host build (-DHOST): prints. */
#include "control.h"
#include "scenario.h"

#ifdef HOST
#include <stdio.h>
#include <stdlib.h>
static void sim_mode(uint32_t m) { (void)m; }
static void sim_check(uint32_t m, uint32_t v) { printf("CHK %u %08x\n", m, v); }
static void sim_exit(int c) { exit(c); }
#else
#define MMIO(off) (*(volatile uint32_t *)(0x10000000u + (off)))
static void sim_mode(uint32_t m) { MMIO(0) = m; }
static void sim_check(uint32_t m, uint32_t v) { MMIO(4) = m; MMIO(4) = v; }
/* Named boundaries: the exit store retires; the terminal spin does not count.
 * Keep them adjacent with no call/jump counted by QEMU only. QEMU's finisher
 * may exit before tracing the spin, so the store has its own symbol as well. */
__attribute__((noinline, noclone, noreturn)) void sim_exit(int c)
{
#ifdef PLAT_QEMU
    uint32_t address = 0x100000u;
    uint32_t value = c ? ((uint32_t)c << 16 | 0x3333u) : 0x5555u;
#else
    uint32_t address = 0x10000008u;
    uint32_t value = (uint32_t)c;
#endif
    __asm__ volatile (".global sim_finish\nsim_finish:\n"
                      "sw %0, 0(%1)\n"
                      ".global sim_spin\nsim_spin:\nj sim_spin"
                      : : "r"(value), "r"(address) : "memory");
    __builtin_unreachable();
}
#endif

#ifdef NITER_RUN
#define RUN_N NITER_RUN
#else
#define RUN_N SCEN_N
#endif

#ifdef NUM_FLOAT
#define QF2D(x) ((double)(x))
#else
#define QF2D(x) ((double)(x) / 1073741824.0)
#endif
static state_t st;
static inputs_t in;
static outputs_t out;

static uint32_t fnv(uint32_t h, uint32_t v)
{
    for (int i = 0; i < 4; i++) { h ^= (v >> (8 * i)) & 0xff; h *= 16777619u; }
    return h;
}
static uint32_t bits(num x) { union { num n; uint32_t u; } c; c.n = x; return c.u; }

int main(void)
{
    for (uint32_t m = 0; m < 3; m++) {
        uint32_t h = 2166136261u;
        ctrl_init(&st);
        sim_mode(m);
        for (int k = 0; k < RUN_N; k++) {
            const scen_t *sc = &scen[m][k];
            for (int i = 0; i < 3; i++) {
                in.gyro[i] = sc->gyro[i]; in.accel[i] = sc->accel[i];
                in.rate_ff[i] = FROM_Q16(sc->ff[i]);
            }
            for (int i = 0; i < 4; i++) in.att_cmd[i] = FROM_Q30(sc->att[i]);
            in.airspeed = FROM_Q16(sc->airspeed);
            in.thrust = FROM_Q16(sc->thrust);
            in.trans = FROM_Q16(sc->trans);

            control_step(&in, &st, &out);

            for (int i = 0; i < 3; i++) h = fnv(h, out.motor[i]);
            for (int i = 0; i < 6; i++) h = fnv(h, out.servo[i]);
            for (int i = 0; i < 4; i++) h = fnv(h, bits(st.q[i]));
#ifdef DUMP
            printf("O %u %d %d %d %d %d %d %d %d %d %d %d %d %d\n", m, k,
                   out.motor[0], out.motor[1], out.motor[2], out.servo[0], out.servo[1],
                   out.servo[2], out.servo[3], out.servo[4], out.servo[5],
                   (int)(QF2D(st.q[1]) * 1e6), (int)(QF2D(st.q[2]) * 1e6), (int)(QF2D(st.q[3]) * 1e6));
#endif
        }
        sim_check(m, h);
    }
    sim_exit(0);
    return 0;
}
