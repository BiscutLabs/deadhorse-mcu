/* rvsim: minimal RV32IMC instruction-set simulator with dynamic instruction
 * counting around one function (entry symbol -> its return).
 *
 *   rvsim [-e entry_addr_hex] [-s nm_file] [-o csv] [-m maxinstr] prog.elf
 *
 * - RV32I + M + C (no A/F/D/Zicsr beyond nop-ing fence). ecall/ebreak stop the run.
 * - Flat 4 MiB RAM at 0x80000000, zero-initialised, ELF PT_LOAD segments loaded.
 * - MMIO at 0x10000000: +0 write = current mode id, +4 write = check word stream
 *   (mode, value), +8 write = exit code.  0x00100000 write = exit (QEMU-virt
 *   test-finisher compatible: 0x5555 = pass).
 * - Counting window: starts when pc == entry (that instruction is counted), ends
 *   after the instruction that returns to the caller's ra.  Compressed
 *   instructions count as one instruction.
 * - Categories: mul (MUL/MULH/MULHSU/MULHU), div (DIV/DIVU/REM/REMU), load,
 *   store, branch/jump (conditional branches, JAL, JALR), other.
 * - Optional per-stage attribution: symbols named stage_* (and the entry
 *   function itself = "glue") own the PC range; any other function (libgcc
 *   helpers) is charged to the most recent stage_* / entry function.
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <elf.h>

#define MEM_BASE 0x80000000u
#define MEM_SIZE (4u << 20)
static uint8_t *mem;
static uint32_t x[32], pc;

enum { C_MUL, C_DIV, C_LOAD, C_STORE, C_BR, C_OTHER, NCAT };

typedef struct { uint64_t n, cat[NCAT], rvc, taken, misaligned; } cnt_t;

static uint32_t cur_mode;
static uint64_t total_retired, total_rvc;
static int exit_code = -1;
static uint32_t chk_phase, chk_mode;

static void die(const char *m, uint32_t a) { fprintf(stderr, "rvsim: %s (0x%08x) pc=0x%08x\n", m, a, pc); exit(2); }

static inline uint8_t *ptr(uint32_t a, int n)
{
    if (a < MEM_BASE || a - MEM_BASE > MEM_SIZE - (uint32_t)n) die("bad address", a);
    return mem + (a - MEM_BASE);
}
static uint64_t misaligned_ct;

static uint32_t mmio_write(uint32_t a, uint32_t v)
{
    if (a == 0x10000000u) cur_mode = v;
    else if (a == 0x10000004u) {
        if (!chk_phase) { chk_mode = v; chk_phase = 1; }
        else { printf("CHK %u %08x\n", chk_mode, v); chk_phase = 0; }
    } else if (a == 0x10000008u) exit_code = (int)v;
    else if (a == 0x00100000u) exit_code = (v == 0x5555) ? 0 : (int)(v >> 16) | 1;
    return 0;
}
static inline int is_mmio(uint32_t a) { return (a & 0xFFF00000u) == 0x10000000u || a == 0x00100000u; }

static inline uint32_t ld(uint32_t a, int n, int sign)
{
    if (is_mmio(a)) return 0;
    if (a & (n - 1)) misaligned_ct++;
    uint32_t v = 0;
    memcpy(&v, ptr(a, n), n);
    if (sign && n < 4) { int sh = 32 - 8 * n; v = (uint32_t)((int32_t)(v << sh) >> sh); }
    return v;
}
static inline void st(uint32_t a, uint32_t v, int n)
{
    if (is_mmio(a)) { mmio_write(a, v); return; }
    if (a & (n - 1)) misaligned_ct++;
    memcpy(ptr(a, n), &v, n);
}

/* ---- RVC expansion to 32-bit encodings ---- */
static uint32_t e_r(uint32_t op, uint32_t rd, uint32_t f3, uint32_t rs1, uint32_t rs2, uint32_t f7)
{ return op | rd << 7 | f3 << 12 | rs1 << 15 | rs2 << 20 | f7 << 25; }
static uint32_t e_i(uint32_t op, uint32_t rd, uint32_t f3, uint32_t rs1, int32_t imm)
{ return op | rd << 7 | f3 << 12 | rs1 << 15 | ((uint32_t)imm & 0xFFF) << 20; }
static uint32_t e_s(uint32_t op, uint32_t f3, uint32_t rs1, uint32_t rs2, int32_t imm)
{ return op | ((uint32_t)imm & 0x1F) << 7 | f3 << 12 | rs1 << 15 | rs2 << 20 | (((uint32_t)imm >> 5) & 0x7F) << 25; }
static uint32_t e_b(uint32_t f3, uint32_t rs1, uint32_t rs2, int32_t imm)
{
    uint32_t i = (uint32_t)imm;
    return 0x63 | ((i >> 11) & 1) << 7 | ((i >> 1) & 0xF) << 8 | f3 << 12 | rs1 << 15 | rs2 << 20
         | ((i >> 5) & 0x3F) << 25 | ((i >> 12) & 1) << 31;
}
static uint32_t e_j(uint32_t rd, int32_t imm)
{
    uint32_t i = (uint32_t)imm;
    return 0x6F | rd << 7 | ((i >> 12) & 0xFF) << 12 | ((i >> 11) & 1) << 20 | ((i >> 1) & 0x3FF) << 21 | ((i >> 20) & 1) << 31;
}
static int32_t sx(uint32_t v, int bits) { return (int32_t)(v << (32 - bits)) >> (32 - bits); }

