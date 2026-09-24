// SPDX-License-Identifier: BSD-3-Clause
/**
 ******************************************************************************
 * @file    main.c
 * @brief   E-Book Reading Lamp - STEP 2: Hardware PWM (TIM1_CH1 + TIM1_CH3)
 *          MCU: PUYA PY32F002Bx5 (ARM Cortex-M0+ @ 24MHz)
 *          Board: CXV0257-V1.3
 * 
 *          Hardware pinout:
 *          - PA0 (Pin 13): TIM1_CH1 (AF2) -> Indicator LED (1.0 kHz Hardware PWM)
 *          - PB2 (Pin 10): TIM1_CH3 (AF3) -> Power MOSFET 2 (Coil Pad 2: All 4 Filaments)
 *                          P-Channel FET (Active LOW via CC3P, 1.0 kHz Hardware PWM, 0% CPU)
 *          - PB3 (Pin 9):  Power MOSFET 1 (Coil Pad 1) -> Safe Output HIGH (Closed)
 *          - SWD Debug:    DBGMCU enabled, CoreSight debug active 24/7
 ******************************************************************************
 */

#include "py32f0xx.h"
#include <stdint.h>

int main(void)
{
    /* 1. Enable DBGMCU peripheral clock and keep SWD debug port active in STOP mode */
    RCC->APBENR1 |= RCC_APBENR1_DBGEN;
    DBGMCU->CR |= DBGMCU_CR_DBG_STOP;

    /* 2. Enable Clocks: GPIOA, GPIOB, and TIM1 */
    RCC->IOPENR  |= RCC_IOPENR_GPIOAEN | RCC_IOPENR_GPIOBEN;
    RCC->APBENR2 |= RCC_APBENR2_TIM1EN;

    /* 3. Configure PA0 (Pin 13) as Alternate Function 2 (TIM1_CH1, Indicator LED) */
    GPIOA->MODER   &= ~(GPIO_MODER_MODE0);
    GPIOA->MODER   |= (2U << 0);           // Mode 10 = Alternate Function
    GPIOA->AFR[0]  &= ~(0xFU << 0);
    GPIOA->AFR[0]  |= (2U << 0);           // AF2 = TIM1_CH1
    GPIOA->OSPEEDR |= (3U << 0);          // High Speed
    GPIOA->PUPDR   &= ~(GPIO_PUPDR_PUPD0);

    /* 4. Configure PB2 (Pin 10, Coil Pad 2) as Alternate Function 3 (TIM1_CH3, 4 Filaments) */
    GPIOB->MODER   &= ~(GPIO_MODER_MODE2);
    GPIOB->MODER   |= (2U << 4);           // Mode 10 = Alternate Function
    GPIOB->AFR[0]  &= ~(0xFU << 8);
    GPIOB->AFR[0]  |= (3U << 8);           // AF3 = TIM1_CH3
    GPIOB->OSPEEDR |= (3U << 4);          // High Speed
    GPIOB->PUPDR   &= ~(GPIO_PUPDR_PUPD2);

    /* 5. Configure PB3 (Pin 9, Coil Pad 1) as Output Push-Pull HIGH (Safe Idle) */
    GPIOB->MODER   &= ~(GPIO_MODER_MODE3);
    GPIOB->MODER   |= (1U << 6);           // Mode 01 = Output
    GPIOB->OTYPER  &= ~(1U << 3);
    GPIOB->BSRR    = (1U << 3);            // 3.3V (P-FET closed)

    /* 6. Configure TIM1 for 1.0 kHz Hardware PWM
     *    Timer Clock: 24 MHz / (23 + 1) = 1.0 MHz
     *    PWM Period:  1.0 MHz / (999 + 1) = 1000 Hz (1.0 kHz)
     */
    TIM1->PSC = 23;
    TIM1->ARR = 999;

    /* Channel 1 (PA0, Indicator LED): PWM Mode 1 (Active HIGH) */
    TIM1->CCMR1 = (6U << 4) | TIM_CCMR1_OC1PE;
    TIM1->CCR1  = 500;                     // Initial 50%

    /* Channel 3 (PB2, Filaments P-FET): PWM Mode 1 with Preload */
    TIM1->CCMR2 = (6U << 4) | TIM_CCMR2_OC3PE;
    TIM1->CCR3  = 0;                       // Initial 0% (Completely OFF)

    /* Enable Outputs:
     * - CC1E: Output Channel 1 enabled (Polarity: normal, Active HIGH)
     * - CC3E: Output Channel 3 enabled
     * - CC3P: Output Channel 3 Polarity inverted (Active LOW for P-FET):
     *         CCR3 = 0    -> Pin is constantly HIGH (3.3V) -> P-FET 100% OFF!
     *         CCR3 = 500  -> Pin is LOW 50% of time -> 50% Brightness!
     *         CCR3 = 1000 -> Pin is constantly LOW (0V) -> P-FET 100% ON!
     */
    TIM1->CCER = TIM_CCER_CC1E | TIM_CCER_CC3E | TIM_CCER_CC3P;

    /* Master Output Enable & Counter Start */
    TIM1->BDTR = TIM_BDTR_MOE;
    TIM1->CR1  = TIM_CR1_CEN;

    /* 7. Main loop - core sleeps / idles, HW PWM runs with 0% CPU */
    while (1)
    {
        __NOP();
    }
}
