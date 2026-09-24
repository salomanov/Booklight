// SPDX-License-Identifier: BSD-3-Clause
/**
 ******************************************************************************
 * @file    main.c
 * @brief   E-Book Reading Lamp - STEP 3 & 4: GyverLED + GyverButton + Gamma 2.2
 *          MCU: PUYA PY32F002Bx5 (ARM Cortex-M0+ @ 24MHz)
 *          Board: CXV0257-V1.3
 * 
 *          Hardware pinout:
 *          - PA0 (Pin 13): TIM1_CH1 (AF2) -> Indicator LED (1.0 kHz Hardware PWM)
 *          - PB2 (Pin 10): TIM1_CH3 (AF3) -> Power MOSFET 2 (Coil Pad 2: All 4 Filaments)
 *                          P-Channel FET (Active LOW via CC3P, 1.0 kHz Hardware PWM, 0% CPU)
 *          - PB3 (Pin 9):  Power MOSFET 1 (Coil Pad 1) -> Safe Output HIGH (Closed)
 *          - PB4 (Pin 8):  Touch Button (Pad M+ / TTP223) -> Input Pull-down
 *          - SWD Debug:    DBGMCU enabled, CoreSight debug active 24/7
 ******************************************************************************
 */

#include "py32f0xx.h"
#include <stdint.h>
#include <stdbool.h>
#include "gyver_led.h"
#include "gyver_ubutton.h"

/* Shared memory block for SWD control and telemetry */
typedef struct {
    uint32_t magic;           // 0x50574D31 ('PWM1')
    uint32_t target_brightness;// 0..255
    uint32_t current_brightness;// 0..255
    uint32_t pwm_raw;         // 0..1000 (actual TIM1_CCR3 hardware value)
    uint32_t touch_raw;       // 1 = touch detected on PB4, 0 = idle
    uint32_t fade_time_ms;    // Fade duration in ms (default 350 ms)
    uint32_t lamp_state;      // 0 = OFF, 1 = ON
} LampSharedControl_t;

volatile LampSharedControl_t g_lamp = {
    .magic              = 0x50574D31,
    .target_brightness  = 0,
    .current_brightness = 0,
    .pwm_raw            = 0,
    .touch_raw          = 0,
    .fade_time_ms       = 350,
    .lamp_state         = 0
};

/* Millisecond timebase via SysTick */
static volatile uint32_t s_millis = 0;

void SysTick_Handler(void)
{
    s_millis++;
}

