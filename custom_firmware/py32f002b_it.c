/**
  ******************************************************************************
  * @file    py32f002b_it.c
  * @author  MCU Application Team
  * @brief   Interrupt Service Routines.
  ******************************************************************************
  */

#include "py32f002b_hal.h"
#include "py32f002b_it.h"
#include "book_light.h"

/******************************************************************************/
/*            Cortex-M0+ Processor Exceptions Handlers                         */
/******************************************************************************/

void NMI_Handler(void)
{
}

void HardFault_Handler(void)
{
    while (1)
    {
    }
}

void SVC_Handler(void)
{
}

void PendSV_Handler(void)
{
}

/* SysTick runs at 20 kHz (50 us period)
 * 20 ticks = 1 ms (1000 Hz)
 */
static volatile uint8_t systick_ms_div = 0;

void SysTick_Handler(void)
{
    /* 1. Fast PWM Step (200 Hz PWM across 100 duty steps) */
    book_light_pwm_tick();

    /* 2. 1 ms Timebase */
    if (++systick_ms_div >= 20) {
        systick_ms_div = 0;
        HAL_IncTick();
        book_light_tick_1ms();
    }
}

/******************************************************************************/
/*                 PY32F002B Peripheral Interrupt Handlers                     */
/******************************************************************************/

void EXTI0_1_IRQHandler(void)
{
    HAL_GPIO_EXTI_IRQHandler(GPIO_PIN_0);
    HAL_GPIO_EXTI_IRQHandler(GPIO_PIN_1);
}

void EXTI2_3_IRQHandler(void)
{
    HAL_GPIO_EXTI_IRQHandler(GPIO_PIN_2);
    HAL_GPIO_EXTI_IRQHandler(GPIO_PIN_3);
}

void EXTI4_15_IRQHandler(void)
{
    HAL_GPIO_EXTI_IRQHandler(GPIO_PIN_4);
    HAL_GPIO_EXTI_IRQHandler(GPIO_PIN_5);
    HAL_GPIO_EXTI_IRQHandler(GPIO_PIN_6);
    HAL_GPIO_EXTI_IRQHandler(GPIO_PIN_7);
}

void HAL_GPIO_EXTI_Callback(uint16_t GPIO_Pin)
{
    book_light_on_touch_irq();
}
