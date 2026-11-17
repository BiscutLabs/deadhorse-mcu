/* S3 representative memory fixture, NOT production flight firmware. */
#include <stdint.h>
#include <stddef.h>
#include "bmi270.h"
#include "control.h"

void hex(uint32_t); void line(void); void finish(unsigned);
extern const uint8_t bmi270_config_file[];
#define NOINLINE __attribute__((noinline))

/* SPI sensor model state is counted separately and conservatively in the
 * analytical total, even though real firmware would use an external sensor. */
struct sensor_model {
    uint8_t regs[128];
    uint32_t uploaded, chunks, config_hash, delays_us, errors, disabled_at;
} sensor;
struct bmi2_dev imu;
state_t controller;
inputs_t input;
outputs_t output;
struct dma_config { uint32_t address, length, owner, complete; } dma[4];
uint8_t spi_buffer[64], gps_buffer[128], rc_buffer[64], log_buffers[8][256], log_staging[256];
struct publication { uint16_t bank[2][9]; volatile uint32_t active, generation; } actuators;
struct navigation { float velocity[3], position[3]; uint32_t acquisition_us, ticks; } nav;
volatile uint32_t trap_count;

static void reset_sensor(void) {
    for (unsigned i = 0; i < 128; ++i) sensor.regs[i] = 0;
    sensor.regs[0] = 0x24;
    sensor.regs[0x7c] = 1;
    sensor.uploaded = sensor.chunks = sensor.errors = 0;
    sensor.config_hash = 2166136261u;
}

NOINLINE int8_t sensor_read(uint8_t address, uint8_t *bytes, uint32_t length, void *context) {
    if (context != &sensor || !(address & 0x80) || length < 2 || length > 129) return -1;
    address &= 0x7f;
    if (address == BMI2_STATUS_ADDR && length == 25 && (sensor.regs[0x7d] & 6) != 6) return -1;
    bytes[0] = 0; /* Actual SPI dummy byte consumed by the upstream driver. */
    for (unsigned i = 1; i < length; ++i) bytes[i] = sensor.regs[(address + i - 1) & 127];
#ifdef BAD_SAMPLE
    if (address == BMI2_STATUS_ADDR && length > 10) bytes[10] ^= 1; /* Delivered acc.x LSB. */
#endif
    return 0;
}

NOINLINE int8_t sensor_write(uint8_t address, const uint8_t *bytes, uint32_t length, void *context) {
    if (context != &sensor || (address & 0x80) || !length || length > 64) return -1;
    if (address == 0x7e && bytes[0] == 0xb6) { reset_sensor(); return 0; }
    if (address == 0x5e) {
        unsigned offset = 2u * ((sensor.regs[0x5b] & 15u) | ((unsigned)sensor.regs[0x5c] << 4));
        if (offset != sensor.uploaded || offset + length > 8192 || sensor.regs[0x59] != 0 ||
            (sensor.regs[0x7c] & 1) || sensor.delays_us - sensor.disabled_at < 450) return -1;
        ++sensor.chunks;
        for (unsigned i = 0; i < length; ++i) {
            uint8_t delivered = bytes[i];
#ifdef BAD_CONFIG
            if (offset + i == 1234) delivered ^= 1;
#endif
            if (delivered != bmi270_config_file[offset + i]) ++sensor.errors;
            sensor.config_hash = (sensor.config_hash ^ delivered) * 16777619u;
        }
        sensor.uploaded += length;
        return 0;
    }
    for (unsigned i = 0; i < length; ++i) sensor.regs[(address + i) & 127] = bytes[i];
    if (address == 0x7c && !(bytes[0] & 1)) sensor.disabled_at = sensor.delays_us;
    if (address == 0x59 && (bytes[0] & 1)) {
        sensor.regs[0x21] = sensor.uploaded == 8192 && !sensor.errors &&
                           sensor.config_hash == EXPECT_CONFIG_FNV ? 1 : 2;
    }
    return 0;
}
NOINLINE void sensor_delay(uint32_t us, void *context) {
    if (context == &sensor) sensor.delays_us += us;
}

static void put16(unsigned address, int value) {
    sensor.regs[address] = (uint8_t)value;
    sensor.regs[address + 1] = (uint8_t)((unsigned)value >> 8);
}
static NOINLINE void prepare_sample(unsigned frame) {
    const int values[6] = {100 + (int)frame, -200 - (int)frame, 2048,
                          12 + (int)frame, 12 - 2 * (int)frame, 12 + 3 * (int)frame};
    for (unsigned j = 0; j < 6; ++j) put16(0x0c + 2*j, values[j]);
    unsigned timestamp = 256 + frame * 32;
    sensor.regs[0x18] = timestamp;
    sensor.regs[0x19] = timestamp >> 8;
    sensor.regs[0x1a] = timestamp >> 16;
    sensor.regs[0x03] = 0xc0;
}
static uint32_t float_bits(float value) { union {float f; uint32_t u;} x = {.f=value}; return x.u; }
static NOINLINE uint32_t snapshot_hash(void) {
    uint32_t hash = 2166136261u, bank = actuators.active;
    for (unsigned i = 0; i < 9; ++i) hash = (hash ^ actuators.bank[bank][i]) * 16777619u;
    return hash;
}

/* Python independently checks every pre-commit snapshot against the previous
 * frame and the post-commit snapshot against all nine staged commands. */
