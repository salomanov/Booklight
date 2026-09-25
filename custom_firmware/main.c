// SPDX-License-Identifier: BSD-3-Clause
/**
 ******************************************************************************
 * @file    main.c
 * @brief   E-Book Reading Lamp - STEP 3..6: Filaments + LEDs + Display + Battery ADC & Charge
 *          MCU: PUYA PY32F002Bx5 (ARM Cortex-M0+ @ 24MHz)
 *          Board: CXV0257-V1.3
 * 
 *          Hardware pinout:
 *          - PA0 (Pin 13): TIM1_CH1 (AF2) -> Test Board LED (0..100% PWM, 0% = 100% OFF)
 *          - PA1 (Pin 14): GPIO Output -> FH8016 1-Wire Display (Non-blocking TIM14, 0% CPU)
 *          - PB2 (Pin 10): TIM1_CH3 (AF3) -> Coil Pad 2 (All 4 Filaments, P-FET CJ3415 up to 4.0A)
 *                          P-Channel FET (Active LOW via CC3P, 1.0 kHz Hardware PWM, 0% CPU)
 *          - PB3 (Pin 9):  Coil Pad 1 (Safe Output HIGH / Closed)
 *          - PB4 (Pin 8):  Touch Sensor (Pad M+ / TTP223) -> Input Pull-down
 *          - PB5 (Pin 7):  C60H Charge Status (CHRG Pin 1) -> Input Pull-up (0 = Charging)
 *          - ADC Internal: ADC_CHANNEL_VREFINT (Bandgap 1.20V) -> VDD/Battery Measurement
 *          - SWD Debug:    DBGMCU enabled, CoreSight debug active 24/7
 ******************************************************************************
 */

#include "py32f0xx.h"
#include "py32f002b_hal.h"
#include "py32f002b_hal_adc.h"
#include <stdint.h>
#include <stdbool.h>
#include "gyver_led.h"
#include "gyver_ubutton.h"
#include "fh8016_py32.h"

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

    /* FH8016 Display Control (1-Wire PA1, TIM14 non-blocking) */
    uint32_t disp_power;         // +0x34: 0 = OFF (sleep), 1 = ON
    uint32_t disp_percent;       // +0x38: 0..100
    uint32_t disp_bars;          // +0x3C: 0..4
    uint32_t disp_icons;         // +0x40: 0x02 = lightning
    uint32_t disp_hl_left;       // +0x44: color enum (0..7)
    uint32_t disp_hl_right;      // +0x48: color enum (0..7)
    uint32_t disp_auto_sync;     // +0x4C: 1 = auto, 0 = manual SWD test

    /* Battery & Charge Telemetry (Step 6) */
    uint32_t bat_millivolts;     // +0x50: mV (e.g. 3300 or 4150)
    uint32_t bat_percent;        // +0x54: 0..100%
    uint32_t bat_adc_raw;        // +0x58: raw ADC 12-bit code (0..4095)
    uint32_t chrg_pin_raw;       // +0x5C: 0 = LOW (charging active), 1 = HIGH (idle)
    uint32_t is_charging;        // +0x60: 1 = charging, 0 = battery power
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
    .fade_time_ms    = 250,

    .disp_power      = 1,
    .disp_percent    = 50,
    .disp_bars       = 2,
    .disp_icons      = 0,
    .disp_hl_left    = FH8016_COLOR_GREEN,
    .disp_hl_right   = FH8016_COLOR_GREEN,
    .disp_auto_sync  = 1,

    .bat_millivolts  = 3300,
    .bat_percent     = 1,
    .bat_adc_raw     = 1489,
    .chrg_pin_raw    = 1,
    .is_charging     = 0
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

/* ADC Handle for Battery Measurement */
static ADC_HandleTypeDef s_hadc;

static void adc_init(void)
{
    __HAL_RCC_ADC_CLK_ENABLE();

    s_hadc.Instance = ADC1;
    s_hadc.Init.ClockPrescaler        = ADC_CLOCK_SYNC_PCLK_DIV32;
    s_hadc.Init.Resolution            = ADC_RESOLUTION_12B;
    s_hadc.Init.DataAlign             = ADC_DATAALIGN_RIGHT;
    s_hadc.Init.ScanConvMode          = ADC_SCAN_DIRECTION_FORWARD;
    s_hadc.Init.EOCSelection          = ADC_EOC_SINGLE_CONV;
    s_hadc.Init.LowPowerAutoWait      = DISABLE;
    s_hadc.Init.ContinuousConvMode    = DISABLE;
    s_hadc.Init.DiscontinuousConvMode = DISABLE;
    s_hadc.Init.ExternalTrigConv      = ADC_SOFTWARE_START;
    s_hadc.Init.ExternalTrigConvEdge  = ADC_EXTERNALTRIGCONVEDGE_NONE;
    s_hadc.Init.Overrun               = ADC_OVR_DATA_OVERWRITTEN;
    s_hadc.Init.SamplingTimeCommon    = ADC_SAMPLETIME_41CYCLES_5;
    HAL_ADC_Init(&s_hadc);

    ADC_ChannelConfTypeDef sConfig = {0};
    sConfig.Rank    = ADC_RANK_CHANNEL_NUMBER;
    sConfig.Channel = ADC_CHANNEL_VREFINT;
    HAL_ADC_ConfigChannel(&s_hadc, &sConfig);

    HAL_ADC_ConfigVrefBuf(&s_hadc, ADC_VREFBUF_VCCA);
    SET_BIT(ADC->CCR, ADC_CCR_VREFEN);
    HAL_ADCEx_Calibration_Start(&s_hadc);
}

