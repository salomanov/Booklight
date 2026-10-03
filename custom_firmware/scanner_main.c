// SPDX-License-Identifier: BSD-3-Clause
/**
 ******************************************************************************
 * @file    scanner_main.c
 * @brief   Hardware Scanner & Pin Hunter for DM02i V03 (Puya PY32C642 / PY32F002B)
 *          Autonomously probes Charlieplexing pairs, detects switch positions,
 *          samples ADC Bandgap, and exposes live SWD telemetry at 0x20000000.
 ******************************************************************************
 */

#include "py32f0xx.h"
#include "py32f002b_hal.h"
#include "py32f002b_hal_adc.h"
#include <stdint.h>
#include <stdbool.h>

#define SCANNER_MAGIC 0x5343414E // 'SCAN'

typedef struct {
    uint32_t magic;          // +0x00: 'SCAN'
    uint32_t mode;           // +0x04: 0 = Auto Charlie, 1 = Manual Pair, 2 = Single Pin High, 3 = All Off
    uint32_t step_idx;       // +0x08: Current pair step index
    uint32_t total_steps;    // +0x0C: Total steps (156)
    uint32_t high_pin_idx;   // +0x10: 0..12
    uint32_t low_pin_idx;    // +0x14: 0..12
    uint32_t delay_ms;       // +0x18: Delay per step (default 1000 ms)
    uint32_t is_paused;      // +0x1C: 1 = Paused, 0 = Running
    
    /* Live hardware telemetry */
    uint32_t idr_a;          // +0x20: GPIOA->IDR
    uint32_t idr_b;          // +0x24: GPIOB->IDR
    uint32_t vdd_mv;         // +0x28: VDD in mV (from VREFINT)
    uint32_t raw_adc;        // +0x2C: Raw ADC VREFINT
    
    /* Control commands from Python via SWD */
    uint32_t cmd_next;       // +0x30: Write 1 to advance step
    uint32_t cmd_prev;       // +0x34: Write 1 to go back
    uint32_t cmd_set_high;   // +0x38: Target high pin
    uint32_t cmd_set_low;    // +0x3C: Target low pin
    uint32_t heartbeat;      // +0x40: Increments every 10ms
} __attribute__((aligned(4))) ScannerShared_t;

/* Pinned strictly to start of SRAM 0x20000000 */
__attribute__((section(".shared_data")))
volatile ScannerShared_t g_scanner = {
    .magic       = SCANNER_MAGIC,
    .mode        = 0,
    .step_idx    = 0,
    .total_steps = 156,
    .high_pin_idx= 0,
    .low_pin_idx = 1,
    .delay_ms    = 1000,
    .is_paused   = 0,
    .idr_a       = 0,
    .idr_b       = 0,
    .vdd_mv      = 3300,
    .raw_adc     = 0,
    .cmd_next    = 0,
    .cmd_prev    = 0,
    .cmd_set_high= 0,
    .cmd_set_low = 1,
    .heartbeat   = 0
};

typedef struct {
    GPIO_TypeDef *port;
    uint16_t pin;
} PinDef_t;

/* Exactly the 6 GPIOs routed to the 6-pin display connector on DM02i V03 */
static const PinDef_t PINS[6] = {
    {GPIOA, GPIO_PIN_1}, // 0: PA1
    {GPIOA, GPIO_PIN_3}, // 1: PA3
    {GPIOA, GPIO_PIN_4}, // 2: PA4
    {GPIOA, GPIO_PIN_5}, // 3: PA5
    {GPIOA, GPIO_PIN_6}, // 4: PA6
    {GPIOA, GPIO_PIN_7}, // 5: PA7
};

#define NUM_PINS 6

static volatile uint32_t s_millis = 0;

void SysTick_Handler(void) {
    s_millis++;
}

void book_light_on_touch_irq(void) {
    // Dummy callback for EXTI
}

static uint32_t millis(void) {
    return s_millis;
}

static void delay_ms(uint32_t ms) {
    uint32_t start = millis();
    while ((millis() - start) < ms) {
        __NOP();
    }
}

static void all_pins_high_z(void) {
    GPIO_InitTypeDef GPIO_InitStruct = {0};
    GPIO_InitStruct.Mode = GPIO_MODE_ANALOG;
    GPIO_InitStruct.Pull = GPIO_NOPULL;

    for (int i = 0; i < NUM_PINS; i++) {
        GPIO_InitStruct.Pin = PINS[i].pin;
        HAL_GPIO_Init(PINS[i].port, &GPIO_InitStruct);
    }
}

