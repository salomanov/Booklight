// SPDX-License-Identifier: BSD-3-Clause
/**
 ******************************************************************************
 * @file    main.c
 * @brief   E-Book Reading Lamp - STEP 3 & 4: Independent Channels + GyverLED
 *          MCU: PUYA PY32F002Bx5 (ARM Cortex-M0+ @ 24MHz)
 *          Board: CXV0257-V1.3
 * 
 *          Hardware pinout:
 *          - PA0 (Pin 13): TIM1_CH1 (AF2) -> Test Board LED (0..100% PWM, 0% = 100% OFF)
 *          - PB2 (Pin 10): TIM1_CH3 (AF3) -> Coil Pad 2 (All 4 Filaments, P-FET CJ3415 up to 4.0A)
 *                          P-Channel FET (Active LOW via CC3P, 1.0 kHz Hardware PWM, 0% CPU)
 *          - PB3 (Pin 9):  Coil Pad 1 (Safe Output HIGH / Closed)
 *          - PB4 (Pin 8):  Touch Sensor (Pad M+ / TTP223) -> Input Pull-down
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
    uint32_t magic;              // +0x00: 0x50574D31 ('PWM1')
    
    /* Channel 1: Filaments (PB2 / TIM1_CH3) */
    uint32_t fil_target_pct;     // +0x04: 0..100% (target brightness)
    uint32_t fil_current_pct;    // +0x08: 0..100% (live interpolated)
    uint32_t fil_pwm_raw;        // +0x0C: 0..1000 (actual TIM1_CCR3)
    uint32_t fil_state;          // +0x10: 0 = OFF, 1 = ON
    uint32_t fil_saved_pct;      // +0x14: Last ON value (1..100%, default 50%)
    
    /* Channel 2: Board LEDs (PA0 / TIM1_CH1) */
    uint32_t led_target_pct;     // +0x18: 0..100% (target brightness)
    uint32_t led_current_pct;    // +0x1C: 0..100% (live interpolated)
    uint32_t led_pwm_raw;        // +0x20: 0..1000 (actual TIM1_CCR1)
    uint32_t led_state;          // +0x24: 0 = OFF, 1 = ON
    uint32_t led_saved_pct;      // +0x28: Last ON value (1..100%, default 50%)
    
    /* Touch sensor and transition */
    uint32_t touch_raw;          // +0x2C: 1 = touch detected on PB4, 0 = idle
    uint32_t fade_time_ms;       // +0x30: Transition duration in ms (default 250)
} LampSharedControl_t;

