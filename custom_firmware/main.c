// SPDX-License-Identifier: BSD-3-Clause
/**
 ******************************************************************************
 * @file    main.c
 * @brief   E-Book Reading Lamp - STEP 2: Multi-Channel PWM Control (Hardware + Filaments)
 *          MCU: PUYA PY32F002Bx5 (ARM Cortex-M0+ @ 24MHz)
 *          Board: CXV0257-V1.3
 * 
 *          Hardware pinout:
 *          - PA0 (Pin 13): TIM1_CH1 (AF2) -> Indicator LED (1.0 kHz Hardware PWM)
 *          - PB3 (Pin 9):  Coil 1 MOSFET (Active LOW for P-FET) -> 500 Hz PWM
 *          - PB2 (Pin 10): Coil 2 MOSFET (Active LOW for P-FET) -> 500 Hz PWM
 *          - SWD Debug:    DBGMCU enabled, CoreSight debug active 24/7
 ******************************************************************************
 */

#include "py32f0xx.h"
#include <stdint.h>

/* Shared control block at known memory location for SWD control */
typedef struct {
    uint32_t magic;         // 0x50574D31 ('PWM1')
    uint32_t duty_pa0;      // 0..100% (Indicator LED via TIM1_CH1)
    uint32_t duty_pb3;      // 0..100% (Filament 1 via PB3 P-FET)
    uint32_t duty_pb2;      // 0..100% (Filament 2 via PB2 P-FET)
    uint32_t flags;         // Status flags
} LampSharedControl_t;

volatile LampSharedControl_t g_lamp = {
    .magic    = 0x50574D31,
    .duty_pa0 = 50,
    .duty_pb3 = 0,
    .duty_pb2 = 0,
    .flags    = 1
};

/* Fast PWM Counter for Filaments (runs inside SysTick @ 50 kHz -> 500 Hz PWM) */
static volatile uint8_t pwm_cnt = 0;

void SysTick_Handler(void)
{
    uint8_t cnt = pwm_cnt + 1;
    if (cnt >= 100) cnt = 0;
    pwm_cnt = cnt;

    uint32_t d_pb3 = g_lamp.duty_pb3;
    uint32_t d_pb2 = g_lamp.duty_pb2;

    /* Filament 1 (PB3): CJ3415 P-FET (0V / LOW = ON, 3.3V / HIGH = OFF) */
    if (d_pb3 == 0) {
        GPIOB->BSRR = (1U << 3);           // 3.3V (OFF)
    } else if (d_pb3 >= 100) {
        GPIOB->BSRR = (1U << (3 + 16));    // 0V (ON)
    } else {
        if (cnt < d_pb3) {
            GPIOB->BSRR = (1U << (3 + 16)); // 0V (ON)
        } else {
            GPIOB->BSRR = (1U << 3);        // 3.3V (OFF)
        }
    }

    /* Filament 2 (PB2): CJ3415 P-FET (0V / LOW = ON, 3.3V / HIGH = OFF) */
    if (d_pb2 == 0) {
        GPIOB->BSRR = (1U << 2);           // 3.3V (OFF)
    } else if (d_pb2 >= 100) {
        GPIOB->BSRR = (1U << (2 + 16));    // 0V (ON)
    } else {
        if (cnt < d_pb2) {
            GPIOB->BSRR = (1U << (2 + 16)); // 0V (ON)
        } else {
            GPIOB->BSRR = (1U << 2);        // 3.3V (OFF)
        }
    }
}

int main(void)
{
    /* 1. Enable DBGMCU peripheral clock and keep SWD debug port active in STOP mode */
    RCC->APBENR1 |= RCC_APBENR1_DBGEN;
    DBGMCU->CR |= DBGMCU_CR_DBG_STOP;

    /* 2. Enable Clocks: GPIOA, GPIOB, and TIM1 */
    RCC->IOPENR |= RCC_IOPENR_GPIOAEN | RCC_IOPENR_GPIOBEN;
    RCC->APBENR2 |= RCC_APBENR2_TIM1EN;

    /* 3. Configure PA0 (Pin 13) as Alternate Function 2 (TIM1_CH1) */
    GPIOA->MODER &= ~(GPIO_MODER_MODE0);
    GPIOA->MODER |= (2U << 0);           // Mode 10 = Alternate Function
    GPIOA->AFR[0] &= ~(0xFU << 0);
    GPIOA->AFR[0] |= (2U << 0);           // AF2 = TIM1_CH1
    GPIOA->OSPEEDR |= (3U << 0);          // High Speed
    GPIOA->PUPDR &= ~(GPIO_PUPDR_PUPD0);

    /* 4. Configure PB2 (Pin 10, Coil 2) and PB3 (Pin 9, Coil 1) as Output Push-Pull */
    GPIOB->MODER &= ~(GPIO_MODER_MODE2 | GPIO_MODER_MODE3);
    GPIOB->MODER |= (GPIO_MODER_MODE2_0 | GPIO_MODER_MODE3_0);
    GPIOB->OTYPER &= ~((1U << 2) | (1U << 3));
    GPIOB->OSPEEDR |= ((3U << (2 * 2)) | (3U << (3 * 2)));
    GPIOB->PUPDR &= ~(GPIO_PUPDR_PUPD2 | GPIO_PUPDR_PUPD3);

    /* Safe initial state for power MOSFETs: PB2 and PB3 = HIGH (P-FETs closed / off) */
    GPIOB->BSRR = GPIO_BSRR_BS2 | GPIO_BSRR_BS3;

    /* 5. Configure TIM1 for 1 kHz Hardware PWM on Channel 1 (PA0) */
    TIM1->PSC = 23;                       // 24 MHz / (23 + 1) = 1 MHz timer clock
    TIM1->ARR = 999;                      // 1 MHz / (999 + 1) = 1.0 kHz PWM frequency
    TIM1->CCR1 = 500;                     // Initial 50%
    TIM1->CCMR1 = (6U << 4) | TIM_CCMR1_OC1PE;
    TIM1->CCER = TIM_CCER_CC1E;
    TIM1->BDTR = TIM_BDTR_MOE;
    TIM1->CR1 = TIM_CR1_CEN;

    /* 6. Configure SysTick for 50 kHz timer interrupt (500 Hz across 100 PWM steps) */
    SysTick_Config(SystemCoreClock / 50000);

    /* 7. Main loop */
    while (1)
    {
        /* Synchronize TIM1_CH1 with g_lamp.duty_pa0 */
        uint32_t d_pa0 = g_lamp.duty_pa0;
        if (d_pa0 > 100) d_pa0 = 100;
        TIM1->CCR1 = d_pa0 * 10;

        __NOP();
    }
}