static uint8_t calc_bat_percent(uint16_t mv)
{
    if (mv >= 4150) return 100;
    if (mv >= 4050) return 90 + (uint8_t)(((mv - 4050) * 10) / 100);
    if (mv >= 3950) return 80 + (uint8_t)(((mv - 3950) * 10) / 100);
    if (mv >= 3850) return 65 + (uint8_t)(((mv - 3850) * 15) / 100);
    if (mv >= 3780) return 50 + (uint8_t)(((mv - 3780) * 15) / 70);
    if (mv >= 3700) return 35 + (uint8_t)(((mv - 3700) * 15) / 80);
    if (mv >= 3600) return 20 + (uint8_t)(((mv - 3600) * 15) / 100);
    if (mv >= 3450) return 10 + (uint8_t)(((mv - 3450) * 10) / 150);
    if (mv >= 3300) return 1  + (uint8_t)(((mv - 3300) * 9)  / 150);
    return 0;
}

static uint16_t s_filtered_mv = 3300;

static void sample_battery_and_charge(void)
{
    /* 1. Read C60H charge controller status pin (PB5, Pin 7) */
    bool pin_low = (GPIOB->IDR & (1U << 5)) == 0;
    g_lamp.chrg_pin_raw = pin_low ? 0 : 1;

    /* 2. Sample 12-bit ADC on 1.20V Bandgap reference */
    HAL_ADC_Start(&s_hadc);
    if (HAL_ADC_PollForConversion(&s_hadc, 5) == HAL_OK)
    {
        uint32_t raw = HAL_ADC_GetValue(&s_hadc);
        g_lamp.bat_adc_raw = raw;
        if (raw > 500 && raw < 4095)
        {
            uint32_t inst_mv = (4095UL * 1200UL) / raw;
            /* Smooth exponential filter: 7/8 previous + 1/8 new */
            s_filtered_mv = (uint16_t)(((uint32_t)s_filtered_mv * 7 + inst_mv) / 8);
        }
    }
    g_lamp.bat_millivolts = s_filtered_mv;
    g_lamp.bat_percent = calc_bat_percent(s_filtered_mv);

    /* 3. Determine overall charging status:
     * Active if C60H pulls PB5 LOW, OR if battery voltage spikes above 4.18V
     */
    if (pin_low || s_filtered_mv >= 4180)
    {
        g_lamp.is_charging = 1;
    }
    else
    {
        g_lamp.is_charging = 0;
    }
}