volatile LampSharedControl_t g_lamp = {
    .magic           = 0x50574D31,
    .fil_target_pct  = 0,
    .fil_current_pct = 0,
    .fil_pwm_raw     = 0,
    .fil_state       = 0,
    .fil_saved_pct   = 50,

    .led_target_pct  = 0,
    .led_current_pct = 0,
    .led_pwm_raw     = 0,
    .led_state       = 0,
    .led_saved_pct   = 50,

    .touch_raw       = 0,
    .fade_time_ms    = 250
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

    /* 3. Configure PA0 (Pin 13) as Alternate Function 2 (TIM1_CH1, Test Board LED) */
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

    /* 5. Configure PB3 (Pin 9, Coil Pad 1) as Output Push-Pull HIGH (Safe Closed) */
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

    /* Channel 1 (PA0, Board LED): PWM Mode 1 (Active HIGH) */
    TIM1->CCMR1 = (6U << 4) | TIM_CCMR1_OC1PE;
    TIM1->CCR1  = 0;                      // 0% -> completely OFF (0V)

    /* Channel 3 (PB2, Filaments P-FET): PWM Mode 1 with Preload */
    TIM1->CCMR2 = (6U << 4) | TIM_CCMR2_OC3PE;
    TIM1->CCR3  = 0;                      // 0% -> completely OFF (3.3V)

    /* Enable Outputs:
     * - CC1E: Output Channel 1 enabled (Active HIGH)
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

    /* 9. Initialize GyverLED for both independent channels */
    gyver_led_t fil_led;
    gled_init(&fil_led, 1000);            // 0..1000 PWM
    gled_set_gamma(&fil_led, true);       // Perceptual Gamma 2.2 curve

    gyver_led_t board_led;
    gled_init(&board_led, 1000);          // 0..1000 PWM
    gled_set_gamma(&board_led, true);     // Perceptual Gamma 2.2 curve

    ubutton_t touch_btn;
    ubutton_init(&touch_btn);

    int8_t dim_direction = 1;             // +1 = brightening, -1 = dimming
    uint32_t last_swd_fil_target = 0;
    uint32_t last_swd_led_target = 0;

    /* 10. Main non-blocking event loop */
    while (1)
    {
        uint32_t now = millis();

        /* A. Read capacitive touch sensor (TTP223 on PB4: HIGH = Finger touched) */
        bool is_touched = (GPIOB->IDR & (1U << 4)) != 0;
        g_lamp.touch_raw = is_touched ? 1 : 0;

        /* B. Tick GyverButton state machine (Controls ONLY Filaments) */
        if (ubutton_tick(&touch_btn, is_touched, now))
        {
            /* Short click: Toggle Filaments ON / OFF with last-value memory */
            if (ubutton_click(&touch_btn))
            {
                if (g_lamp.fil_state)
                {
                    g_lamp.fil_state = 0;
                    g_lamp.fil_target_pct = 0;
                    last_swd_fil_target = 0;
                    gled_fade(&fil_led, 0, g_lamp.fade_time_ms);
                }
                else
                {
                    g_lamp.fil_state = 1;
                    if (g_lamp.fil_saved_pct < 1) g_lamp.fil_saved_pct = 50;
                    g_lamp.fil_target_pct = g_lamp.fil_saved_pct;
                    last_swd_fil_target = g_lamp.fil_saved_pct;
                    uint8_t byte_val = (uint8_t)((g_lamp.fil_saved_pct * 255U) / 100U);
                    gled_fade(&fil_led, byte_val, g_lamp.fade_time_ms);
                }
            }

            /* Hold: Smooth dimming of Filaments */
            if (ubutton_step(&touch_btn))
            {
                if (!g_lamp.fil_state)
                {
                    g_lamp.fil_state = 1;
                }

                int32_t new_pct = (int32_t)g_lamp.fil_saved_pct + (dim_direction * 2);
                if (new_pct > 100) { new_pct = 100; }
                if (new_pct < 1)   { new_pct = 1; }

                g_lamp.fil_saved_pct  = (uint32_t)new_pct;
                g_lamp.fil_target_pct = (uint32_t)new_pct;
                last_swd_fil_target   = (uint32_t)new_pct;

                uint8_t byte_val = (uint8_t)((g_lamp.fil_saved_pct * 255U) / 100U);
                gled_fade(&fil_led, byte_val, 30);
            }

            /* Release after hold: Reverse dim direction for next time */
            if (ubutton_release_step(&touch_btn))
            {
                dim_direction = -dim_direction;
            }
        }

        /* C. Check for SWD commands for Filaments */
        if (g_lamp.fil_target_pct != last_swd_fil_target)
        {
            last_swd_fil_target = g_lamp.fil_target_pct;
            if (last_swd_fil_target > 0)
            {
                g_lamp.fil_state = 1;
                g_lamp.fil_saved_pct = last_swd_fil_target;
            }
            else
            {
                g_lamp.fil_state = 0;
            }
            uint8_t byte_val = (uint8_t)((last_swd_fil_target * 255U) / 100U);
            gled_fade(&fil_led, byte_val, g_lamp.fade_time_ms);
        }

        /* D. Check for SWD commands for Board LEDs (Independent Channel) */
        if (g_lamp.led_target_pct != last_swd_led_target)
        {
            last_swd_led_target = g_lamp.led_target_pct;
            if (last_swd_led_target > 0)
            {
                g_lamp.led_state = 1;
                g_lamp.led_saved_pct = last_swd_led_target;
            }
            else
            {
                g_lamp.led_state = 0;
            }
            uint8_t byte_val = (uint8_t)((last_swd_led_target * 255U) / 100U);
            gled_fade(&board_led, byte_val, g_lamp.fade_time_ms);
        }

        /* E. Tick GyverLED for Filaments */
        if (gled_tick(&fil_led, now))
        {
            TIM1->CCR3 = (fil_led.current == 0) ? 0 : fil_led.pwm_val;
        }

        /* F. Tick GyverLED for Board LEDs */
        if (gled_tick(&board_led, now))
        {
            TIM1->CCR1 = (board_led.current == 0) ? 0 : board_led.pwm_val;
        }

        /* G. Update live telemetry */
        g_lamp.fil_current_pct = (uint32_t)((fil_led.current * 100U + 127U) / 255U);
        g_lamp.fil_pwm_raw     = TIM1->CCR3;

        g_lamp.led_current_pct = (uint32_t)((board_led.current * 100U + 127U) / 255U);
        g_lamp.led_pwm_raw     = TIM1->CCR1;
    }
}
