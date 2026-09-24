// SPDX-License-Identifier: BSD-3-Clause
/**
 ******************************************************************************
 * @file    main.c
 * @brief   E-Book Reading Lamp - STEP 1: Basic LED Test & SWD Keep-Alive
 *          MCU: PUYA PY32F002Bx5 (ARM Cortex-M0+ @ 24MHz)
 *          Board: CXV0257-V1.3
 * 
 *          Hardware pinout:
 *          - PA0 (Pin 13): MOSFET 1 Gate -> LED Filament (Active HIGH)
 *          - PA5 (Pin 18): MOSFET 2 Gate -> Second channel (Active HIGH)
 *          - SWD Debug: DBGMCU enabled, CoreSight debug active in RUN & STOP
 ******************************************************************************
 */

#include "py32f0xx.h"

int main(void)
{
    /* 1. Enable DBGMCU peripheral clock and keep SWD debug port active in STOP mode */
    RCC->APBENR1 |= RCC_APBENR1_DBGEN;
    DBGMCU->CR |= DBGMCU_CR_DBG_STOP;

    /* 2. Enable GPIOA and GPIOB clocks */
    RCC->IOPENR |= RCC_IOPENR_GPIOAEN | RCC_IOPENR_GPIOBEN;

    /* 3. Configure PA0 (Pin 13) as Output Push-Pull (Indicator LED) */
    GPIOA->MODER &= ~(GPIO_MODER_MODE0);
    GPIOA->MODER |= (GPIO_MODER_MODE0_0);
    GPIOA->OTYPER &= ~(1U << 0);
    GPIOA->OSPEEDR |= (3U << 0);
    GPIOA->PUPDR &= ~(GPIO_PUPDR_PUPD0);

    /* 4. Configure PB2 (Pin 10, Coil 2) and PB3 (Pin 9, Coil 1) as Output Push-Pull */
    GPIOB->MODER &= ~(GPIO_MODER_MODE2 | GPIO_MODER_MODE3);
    GPIOB->MODER |= (GPIO_MODER_MODE2_0 | GPIO_MODER_MODE3_0);
    GPIOB->OTYPER &= ~((1U << 2) | (1U << 3));
    GPIOB->OSPEEDR |= ((3U << (2 * 2)) | (3U << (3 * 2)));
    GPIOB->PUPDR &= ~(GPIO_PUPDR_PUPD2 | GPIO_PUPDR_PUPD3);

    /* 5. Initial state:
     * - PA0 = HIGH (Indicator LED on)
     * - PB2, PB3 = HIGH (P-FET closed if direct gate, safe idle)
     */
    GPIOA->BSRR = GPIO_BSRR_BS0;
    GPIOB->BSRR = GPIO_BSRR_BS2 | GPIO_BSRR_BS3;

    /* 6. Main loop - controller stays awake, SWD is 100% accessible 24/7 */
    while (1)
    {
        __NOP();
    }
}
