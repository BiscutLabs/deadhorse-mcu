/* SPDX-License-Identifier: Apache-2.0 */
#ifndef DH_BOOT_H
#define DH_BOOT_H
#include <stdint.h>
#include <stddef.h>
#define DH_DIRECTORY_MAGIC UINT32_C(0x32425352)
#define DH_IMAGE_MAGIC UINT32_C(0x33424844)
#define DH_COMMIT UINT32_C(0x54494d43)
#define DH_CONTEXT_MAGIC UINT32_C(0x58544344)
#define DH_PERF_BASE UINT32_C(0x20000000)
#define DH_PERF_BYTES UINT32_C(14336)
#define DH_LITE_BASE UINT32_C(0x30000000)
#define DH_LITE_BYTES UINT32_C(1024)
#define DH_CONFIG_BASE UINT32_C(0x20003800)
#define DH_CONTEXT_BASE UINT32_C(0x20003900)
#define DH_STAGING_BASE UINT32_C(0x20003980)
#define DH_STAGING_BYTES UINT32_C(256)
#define DH_FLASH_MAX UINT32_C(0x1000000)
#define DH_CYCLES_PER_SECOND UINT32_C(8000000)
enum { H_MAGIC,H_VERSION,H_GENERATION,H_FLAGS,H_PERF_BYTES,H_PERF_ENTRY,
 H_PERF_CRC,H_LITE_BYTES,H_LITE_ENTRY,H_LITE_CRC,H_CONFIG_BYTES,H_CONFIG_CRC,
 H_PERF_ALLOCATION,H_LITE_DATA,H_LITE_STACK,H_PERF_ISA,H_LITE_ISA,H_HARDWARE,
 H_EXTENT,H_RESERVED0,H_RESERVED1,H_RESERVED2,H_CRC,H_COMMIT,H_WORDS };
typedef struct { uint32_t w[H_WORDS]; } dh_header;
/* Cold selection and recovery scanning never run concurrently. */
extern dh_header dh_selected;
typedef struct { uint32_t stride,capacity; } dh_directory;
typedef struct { uint32_t magic,version,stride,capacity,slot;
 dh_header header;uint32_t crc,reserved[2]; } dh_context;
_Static_assert(sizeof(dh_header)==96,"header ABI");
_Static_assert(sizeof(dh_context)==128,"context ABI");
uint32_t dh_crc_byte(uint32_t crc,uint8_t byte);
uint32_t dh_crc(const void *bytes,uint32_t count);
int dh_directory_decode(const uint32_t words[8],dh_directory *out);
int dh_header_valid(const dh_header *h,const dh_directory *d,int golden,int committed,uint32_t misa);
uint32_t dh_slot(const dh_directory *d,unsigned slot);
int dh_flash_read(uint32_t address,uint32_t *word);
int dh_flash_program(uint32_t address,uint32_t word);
int dh_flash_erase(uint32_t address);
int dh_flash_ready(void);
int dh_flash_initialize(void);
int dh_read_header(uint32_t slot,dh_header *h);
int dh_payload_valid(uint32_t slot,const dh_header *h);
/* -1 transport failure, 0 corrupt bytes, 1 validated bytes. */
int dh_payload_status(uint32_t slot,const dh_header *h);
int dh_choose(const dh_directory *d,dh_header *best,uint32_t *slot,uint32_t misa);
void dh_recovery_poll(void);
void dh_fail(void) __attribute__((noreturn));
#endif
