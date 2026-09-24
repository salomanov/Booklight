// SPDX-License-Identifier: BSD-3-Clause
/**
 ******************************************************************************
 * @file    main.c
 * @brief   E-Book Reading Lamp - STEP 2: Hardware PWM (TIM1_CH1) & 3-Channel Control
 *          MCU: PUYA PY32F002Bx5 (ARM Cortex-M0+ @ 24MHz)
 *          Board: CXV0257-V1.3
 * 
 *          Hardware pinout:
 *          - PA0 (Pin 13): TIM1_CH1 (AF2) -> Indicator LED / PWM test channel
 *          - PB3 (Pin 9):  Power MOSFET 1 Gate -> Coil Pad 1 (Active LOW for P-FET)
 *          - PB2 (Pin 10): Power MOSFET 2 Gate -> Coil Pad 2 (Active LOW for P-FET)
 *          - SWD Debug:    DBGMCU enabled, CoreSight debug active 24/7
 ******************************************************************************
 */

#include "py32f0xx.h"

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

    /* 5. Safe initial state for power MOSFETs:
     * PB2 and PB3 = HIGH (P-FETs closed / off)
     */
    GPIOB->BSRR = GPIO_BSRR_BS2 | GPIO_BSRR_BS3;

    /* 6. Configure TIM1 for 1 kHz Hardware PWM on Channel 1 */
    TIM1->PSC = 23;                       // Prescaler: 24 MHz / (23 + 1) = 1 MHz timer clock
    TIM1->ARR = 999;                      // Period: 1 MHz / (999 + 1) = 1.0 kHz PWM frequency
    TIM1->CCR1 = 500;                     // Initial duty cycle: 50% (500 / 1000)

    /* PWM Mode 1 (OC1M = 110: Active while CNT < CCR1), Preload Enable */
    TIM1->CCMR1 = (6U << 4) | TIM_CCMR1_OC1PE;

    /* Enable Channel 1 Output, Main Output Enable, Counter Enable */
    TIM1->CCER = TIM_CCER_CC1E;
    TIM1->BDTR = TIM_BDTR_MOE;
    TIM1->CR1 = TIM_CR1_CEN;

    /* 7. Main loop - core stays awake 24/7 with SWD active */
    while (1)
    {
        __NOP();
    }
}