static void set_pair(int high_idx, int low_idx) {
    all_pins_high_z();

    if (high_idx == low_idx || high_idx < 0 || high_idx >= NUM_PINS || low_idx < 0 || low_idx >= NUM_PINS) {
        return;
    }

    /* Voltage safety check */
    if (g_scanner.vdd_mv > 0 && g_scanner.vdd_mv < 2800) {
        return; // Low voltage protection
    }

    GPIO_InitTypeDef GPIO_InitStruct = {0};
    GPIO_InitStruct.Mode  = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull  = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW; // Low slew rate = no spikes

    /* Set Low pin first */
    HAL_GPIO_WritePin(PINS[low_idx].port, PINS[low_idx].pin, GPIO_PIN_RESET);
    GPIO_InitStruct.Pin = PINS[low_idx].pin;
    HAL_GPIO_Init(PINS[low_idx].port, &GPIO_InitStruct);

    /* Set High pin */
    HAL_GPIO_WritePin(PINS[high_idx].port, PINS[high_idx].pin, GPIO_PIN_SET);
    GPIO_InitStruct.Pin = PINS[high_idx].pin;
    HAL_GPIO_Init(PINS[high_idx].port, &GPIO_InitStruct);
}

static void set_single_high(int high_idx) {
    all_pins_high_z();
    if (high_idx < 0 || high_idx >= NUM_PINS) return;

    GPIO_InitTypeDef GPIO_InitStruct = {0};
    GPIO_InitStruct.Mode  = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull  = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;
    GPIO_InitStruct.Pin   = PINS[high_idx].pin;

    HAL_GPIO_WritePin(PINS[high_idx].port, PINS[high_idx].pin, GPIO_PIN_SET);
    HAL_GPIO_Init(PINS[high_idx].port, &GPIO_InitStruct);
}

/* Pair translation from step index (0 .. 155) */
static void get_pair_for_step(int step, int *high_idx, int *low_idx) {
    int cur = 0;
    for (int h = 0; h < NUM_PINS; h++) {
        for (int l = 0; l < NUM_PINS; l++) {
            if (h == l) continue;
            if (cur == step) {
                *high_idx = h;
                *low_idx  = l;
                return;
            }
            cur++;
        }
    }
    *high_idx = 0;
    *low_idx = 1;
}

/* ADC VREFINT setup */
static ADC_HandleTypeDef s_hadc;

static void adc_init(void) {
    __HAL_RCC_ADC_CLK_ENABLE();
    s_hadc.Instance = ADC1;
    s_hadc.Init.ClockPrescaler        = ADC_CLOCK_SYNC_PCLK_DIV32;
    s_hadc.Init.Resolution            = ADC_RESOLUTION_12B;
    s_hadc.Init.DataAlign             = ADC_DATAALIGN_RIGHT;
    s_hadc.Init.ScanConvMode          = ADC_SCAN_DIRECTION_FORWARD;
    s_hadc.Init.EOCSelection          = ADC_EOC_SINGLE_CONV;
    s_hadc.Init.LowPowerAutoWait      = DISABLE;
    s_hadc.Init.ContinuousConvMode    = DISABLE;
    s_hadc.Init.DiscontinuousConvMode = DISABLE;
    s_hadc.Init.ExternalTrigConv      = ADC_SOFTWARE_START;
    s_hadc.Init.ExternalTrigConvEdge  = ADC_EXTERNALTRIGCONVEDGE_NONE;
    s_hadc.Init.Overrun               = ADC_OVR_DATA_OVERWRITTEN;
    s_hadc.Init.SamplingTimeCommon    = ADC_SAMPLETIME_41CYCLES_5;
    HAL_ADC_Init(&s_hadc);

    ADC_ChannelConfTypeDef sConfig = {0};
    sConfig.Rank    = ADC_RANK_CHANNEL_NUMBER;
    sConfig.Channel = ADC_CHANNEL_VREFINT;
    HAL_ADC_ConfigChannel(&s_hadc, &sConfig);

    HAL_ADC_ConfigVrefBuf(&s_hadc, ADC_VREFBUF_VCCA);
    SET_BIT(ADC->CCR, ADC_CCR_VREFEN);
    HAL_ADCEx_Calibration_Start(&s_hadc);
}

static uint32_t adc_read_vref(void) {
    HAL_ADC_Start(&s_hadc);
    if (HAL_ADC_PollForConversion(&s_hadc, 10) == HAL_OK) {
        return HAL_ADC_GetValue(&s_hadc);
    }
    return 0;
}

