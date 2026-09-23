// SPDX-License-Identifier: BSD-3-Clause
/**
  ******************************************************************************
  * @file    main.c
  * @brief   E-Book Reading Lamp Firmware for PY32F002B / FH8020 (W39A_V1.4)
  *          Features:
  *          - Capacitive Touch Button control (Toggle ON/OFF, smooth fade, dimming ramp)
  *          - Flexible 3V LED Filament drive with Gamma 2.2 perceptual PWM
  *          - 1-Wire FH8016 Display (Battery %, 4-arc scale, charging animation)
  *          - 15-minute inactivity timer with 1-minute smooth fade-out (interruptible)
  *          - Ultra-low-power STOP mode deep sleep (< 10 uA) with EXTI wakeup
  ******************************************************************************
  */

#include "py32f002b_hal.h"
#include "book_light.h"

int main(void)
{
    /* 1. Initialize HAL driver */
    HAL_Init();

    /* 2. Configure SysTick for 20 kHz (50 us period)
     *    - Fast software PWM for LED filament (200 Hz across 100 duty steps)
     *    - 1 ms system timebase (every 20 ticks)
     */
    SysTick_Config(SystemCoreClock / 20000);

    /* 3. Initialize E-Book Lamp hardware (GPIO, ADC, Display, State) */
    book_light_init();

    /* 4. Main Event Loop */
    while (1)
    {
        book_light_loop();
    }
}