static uint32_t expand(uint16_t h)
{
    uint32_t f3 = h >> 13, op = h & 3;
    uint32_t rd = (h >> 7) & 31, rs2 = (h >> 2) & 31;
    uint32_t rdp = ((h >> 2) & 7) + 8, rs1p = ((h >> 7) & 7) + 8;
    if (op == 0) {
        switch (f3) {
        case 0: { /* C.ADDI4SPN */
            uint32_t imm = ((h >> 7) & 0xF) << 6 | ((h >> 11) & 3) << 4 | ((h >> 5) & 1) << 3 | ((h >> 6) & 1) << 2;
            if (!imm) die("illegal c.addi4spn/zero insn", h);
            return e_i(0x13, rdp, 0, 2, imm); }
        case 2: { /* C.LW */
            uint32_t imm = ((h >> 10) & 7) << 3 | ((h >> 6) & 1) << 2 | ((h >> 5) & 1) << 6;
            return e_i(0x03, rdp, 2, rs1p, imm); }
        case 6: { /* C.SW */
            uint32_t imm = ((h >> 10) & 7) << 3 | ((h >> 6) & 1) << 2 | ((h >> 5) & 1) << 6;
            return e_s(0x23, 2, rs1p, rdp, imm); }
        }
    } else if (op == 1) {
        int32_t imm6 = sx(((h >> 12) & 1) << 5 | ((h >> 2) & 31), 6);
        switch (f3) {
        case 0: return e_i(0x13, rd, 0, rd, imm6);                       /* C.ADDI / C.NOP */
        case 1: case 5: {                                                /* C.JAL / C.J */
            uint32_t o = ((h >> 12) & 1) << 11 | ((h >> 11) & 1) << 4 | ((h >> 9) & 3) << 8 | ((h >> 8) & 1) << 10
                       | ((h >> 7) & 1) << 6 | ((h >> 6) & 1) << 7 | ((h >> 3) & 7) << 1 | ((h >> 2) & 1) << 5;
            return e_j(f3 == 1 ? 1 : 0, sx(o, 12)); }
        case 2: return e_i(0x13, rd, 0, 0, imm6);                        /* C.LI */
        case 3:
            if (rd == 2) {                                               /* C.ADDI16SP */
                uint32_t o = ((h >> 12) & 1) << 9 | ((h >> 6) & 1) << 4 | ((h >> 5) & 1) << 6 | ((h >> 3) & 3) << 7 | ((h >> 2) & 1) << 5;
                return e_i(0x13, 2, 0, 2, sx(o, 10));
            } else {                                                     /* C.LUI */
                uint32_t v = (uint32_t)(imm6 << 12);
                return 0x37 | rd << 7 | (v & 0xFFFFF000u);
            }
        case 4: {
            uint32_t sub = (h >> 10) & 3;
            if (sub == 0) return e_i(0x13, rs1p, 5, rs1p, (h >> 2) & 31);               /* C.SRLI */
            if (sub == 1) return e_i(0x13, rs1p, 5, rs1p, ((h >> 2) & 31) | 0x400);     /* C.SRAI */
            if (sub == 2) return e_i(0x13, rs1p, 7, rs1p, imm6);                        /* C.ANDI */
            uint32_t s2 = (h >> 5) & 3;
            switch (s2) {
            case 0: return e_r(0x33, rs1p, 0, rs1p, rdp, 0x20);   /* C.SUB */
            case 1: return e_r(0x33, rs1p, 4, rs1p, rdp, 0);      /* C.XOR */
            case 2: return e_r(0x33, rs1p, 6, rs1p, rdp, 0);      /* C.OR  */
            default: return e_r(0x33, rs1p, 7, rs1p, rdp, 0);     /* C.AND */
            } }
        case 6: case 7: {                                                /* C.BEQZ / C.BNEZ */
            uint32_t o = ((h >> 12) & 1) << 8 | ((h >> 10) & 3) << 3 | ((h >> 5) & 3) << 6 | ((h >> 3) & 3) << 1 | ((h >> 2) & 1) << 5;
            return e_b(f3 == 6 ? 0 : 1, rs1p, 0, sx(o, 9)); }
        }
    } else if (op == 2) {
        switch (f3) {
        case 0: return e_i(0x13, rd, 1, rd, (h >> 2) & 31);              /* C.SLLI */
        case 2: {                                                        /* C.LWSP */
            uint32_t imm = ((h >> 12) & 1) << 5 | ((h >> 4) & 7) << 2 | ((h >> 2) & 3) << 6;
            return e_i(0x03, rd, 2, 2, imm); }
        case 4:
            if (!((h >> 12) & 1)) {
                if (rs2 == 0) return e_i(0x67, 0, 0, rd, 0);             /* C.JR */
                return e_r(0x33, rd, 0, 0, rs2, 0);                      /* C.MV */
            } else {
                if (rd == 0 && rs2 == 0) return 0x00100073;              /* C.EBREAK */
                if (rs2 == 0) return e_i(0x67, 1, 0, rd, 0);             /* C.JALR */
                return e_r(0x33, rd, 0, rd, rs2, 0);                     /* C.ADD */
            }
        case 6: {                                                        /* C.SWSP */
            uint32_t imm = ((h >> 9) & 0xF) << 2 | ((h >> 7) & 3) << 6;
            return e_s(0x23, 2, 2, rs2, imm); }
        }
    }
    die("unsupported compressed insn", h);
    return 0;
}