uint32_t millis(void)
{
    return s_millis;
}

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

    /* 6. Configure PB4 (Pin 8, Touch Pad M+ / TTP223) as Input with Pull-Down */
    GPIOB->MODER   &= ~(GPIO_MODER_MODE4); // Mode 00 = Input
    GPIOB->PUPDR   &= ~(GPIO_PUPDR_PUPD4);
    GPIOB->PUPDR   |= (GPIO_PUPDR_PUPD4_1);// 10 = Pull-Down

    /* 7. Configure TIM1 for 1.0 kHz Hardware PWM
     *    Timer Clock: 24 MHz / (23 + 1) = 1.0 MHz
     *    PWM Period:  1.0 MHz / (999 + 1) = 1000 Hz (1.0 kHz)
     */
    TIM1->PSC = 23;
    TIM1->ARR = 999;

    /* Channel 1 (PA0, Indicator LED): PWM Mode 1 (Active HIGH) */
    TIM1->CCMR1 = (6U << 4) | TIM_CCMR1_OC1PE;
    TIM1->CCR1  = 100;                    // Soft idle glow on indicator

    /* Channel 3 (PB2, Filaments P-FET): PWM Mode 1 with Preload */
    TIM1->CCMR2 = (6U << 4) | TIM_CCMR2_OC3PE;
    TIM1->CCR3  = 0;                      // Initial 0% (Completely OFF)

    /* Enable Outputs:
     * - CC1E: Output Channel 1 enabled
     * - CC3E: Output Channel 3 enabled
     * - CC3P: Output Channel 3 Polarity inverted (Active LOW for P-FET):
     *         CCR3 = 0    -> Pin HIGH (3.3V) -> P-FET 100% OFF
     *         CCR3 = 1000 -> Pin LOW (0V)   -> P-FET 100% ON
     */
    TIM1->CCER = TIM_CCER_CC1E | TIM_CCER_CC3E | TIM_CCER_CC3P;

    /* Master Output Enable & Counter Start */
    TIM1->BDTR = TIM_BDTR_MOE;
    TIM1->CR1  = TIM_CR1_CEN;

    /* 8. 1 ms System Timebase via SysTick */
    SysTick_Config(SystemCoreClock / 1000U);

    /* 9. Initialize GyverLED and GyverButton */
    gyver_led_t lamp_led;
    gled_init(&lamp_led, 1000);           // Max PWM = 1000 for TIM1
    gled_set_gamma(&lamp_led, true);      // Enable Gamma 2.2 perceptual curve

    ubutton_t touch_btn;
    ubutton_init(&touch_btn);

    uint8_t saved_brightness = 180;       // ~70% default reading brightness (0..255)
    int8_t dim_direction = 1;             // +1 = brightening, -1 = dimming
    uint32_t last_swd_target = 0;

    /* 10. Main non-blocking event loop */
    while (1)
    {
        uint32_t now = millis();

        /* A. Read capacitive touch sensor (TTP223 on PB4: HIGH = Finger touched) */
        bool is_touched = (GPIOB->IDR & (1U << 4)) != 0;
        g_lamp.touch_raw = is_touched ? 1 : 0;

        /* B. Tick GyverButton state machine */
        if (ubutton_tick(&touch_btn, is_touched, now))
        {
            /* Short click: Toggle Lamp ON / OFF with smooth fade */
            if (ubutton_click(&touch_btn))
            {
                if (g_lamp.lamp_state)
                {
                    g_lamp.lamp_state = 0;
                    g_lamp.target_brightness = 0;
                    gled_fade(&lamp_led, 0, g_lamp.fade_time_ms);
                }
                else
                {
                    g_lamp.lamp_state = 1;
                    if (saved_brightness < 15) saved_brightness = 150;
                    g_lamp.target_brightness = saved_brightness;
                    gled_fade(&lamp_led, saved_brightness, g_lamp.fade_time_ms);
                }
            }

            /* Hold: Smooth dimming step */
            if (ubutton_step(&touch_btn))
            {
                if (!g_lamp.lamp_state)
                {
                    g_lamp.lamp_state = 1;
                }

                if (dim_direction > 0)
                {
                    if (saved_brightness <= 250) saved_brightness += 5;
                    else saved_brightness = 255;
                }
                else
                {
                    if (saved_brightness >= 15) saved_brightness -= 5;
                    else saved_brightness = 10;
                }

                g_lamp.target_brightness = saved_brightness;
                gled_fade(&lamp_led, saved_brightness, 25);
            }

            /* Release after hold: Reverse dim direction for next time */
            if (ubutton_release_step(&touch_btn))
            {
                dim_direction = -dim_direction;
            }
        }

        /* C. Check for SWD commands from PC GUI */
        if (g_lamp.target_brightness != last_swd_target)
        {
            last_swd_target = g_lamp.target_brightness;
            if (last_swd_target > 0)
            {
                g_lamp.lamp_state = 1;
                saved_brightness = (uint8_t)last_swd_target;
            }
            else
            {
                g_lamp.lamp_state = 0;
            }
            gled_fade(&lamp_led, (uint8_t)last_swd_target, g_lamp.fade_time_ms);
        }

        /* D. Tick GyverLED (non-blocking step) */
        if (gled_tick(&lamp_led, now))
        {
            TIM1->CCR3 = lamp_led.pwm_val; // Update hardware PWM on PB2!
        }

        /* E. Update live telemetry */
        g_lamp.current_brightness = lamp_led.current;
        g_lamp.pwm_raw            = lamp_led.pwm_val;

        /* Indicator LED reflects lamp state */
        TIM1->CCR1 = (g_lamp.lamp_state) ? 500 : 50;
    }
}
