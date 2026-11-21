#include <stdint.h>
#include "soc.h"
#include "uart_regs.h"

static volatile uint32_t *const uart = (volatile uint32_t *)DH_SOC_UART0_BASE;

static void putc_uart(char value) {
    while (!(uart[DH_UART_STATUS_OFFSET / 4] & DH_UART_STATUS_TX_READY_MASK)) {}
    uart[DH_UART_TX_DATA_OFFSET / 4] = (uint8_t)value;
}

int main(void) {
    uart[DH_UART_BAUD_OFFSET / 4] = 4096;
    uart[DH_UART_CONFIGURATION_OFFSET / 4] = DH_UART_CONFIGURATION_TX_ENABLE_MASK;
    uart[DH_UART_COMMAND_OFFSET / 4] = DH_UART_COMMAND_APPLY_MASK;

    volatile uint32_t *word = (volatile uint32_t *)DH_SOC_PERFORMANCE_SRAM_BASE;
    volatile uint8_t *bytes = (volatile uint8_t *)word;
    *word = UINT32_C(0x11223344);
    bytes[1] = 0xaa;
    volatile float left = 1.5f, right = 2.5f;
    union { float value; uint32_t bits; } result;
    result.value = left * right;
    if (*word != UINT32_C(0x1122aa44) || result.bits != UINT32_C(0x40700000)) {
        putc_uart('E'); putc_uart('R'); putc_uart('R'); putc_uart('\n');
    } else {
        putc_uart('I'); putc_uart('0'); putc_uart('\n');
    }
    while (uart[DH_UART_STATUS_OFFSET / 4] & DH_UART_STATUS_TX_BUSY_MASK) {}
    return 0;
}
