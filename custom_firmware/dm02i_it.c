// SPDX-License-Identifier: BSD-3-Clause
/**
 * @file    dm02i_it.c
 * @brief   Interrupt Service Routines for DM02i V03 Vape Board
 */

#include "py32f0xx.h"
#include "py32f002b_hal.h"
#include "dm02i_display.h"
#include "py32_dm02i_board.h"

void NMI_Handler(void) {
}

void HardFault_Handler(void) {
    while (1) {
    }
}

void SVC_Handler(void) {
}

void PendSV_Handler(void) {
}

/**
 * @brief 1 kHz SysTick Interrupt Handler
 *        Drives the 6-phase Charlieplexing multiplexer smoothly without CPU hogging
 */
void SysTick_Handler(void) {
    HAL_IncTick();

    /* 1. Следующий шаг мультиплексирования дисплея (1 кГц) */
    dm02i_render_step();

    /* 2. Анимационные счетчики дисплея */
    dm02i_tick_1ms();
}

/******************************************************************************/
/*                 PY32F002B Peripheral Interrupt Handlers                     */
/******************************************************************************/

void EXTI0_1_IRQHandler(void) {
    HAL_GPIO_EXTI_IRQHandler(GPIO_PIN_0);
    HAL_GPIO_EXTI_IRQHandler(GPIO_PIN_1);
}

void EXTI2_3_IRQHandler(void) {
    HAL_GPIO_EXTI_IRQHandler(GPIO_PIN_2);
    HAL_GPIO_EXTI_IRQHandler(GPIO_PIN_3);
}

void EXTI4_15_IRQHandler(void) {
    HAL_GPIO_EXTI_IRQHandler(GPIO_PIN_7); // Датчик затяжки PB7
}

void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin) {
    if (GPIO_Pin == GPIO_PIN_7) {
        // Пробуждение по затяжке
    }
}
