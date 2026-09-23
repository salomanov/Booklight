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

    /* 2. Enable GPIOA clock */
    RCC->IOPENR |= RCC_IOPENR_GPIOAEN;

    /* 3. Configure PA0 (Pin 13) and PA5 (Pin 18) as Output Push-Pull */
    /* PA0: MODER[1:0] = 01 (General purpose output) */
    GPIOA->MODER &= ~(GPIO_MODER_MODE0);
    GPIOA->MODER |= (GPIO_MODER_MODE0_0);
    GPIOA->OTYPER &= ~(1U << 0);
    GPIOA->OSPEEDR |= (3U << 0);
    GPIOA->PUPDR &= ~(GPIO_PUPDR_PUPD0);

    /* PA5: MODER[11:10] = 01 (General purpose output) */
    GPIOA->MODER &= ~(GPIO_MODER_MODE5);
    GPIOA->MODER |= (GPIO_MODER_MODE5_0);
    GPIOA->OTYPER &= ~(1U << 5);
    GPIOA->OSPEEDR |= (3U << (5 * 2));
    GPIOA->PUPDR &= ~(GPIO_PUPDR_PUPD5);

    /* 4. Turn PA0 and PA5 HIGH (LED filament turns ON permanently) */
    GPIOA->BSRR = GPIO_BSRR_BS0 | GPIO_BSRR_BS5;

    /* 5. Main loop - controller stays awake, SWD is 100% accessible 24/7 */
    while (1)
    {
        __NOP();
    }
}