/* ---- stage attribution ---- */
typedef struct { uint32_t addr, size; char name[256]; } sym_t;
static sym_t *syms; static int nsyms;
static uint8_t *stage_tab;                 /* per halfword of the loaded image: stage id+1, 0 = none */
static char stage_names[64][64]; static int nstage;
static uint32_t img_lo = 0xFFFFFFFF, img_hi = 0;

static int stage_id(const char *nm)
{
    for (int i = 0; i < nstage; i++) if (!strcmp(stage_names[i], nm)) return i;
    if (nstage >= 64) die("too many stages", 0);
    strcpy(stage_names[nstage], nm);
    return nstage++;
}
static void load_syms(const char *file, uint32_t entry_name_addr_unused)
{
    (void)entry_name_addr_unused;
    FILE *f = fopen(file, "r"); if (!f) die("cannot open sym file", 0);
    char l[512]; int cap = 0;
    while (fgets(l, sizeof l, f)) {
        unsigned a, s; char t, n[256];
        if (sscanf(l, "%x %x %c %255s", &a, &s, &t, n) != 4) continue;
        if (t != 't' && t != 'T') continue;
        char *dot = strchr(n, '.'); if (dot) *dot = 0;       /* foo.constprop.0 -> foo */
        if (nsyms == cap) { cap = cap ? cap * 2 : 256; syms = realloc(syms, cap * sizeof *syms); }
        syms[nsyms].addr = a; syms[nsyms].size = s; snprintf(syms[nsyms].name, 256, "%s", n); nsyms++;
    }
    fclose(f);
    stage_tab = calloc((img_hi - img_lo) / 2 + 2, 1);
    stage_id("glue");                                         /* id 0 */
    for (int i = 0; i < nsyms; i++) {
        int id = -1;
        if (!strcmp(syms[i].name, "control_step")) id = 0;
        else if (!strncmp(syms[i].name, "stage_", 6)) id = stage_id(syms[i].name + 6);
        if (id < 0) continue;
        for (uint32_t a = syms[i].addr; a < syms[i].addr + syms[i].size; a += 2)
            if (a >= img_lo && a < img_hi) stage_tab[(a - img_lo) / 2] = id + 1;
    }
}