static NOINLINE void publish(unsigned frame, const uint16_t commands[9]) {
    unsigned next = actuators.active ^ 1;
    hex(0x30); hex(frame);
    for (unsigned i = 0; i < 9; ++i) hex(commands[i]);
    line();
    for (unsigned i = 0; i < 9; ++i) {
        actuators.bank[next][i] = commands[i];
#ifdef BAD_PUBLISH
        if (i == 3) actuators.active = next; /* Deliberately expose a partial frame. */
#endif
        hex(0x31); hex(frame); hex(i); hex(snapshot_hash()); line();
    }
    __asm__ volatile("fence rw,rw" ::: "memory");
    actuators.active = next;
    ++actuators.generation;
    hex(0x32); hex(frame); hex(actuators.generation); hex(snapshot_hash()); line();
}

NOINLINE void trap_handler(uint32_t cause) {
    if (cause != 11) finish(9);
    ++trap_count;
    ++nav.ticks;
    nav.acquisition_us += 1000; /* Timer event fixture, not wall-clock QEMU time. */
}

NOINLINE void flight_iteration(unsigned frame) {
    struct bmi2_sens_data sample;
    uint16_t commands[9];
    prepare_sample(frame);
    __asm__ volatile("ecall" ::: "memory");
    dma[0] = (struct dma_config){(uint32_t)(uintptr_t)spi_buffer, 24, 1, 0};
    if (bmi2_get_sensor_data(&sample, &imu) != BMI2_OK) finish(3);
    dma[0].complete = 1;
    input.accel[0] = sample.acc.x; input.accel[1] = sample.acc.y; input.accel[2] = sample.acc.z;
    input.gyro[0] = sample.gyr.x; input.gyro[1] = sample.gyr.y; input.gyro[2] = sample.gyr.z;
    for (unsigned axis = 0; axis < 3; ++axis) {
        nav.velocity[axis] += (float)input.accel[axis] * (1.0f / 1024.0f);
        nav.position[axis] += nav.velocity[axis] * (1.0f / 1024.0f);
    }
    /* Groundspeed proxy for the historical field; no airspeed sensor is added. */
    input.airspeed = 18.0f; input.thrust = 0.5f; input.trans = 0.0f; input.att_cmd[0] = 1.0f;
    control_step(&input, &controller, &output);
    for (unsigned i = 0; i < 3; ++i) commands[i] = output.motor[i];
    for (unsigned i = 0; i < 4; ++i) commands[i + 3] = output.servo[i];
    /* Representative V-tail sum/difference, not an airframe qualification. */
    int elevator = (int)output.servo[4] - 1500, rudder = (int)output.servo[5] - 1500;
    commands[7] = CLAMP(1500 + elevator + rudder, 900, 2100);
    commands[8] = CLAMP(1500 + elevator - rudder, 900, 2100);
    hex(0x20); hex(frame); hex(nav.acquisition_us); hex(sample.sens_time);
    for (unsigned i = 0; i < 3; ++i) hex((uint32_t)(int32_t)input.accel[i]);
    for (unsigned i = 0; i < 3; ++i) hex((uint32_t)(int32_t)input.gyro[i]);
    for (unsigned i = 0; i < 3; ++i) hex(float_bits(nav.position[i]));
    hex(trap_count); line();
    publish(frame, commands);
    /* Exercise assumed storage capacities; volatile sinks prevent dead data. */
    gps_buffer[frame] = (uint8_t)sample.sens_time;
    rc_buffer[frame] = (uint8_t)commands[0];
    log_buffers[frame & 7][frame] = (uint8_t)commands[8];
    log_staging[frame] = (uint8_t)commands[7];
    dma[1] = (struct dma_config){(uint32_t)(uintptr_t)gps_buffer, sizeof gps_buffer, 1, 1};
    dma[2] = (struct dma_config){(uint32_t)(uintptr_t)rc_buffer, sizeof rc_buffer, 1, 1};
    dma[3] = (struct dma_config){(uint32_t)(uintptr_t)log_buffers, 256, 1, 1};
}

NOINLINE void run_hot_loop(void) {
    for (unsigned frame = 0; frame < 16; ++frame) flight_iteration(frame);
}

int main(void) {
    reset_sensor();
    imu.intf = BMI2_SPI_INTF; imu.intf_ptr = &sensor;
    imu.read = sensor_read; imu.write = sensor_write; imu.delay_us = sensor_delay;
    imu.read_write_len = 64;
    int result = bmi270_init(&imu);
    hex(0x10); hex((uint32_t)result); hex(sensor.uploaded); hex(sensor.chunks);
    hex(sensor.config_hash); hex(sensor.errors); hex(sensor.regs[0x21]); line();
    if (result != BMI2_OK || sensor.errors || sensor.regs[0x21] != 1) finish(2);
    const uint8_t enabled[] = {BMI2_ACCEL, BMI2_GYRO};
    if (bmi2_sensor_enable(enabled, 2, &imu) != BMI2_OK || (sensor.regs[0x7d] & 6) != 6) finish(4);
    ctrl_init(&controller);
    run_hot_loop();
    unsigned checksum = 0;
    for (unsigned i = 0; i < sizeof gps_buffer; ++i) checksum += gps_buffer[i];
    for (unsigned i = 0; i < sizeof rc_buffer; ++i) checksum += rc_buffer[i];
    for (unsigned i = 0; i < sizeof log_buffers; ++i) checksum += ((uint8_t *)log_buffers)[i];
    for (unsigned i = 0; i < sizeof log_staging; ++i) checksum += log_staging[i];
    hex(0x40); hex(checksum); hex(dma[0].length); hex(dma[0].complete); hex(trap_count); line();
    return 0;
}