int main(void) {
    /* 1. Explicitly initialize shared structure */
    g_scanner.magic       = SCANNER_MAGIC;
    g_scanner.mode        = 0;
    g_scanner.step_idx    = 0;
    g_scanner.total_steps = NUM_PINS * (NUM_PINS - 1); // 156
    g_scanner.high_pin_idx= 0;
    g_scanner.low_pin_idx = 1;
    g_scanner.delay_ms    = 1000;
    g_scanner.is_paused   = 0;
    g_scanner.cmd_next    = 0;
    g_scanner.cmd_prev    = 0;
    g_scanner.cmd_set_high= 0;
    g_scanner.cmd_set_low = 1;
    g_scanner.heartbeat   = 0;

    /* 2. Enable DBGMCU peripheral clock and keep SWD debug port active in STOP mode */
    RCC->APBENR1 |= RCC_APBENR1_DBGEN;
    DBGMCU->CR |= DBGMCU_CR_DBG_STOP;

    /* 2. Enable Clocks: GPIOA, GPIOB */
    RCC->IOPENR |= RCC_IOPENR_GPIOAEN | RCC_IOPENR_GPIOBEN;

    /* 3. SysTick 1 ms */
    SysTick_Config(SystemCoreClock / 1000U);

    /* Enable GPIO Port clocks */
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();

    /* Configure all Port B pins as safe Inputs with Pull-up (switches & sensors) */
    GPIO_InitTypeDef b_init = {0};
    b_init.Pin  = GPIO_PIN_0 | GPIO_PIN_1 | GPIO_PIN_2 | GPIO_PIN_3 | GPIO_PIN_4 | GPIO_PIN_5;
    b_init.Mode = GPIO_MODE_INPUT;
    b_init.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(GPIOB, &b_init);

    all_pins_high_z();
    adc_init();

    g_scanner.total_steps = NUM_PINS * (NUM_PINS - 1); // 30 steps
    int init_h = 0, init_l = 1;
    get_pair_for_step(0, &init_h, &init_l);
    g_scanner.high_pin_idx = init_h;
    g_scanner.low_pin_idx  = init_l;
    set_pair(init_h, init_l);

    uint32_t last_step_time = millis();
    uint32_t last_adc_time  = millis();

    while (1) {
        g_scanner.heartbeat++;

        /* 1. Live Input Monitoring (Sample IDR registers) */
        g_scanner.idr_a = GPIOA->IDR;
        g_scanner.idr_b = GPIOB->IDR;

        /* 2. Sample VDD every 200 ms */
        if (millis() - last_adc_time >= 200) {
            last_adc_time = millis();
            uint32_t raw = adc_read_vref();
            if (raw > 0) {
                g_scanner.raw_adc = raw;
                // VDD (mV) = (1200 * 4095) / raw
                g_scanner.vdd_mv = (uint32_t)(4914000ULL / raw);
            }
        }

        /* 3. Check SWD commands from Python */
        if (g_scanner.cmd_next) {
            g_scanner.cmd_next = 0;
            g_scanner.step_idx = (g_scanner.step_idx + 1) % g_scanner.total_steps;
            int h = 0, l = 1;
            get_pair_for_step(g_scanner.step_idx, &h, &l);
            g_scanner.high_pin_idx = h;
            g_scanner.low_pin_idx  = l;
            set_pair(h, l);
            last_step_time = millis();
        }
        if (g_scanner.cmd_prev) {
            g_scanner.cmd_prev = 0;
            if (g_scanner.step_idx == 0) {
                g_scanner.step_idx = g_scanner.total_steps - 1;
            } else {
                g_scanner.step_idx--;
            }
            int h = 0, l = 1;
            get_pair_for_step(g_scanner.step_idx, &h, &l);
            g_scanner.high_pin_idx = h;
            g_scanner.low_pin_idx  = l;
            set_pair(h, l);
            last_step_time = millis();
        }

        /* 4. Execution Modes: Full brightness continuous drive */
        if (g_scanner.mode == 0) {
            /* Mode 0: Auto Charlieplexing Walk */
            if (!g_scanner.is_paused && (millis() - last_step_time >= g_scanner.delay_ms)) {
                last_step_time = millis();
                int h = 0, l = 1;
                get_pair_for_step(g_scanner.step_idx, &h, &l);
                g_scanner.high_pin_idx = h;
                g_scanner.low_pin_idx  = l;

                set_pair(h, l);
                g_scanner.step_idx = (g_scanner.step_idx + 1) % g_scanner.total_steps;
            }
        } else if (g_scanner.mode == 1) {
            /* Mode 1: Manual Pair Hold */
            if (g_scanner.high_pin_idx != g_scanner.cmd_set_high || g_scanner.low_pin_idx != g_scanner.cmd_set_low) {
                g_scanner.high_pin_idx = g_scanner.cmd_set_high;
                g_scanner.low_pin_idx  = g_scanner.cmd_set_low;
                set_pair(g_scanner.high_pin_idx, g_scanner.low_pin_idx);
            }
        } else if (g_scanner.mode == 2) {
            /* Mode 2: Single Pin High */
            if (g_scanner.high_pin_idx != g_scanner.cmd_set_high) {
                g_scanner.high_pin_idx = g_scanner.cmd_set_high;
                set_single_high(g_scanner.high_pin_idx);
            }
        } else {
            /* Mode 3: All Off */
            all_pins_high_z();
        }

        delay_ms(10);
    }
}