int main(int argc, char **argv)
{
    uint32_t entry = 0; const char *symfile = NULL, *csvfile = NULL, *elf = NULL;
    uint64_t maxinstr = 4000000000ull;
    for (int i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "-e")) entry = strtoul(argv[++i], 0, 16);
        else if (!strcmp(argv[i], "-s")) symfile = argv[++i];
        else if (!strcmp(argv[i], "-o")) csvfile = argv[++i];
        else if (!strcmp(argv[i], "-m")) maxinstr = strtoull(argv[++i], 0, 10);
        else elf = argv[i];
    }
    if (!elf) { fprintf(stderr, "usage: rvsim [-e entry] [-s nm] [-o csv] [-m max] prog.elf\n"); return 1; }
    mem = calloc(MEM_SIZE, 1);
    FILE *f = fopen(elf, "rb"); if (!f) die("cannot open elf", 0);
    Elf32_Ehdr eh; if (fread(&eh, sizeof eh, 1, f) != 1 || memcmp(eh.e_ident, ELFMAG, 4) || eh.e_machine != EM_RISCV) die("not a RISC-V ELF", 0);
    for (int i = 0; i < eh.e_phnum; i++) {
        Elf32_Phdr ph; fseek(f, eh.e_phoff + i * eh.e_phentsize, SEEK_SET);
        if (fread(&ph, sizeof ph, 1, f) != 1) die("short phdr", 0);
        if (ph.p_type != PT_LOAD) continue;
        fseek(f, ph.p_offset, SEEK_SET);
        if (fread(ptr(ph.p_paddr, ph.p_filesz ? ph.p_filesz : 1), 1, ph.p_filesz, f) != ph.p_filesz) die("short segment", 0);
        if ((ph.p_flags & PF_X)) { if (ph.p_paddr < img_lo) img_lo = ph.p_paddr; if (ph.p_paddr + ph.p_memsz > img_hi) img_hi = ph.p_paddr + ph.p_memsz; }
    }
    pc = eh.e_entry;
    if (symfile) load_syms(symfile, 0);

    FILE *csv = csvfile ? fopen(csvfile, "w") : NULL;
    if (csv) fprintf(csv, "mode,iter,total,mul,div,load,store,branch,other,rvc,taken,stack\n");

    static cnt_t stage_cnt[3][64]; static uint64_t iters_in_mode[3];
    static uint32_t iter_idx[3];
    int active = 0; uint32_t ret_addr = 0, sp_entry = 0, sp_min = 0; int cur_stage = 0;
    cnt_t c; memset(&c, 0, sizeof c);
    cnt_t sc_iter[64]; (void)sc_iter;

    for (;;) {
        if (!active && entry && pc == entry) {
            active = 1; ret_addr = x[1]; sp_entry = x[2]; sp_min = x[2];
            memset(&c, 0, sizeof c); cur_stage = 0;
        }
        uint32_t inst; int len; uint16_t h;
        { memcpy(&h, ptr(pc, 2), 2); }
        if ((h & 3) != 3) { inst = expand(h); len = 2; }
        else { uint16_t h2; memcpy(&h2, ptr(pc + 2, 2), 2); inst = h | (uint32_t)h2 << 16; len = 4; }

        uint32_t opc = inst & 0x7F, rd = (inst >> 7) & 31, f3 = (inst >> 12) & 7, rs1 = (inst >> 15) & 31, rs2 = (inst >> 20) & 31, f7 = inst >> 25;
        uint32_t a = x[rs1], b = x[rs2], npc = pc + len, res = 0; int wr = 0, cat = C_OTHER, taken = 0;
        int32_t immi = (int32_t)inst >> 20;
        switch (opc) {
        case 0x37: res = inst & 0xFFFFF000u; wr = 1; break;                          /* LUI */
        case 0x17: res = pc + (inst & 0xFFFFF000u); wr = 1; break;                   /* AUIPC */
        case 0x6F: {                                                                 /* JAL */
            uint32_t o = ((inst >> 31) & 1) << 20 | ((inst >> 12) & 0xFF) << 12 | ((inst >> 20) & 1) << 11 | ((inst >> 21) & 0x3FF) << 1;
            res = npc; wr = 1; npc = pc + sx(o, 21); cat = C_BR; taken = 1; break; }
        case 0x67: res = npc; wr = 1; npc = (a + immi) & ~1u; cat = C_BR; taken = 1; break;   /* JALR */
        case 0x63: {                                                                 /* BRANCH */
            uint32_t o = ((inst >> 31) & 1) << 12 | ((inst >> 7) & 1) << 11 | ((inst >> 25) & 0x3F) << 5 | ((inst >> 8) & 0xF) << 1;
            int t;
            switch (f3) {
            case 0: t = a == b; break; case 1: t = a != b; break;
            case 4: t = (int32_t)a < (int32_t)b; break; case 5: t = (int32_t)a >= (int32_t)b; break;
            case 6: t = a < b; break; case 7: t = a >= b; break;
            default: die("bad branch", inst); t = 0;
            }
            if (t) { npc = pc + sx(o, 13); taken = 1; }
            cat = C_BR; break; }
        case 0x03: {                                                                 /* LOAD */
            uint32_t ad = a + immi; cat = C_LOAD; wr = 1;
            switch (f3) {
            case 0: res = ld(ad, 1, 1); break; case 1: res = ld(ad, 2, 1); break; case 2: res = ld(ad, 4, 0); break;
            case 4: res = ld(ad, 1, 0); break; case 5: res = ld(ad, 2, 0); break;
            default: die("bad load", inst);
            } break; }
        case 0x23: {                                                                 /* STORE */
            int32_t o = sx(((inst >> 25) << 5) | ((inst >> 7) & 31), 12); cat = C_STORE;
            switch (f3) { case 0: st(a + o, b, 1); break; case 1: st(a + o, b, 2); break; case 2: st(a + o, b, 4); break; default: die("bad store", inst); }
            break; }
        case 0x13: {                                                                 /* OP-IMM */
            uint32_t sh = rs2; wr = 1;
            switch (f3) {
            case 0: res = a + immi; break; case 2: res = (int32_t)a < immi; break; case 3: res = a < (uint32_t)immi; break;
            case 4: res = a ^ immi; break; case 6: res = a | immi; break; case 7: res = a & immi; break;
            case 1: res = a << sh; break;
            case 5: res = (f7 & 0x20) ? (uint32_t)((int32_t)a >> sh) : a >> sh; break;
            } break; }
        case 0x33: {                                                                 /* OP */
            wr = 1;
            if (f7 == 1) {                                                           /* M extension */
                int32_t sa = a, sb = b;
                switch (f3) {
                case 0: res = a * b; cat = C_MUL; break;
                case 1: res = (uint32_t)(((int64_t)sa * (int64_t)sb) >> 32); cat = C_MUL; break;
                case 2: res = (uint32_t)(((int64_t)sa * (int64_t)(uint64_t)b) >> 32); cat = C_MUL; break;
                case 3: res = (uint32_t)(((uint64_t)a * (uint64_t)b) >> 32); cat = C_MUL; break;
                case 4: res = b == 0 ? 0xFFFFFFFFu : (sa == INT32_MIN && sb == -1) ? (uint32_t)sa : (uint32_t)(sa / sb); cat = C_DIV; break;
                case 5: res = b == 0 ? 0xFFFFFFFFu : a / b; cat = C_DIV; break;
                case 6: res = b == 0 ? a : (sa == INT32_MIN && sb == -1) ? 0 : (uint32_t)(sa % sb); cat = C_DIV; break;
                case 7: res = b == 0 ? a : a % b; cat = C_DIV; break;
                }
            } else {
                switch (f3) {
                case 0: res = (f7 & 0x20) ? a - b : a + b; break; case 1: res = a << (b & 31); break;
                case 2: res = (int32_t)a < (int32_t)b; break; case 3: res = a < b; break; case 4: res = a ^ b; break;
                case 5: res = (f7 & 0x20) ? (uint32_t)((int32_t)a >> (b & 31)) : a >> (b & 31); break;
                case 6: res = a | b; break; case 7: res = a & b; break;
                }
            } break; }
        case 0x0F: break;                                                            /* FENCE */
        case 0x73:                                                                   /* ECALL/EBREAK */
            exit_code = (int)x[10]; break;
        default: die("illegal instruction", inst);
        }
        if (wr && rd) x[rd] = res;
        total_retired++; if (len == 2) total_rvc++;
        if (active) {
            c.n++; c.cat[cat]++; if (len == 2) c.rvc++; if (taken) c.taken++;
            if (x[2] < sp_min) sp_min = x[2];
            if (stage_tab) {
                uint32_t pa = pc;
                if (pa >= img_lo && pa < img_hi) { uint8_t s = stage_tab[(pa - img_lo) / 2]; if (s) cur_stage = s - 1; }
                cnt_t *sc = &stage_cnt[cur_mode < 3 ? cur_mode : 0][cur_stage];
                sc->n++; sc->cat[cat]++; if (len == 2) sc->rvc++;
            }
        }
        pc = npc;
        if (active && pc == ret_addr) {
            active = 0;
            uint32_t m = cur_mode < 3 ? cur_mode : 0;
            if (csv) fprintf(csv, "%u,%u,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%llu,%u\n", m, iter_idx[m], (unsigned long long)c.n,
                (unsigned long long)c.cat[0], (unsigned long long)c.cat[1], (unsigned long long)c.cat[2], (unsigned long long)c.cat[3],
                (unsigned long long)c.cat[4], (unsigned long long)c.cat[5], (unsigned long long)c.rvc, (unsigned long long)c.taken, sp_entry - sp_min);
            iter_idx[m]++; iters_in_mode[m]++;
        }
        if (exit_code >= 0) break;
        if (total_retired >= maxinstr) { fprintf(stderr, "rvsim: instruction limit reached\n"); return 3; }
    }
    if (csv) fclose(csv);
    if (stage_tab) {
        for (int m = 0; m < 3; m++) for (int s = 0; s < nstage; s++) {
            cnt_t *sc = &stage_cnt[m][s]; if (!sc->n) continue;
            printf("STAGE %d %s %llu", m, stage_names[s], (unsigned long long)sc->n);
            for (int k = 0; k < NCAT; k++) printf(" %llu", (unsigned long long)sc->cat[k]);
            printf("\n");
        }
    }
    fprintf(stderr, "rvsim: exit=%d retired=%llu rvc=%llu misaligned=%llu\n", exit_code, (unsigned long long)total_retired,
            (unsigned long long)total_rvc, (unsigned long long)misaligned_ct);
    printf("TOTAL %llu %llu\n", (unsigned long long)total_retired, (unsigned long long)total_rvc);
    return exit_code;
}