int main(void)
{
    /* 1. Enable DBGMCU peripheral clock and keep SWD debug port active in STOP mode */
    RCC->APBENR1 |= RCC_APBENR1_DBGEN;
    DBGMCU->CR |= DBGMCU_CR_DBG_STOP;

    /* 2. Enable Clocks: GPIOA, GPIOB, TIM1, TIM14, ADC */
    RCC->IOPENR  |= RCC_IOPENR_GPIOAEN | RCC_IOPENR_GPIOBEN;
    RCC->APBENR2 |= RCC_APBENR2_TIM1EN | RCC_APBENR2_TIM14EN;

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

    /* 7. Configure PB5 (Pin 7, C60H Charge Status Pin) as Input with Pull-Up */
    GPIOB->MODER   &= ~(GPIO_MODER_MODE5); // Mode 00 = Input
    GPIOB->PUPDR   &= ~(GPIO_PUPDR_PUPD5);
    GPIOB->PUPDR   |= (1U << 10);          // 01 = Pull-Up

    /* 8. Configure TIM1 for 1.0 kHz Hardware PWM */
    TIM1->PSC = 23;
    TIM1->ARR = 999;

    /* Channel 1 (PA0, Board LED): PWM Mode 1 (Active HIGH) */
    TIM1->CCMR1 = (6U << 4) | TIM_CCMR1_OC1PE;
    TIM1->CCR1  = 0;                      // 0% -> completely OFF (0V)

    /* Channel 3 (PB2, Filaments P-FET): PWM Mode 1 with Preload */
    TIM1->CCMR2 = (6U << 4) | TIM_CCMR2_OC3PE;
    TIM1->CCR3  = 0;                      // 0% -> completely OFF (3.3V)

    TIM1->CCER = TIM_CCER_CC1E | TIM_CCER_CC3E | TIM_CCER_CC3P;
    TIM1->BDTR = TIM_BDTR_MOE;
    TIM1->CR1  = TIM_CR1_CEN;

    /* 9. Configure FH8016 1-Wire Display on PA1 (Pin 14 / Pad DAT) with TIM14 non-blocking engine */
    fh8016_t disp;
    fh8016_init(&disp, GPIOA, GPIO_PIN_1);

    /* 10. Initialize 12-bit ADC on 1.20V Bandgap reference */
    adc_init();

    /* 11. 1 ms System Timebase via SysTick */
    SysTick_Config(SystemCoreClock / 1000U);

    /* 12. Initialize GyverLED for both independent channels */
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
    uint32_t last_disp_ms = 0;
    uint32_t last_bat_ms = 0;

    /* Initial sample */
    sample_battery_and_charge();

    /* 13. Main non-blocking event loop */
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

        /* D. Check for SWD commands for Board LEDs */
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

        /* H. Sample Battery & Charge Status every 300 ms */
        if (now - last_bat_ms >= 300)
        {
            last_bat_ms = now;
            sample_battery_and_charge();
        }

        /* I. FH8016 Display update (Every 40 ms / 25 Hz, 100% non-blocking via TIM14) */
        if (now - last_disp_ms >= 40)
        {
            last_disp_ms = now;

            if (g_lamp.disp_auto_sync)
            {
                /* Auto-sync mode */
                if (g_lamp.is_charging)
                {
                    /* CHARGING MODE: Running snake animation, lightning ON, Cyan headlights */
                    uint8_t anim_step = (uint8_t)((now / 350U) % 5U);
                    g_lamp.disp_power    = 1;
                    g_lamp.disp_percent  = g_lamp.bat_percent;
                    g_lamp.disp_bars     = (anim_step == 0) ? 1 : anim_step;
                    g_lamp.disp_icons    = FH8016_ICON_LIGHTNING;
                    g_lamp.disp_hl_left  = FH8016_COLOR_CYAN;
                    g_lamp.disp_hl_right = FH8016_COLOR_CYAN;

                    fh8016_set_state(&disp, g_lamp.bat_percent, g_lamp.disp_bars, 
                                     FH8016_ICON_LIGHTNING, FH8016_COLOR_CYAN, FH8016_COLOR_CYAN);
                }
                else if (g_lamp.fil_state || g_lamp.fil_current_pct > 0)
                {
                    /* LAMP IS ACTIVE: Display shows filament brightness percentage */
                    uint8_t cur = (uint8_t)g_lamp.fil_current_pct;
                    uint8_t bars = (cur >= 80) ? 4 : (cur >= 60) ? 3 : (cur >= 40) ? 2 : (cur >= 20) ? 1 : 0;
                    fh8016_color_t color = (g_lamp.bat_percent >= 60) ? FH8016_COLOR_GREEN : 
                                           (g_lamp.bat_percent >= 25) ? FH8016_COLOR_YELLOW : FH8016_COLOR_RED;
                    
                    g_lamp.disp_power    = 1;
                    g_lamp.disp_percent  = cur;
                    g_lamp.disp_bars     = bars;
                    g_lamp.disp_icons    = 0;
                    g_lamp.disp_hl_left  = color;
                    g_lamp.disp_hl_right = color;

                    fh8016_set_state(&disp, cur, bars, 0, color, color);
                }
                else
                {
                    /* Lamp is OFF and not charging -> display sleep */
                    g_lamp.disp_power = 0;
                    fh8016_set_raw(&disp, 0);
                }
            }
            else
            {
                /* Manual SWD test mode: PC GUI has direct control */
                if (g_lamp.disp_power)
                {
                    fh8016_set_state(&disp, 
                                     (uint8_t)g_lamp.disp_percent, 
                                     (uint8_t)g_lamp.disp_bars, 
                                     (uint8_t)g_lamp.disp_icons,
                                     (fh8016_color_t)g_lamp.disp_hl_left, 
                                     (fh8016_color_t)g_lamp.disp_hl_right);
                }
                else
                {
                    fh8016_set_raw(&disp, 0);
                }
            }

            /* Trigger non-blocking 1-Wire transmission in TIM14 hardware interrupt */
            fh8016_update(&disp);
        }
    }
}
