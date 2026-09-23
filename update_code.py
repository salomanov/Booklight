import sys

content = """// SPDX-License-Identifier: BSD-3-Clause
#include "py32f002b_hal.h"
#include "py32f002b_hal_adc.h"
#include "fh8016_py32.h"
#include "gyver_rgbmath.h"
#include "book_light.h"
#include <stdbool.h>

#define LED_PINS                    (GPIO_PIN_0 | GPIO_PIN_5)
#define TOUCH_PIN                   GPIO_PIN_5
#define CHARGE_SENSE_PIN_B4         GPIO_PIN_4
#define CHARGE_SENSE_PIN_B3         GPIO_PIN_3

static fh8016_t disp;
static ADC_HandleTypeDef hadc_bat;

static volatile uint8_t pwm_counter = 0;
static volatile uint8_t pwm_duty = 0;

static bool lamp_on = false;
static uint8_t current_brightness = 0;
static uint8_t target_brightness = 0;
static uint8_t saved_brightness = 70;
static int8_t dim_direction = 1;

static uint32_t show_brightness_until = 0;
static uint32_t lamp_on_timestamp = 0;
static uint32_t last_fade_tick = 0;
static uint32_t last_dim_tick = 0;
static uint32_t last_bat_sample = 0;

static bool touch_raw_prev = false;
static bool touch_stable = false;
static uint32_t touch_change_time = 0;
static uint32_t touch_press_start = 0;
static bool is_holding = false;

static uint16_t bat_millivolts = 3950;
static uint8_t bat_percent = 85;
static bool is_charging = false;

void book_light_pwm_tick(void)
{
    if (++pwm_counter >= 100) pwm_counter = 0;
    if (pwm_duty > 0 && pwm_counter < pwm_duty) {
        GPIOA->BSRR = LED_PINS;
    } else {
        GPIOA->BRR = LED_PINS;
    }
}

void book_light_tick_1ms(void) {}
void book_light_on_touch_irq(void) {}

static void init_adc(void)
{
    __HAL_RCC_ADC_CLK_ENABLE();
    hadc_bat.Instance = ADC1;
    hadc_bat.Init.ClockPrescaler = ADC_CLOCK_SYNC_PCLK_DIV32;
    hadc_bat.Init.Resolution = ADC_RESOLUTION_12B;
    hadc_bat.Init.DataAlign = ADC_DATAALIGN_RIGHT;
    hadc_bat.Init.ScanConvMode = ADC_SCAN_DIRECTION_FORWARD;
    hadc_bat.Init.EOCSelection = ADC_EOC_SINGLE_CONV;
    hadc_bat.Init.LowPowerAutoWait = DISABLE;
    hadc_bat.Init.ContinuousConvMode = DISABLE;
    hadc_bat.Init.DiscontinuousConvMode = DISABLE;
    hadc_bat.Init.ExternalTrigConv = ADC_SOFTWARE_START;
    hadc_bat.Init.ExternalTrigConvEdge = ADC_EXTERNALTRIGCONVEDGE_NONE;
    hadc_bat.Init.Overrun = ADC_OVR_DATA_OVERWRITTEN;
    hadc_bat.Init.SamplingTimeCommon = ADC_SAMPLETIME_41CYCLES_5;
    HAL_ADC_Init(&hadc_bat);

    ADC_ChannelConfTypeDef sConfig = {0};
    sConfig.Rank = ADC_RANK_CHANNEL_NUMBER;
    sConfig.Channel = ADC_CHANNEL_VREFINT;
    HAL_ADC_ConfigChannel(&hadc_bat, &sConfig);
    HAL_ADC_ConfigVrefBuf(&hadc_bat, ADC_VREFBUF_VCCA);
    HAL_ADCEx_Calibration_Start(&hadc_bat);
}

static uint16_t read_battery_mv(void)
{
    HAL_ADC_Start(&hadc_bat);
    if (HAL_ADC_PollForConversion(&hadc_bat, 5000) == HAL_OK) {
        uint32_t val = HAL_ADC_GetValue(&hadc_bat);
        if (val > 200 && val < 4095) {
            return (uint16_t)((4095UL * 1200UL) / val);
        }
    }
    return 0;
}

static uint8_t calc_battery_percent(uint16_t mv)
{
    if (mv >= 4150) return 100;
    if (mv >= 4050) return 90 + (uint8_t)(((mv - 4050) * 10) / 100);
    if (mv >= 3950) return 80 + (uint8_t)(((mv - 3950) * 10) / 100);
    if (mv >= 3850) return 65 + (uint8_t)(((mv - 3850) * 15) / 100);
    if (mv >= 3780) return 50 + (uint8_t)(((mv - 3780) * 15) / 70);
    if (mv >= 3700) return 35 + (uint8_t)(((mv - 3700) * 15) / 80);
    if (mv >= 3600) return 20 + (uint8_t)(((mv - 3600) * 15) / 100);
    if (mv >= 3450) return 10 + (uint8_t)(((mv - 3450) * 10) / 150);
    if (mv >= 3300) return 1 + (uint8_t)(((mv - 3300) * 9) / 150);
    return 1;
}

int main(void)
{
    HAL_Init();
    SysTick_Config(SystemCoreClock / 20000);
    __HAL_RCC_DBGMCU_CLK_ENABLE();
    HAL_DBGMCU_EnableDBGMCUStopMode();
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();

    GPIO_InitTypeDef g = {0};
    g.Pin = LED_PINS;
    g.Mode = GPIO_MODE_OUTPUT_PP;
    g.Pull = GPIO_NOPULL;
    g.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(GPIOA, &g);
    GPIOA->BRR = LED_PINS;

    g.Pin = TOUCH_PIN;
    g.Mode = GPIO_MODE_INPUT;
    g.Pull = GPIO_PULLDOWN;
    g.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(GPIOB, &g);

    g.Pin = CHARGE_SENSE_PIN_B4 | CHARGE_SENSE_PIN_B3;
    g.Mode = GPIO_MODE_INPUT;
    g.Pull = GPIO_PULLUP;
    HAL_GPIO_Init(GPIOB, &g);

    fh8016_init(&disp, GPIOA, GPIO_PIN_1);
    init_adc();

    bat_millivolts = read_battery_mv();
    if (bat_millivolts == 0) bat_millivolts = 3950;
    bat_percent = calc_battery_percent(bat_millivolts);

    while (1) {
        uint32_t now = HAL_GetTick();
        if (now - last_bat_sample >= 200) {
            last_bat_sample = now;
            uint16_t s = read_battery_mv();
            if (s > 2500 && s < 4500) {
                bat_millivolts = (uint16_t)(((uint32_t)bat_millivolts * 7 + s) / 8);
                bat_percent = calc_battery_percent(bat_millivolts);
            }
            bool v_high = (bat_millivolts >= 4180) || (bat_millivolts >= 4140 && bat_percent >= 95);
            bool p_chrg = (HAL_GPIO_ReadPin(GPIOB, CHARGE_SENSE_PIN_B4) == GPIO_PIN_RESET);
            bool p_vbus = (HAL_GPIO_ReadPin(GPIOB, CHARGE_SENSE_PIN_B3) == GPIO_PIN_SET);
            is_charging = (v_high || p_chrg || p_vbus);
        }

        bool touch_raw = (HAL_GPIO_ReadPin(GPIOB, TOUCH_PIN) == GPIO_PIN_SET);
        if (touch_raw != touch_raw_prev) {
            touch_raw_prev = touch_raw;
            touch_change_time = now;
        }
        if ((now - touch_change_time) >= 30) {
            if (touch_raw != touch_stable) {
                touch_stable = touch_raw;
                if (touch_stable) {
                    touch_press_start = now;
                    is_holding = false;
                } else {
                    uint32_t dur = now - touch_press_start;
                    if (dur < 350 && !is_holding) {
                        lamp_on = !lamp_on;
                        if (lamp_on) {
                            target_brightness = saved_brightness;
                            lamp_on_timestamp = now;
                        } else {
                            target_brightness = 0;
                        }
                    } else if (is_holding) {
                        dim_direction = -dim_direction;
                        saved_brightness = current_brightness;
                    }
                    is_holding = false;
                }
            }
        }

        if (touch_stable && (now - touch_press_start >= 350)) {
            is_holding = true;
            lamp_on = true;
            lamp_on_timestamp = now;
            if (now - last_dim_tick >= 25) {
                last_dim_tick = now;
                int16_t nb = (int16_t)target_brightness + dim_direction;
                if (nb > 100) { nb = 100; dim_direction = -1; }
                else if (nb < 5) { nb = 5; dim_direction = 1; }
                target_brightness = (uint8_t)nb;
                current_brightness = target_brightness;
                saved_brightness = target_brightness;
                pwm_duty = gyver_gamma2(current_brightness);
                show_brightness_until = now + 2000;
            }
        }

        if (!is_holding && (now - last_fade_tick >= 5)) {
            last_fade_tick = now;
            if (current_brightness < target_brightness) {
                current_brightness++;
                pwm_duty = gyver_gamma2(current_brightness);
            } else if (current_brightness > target_brightness) {
                current_brightness--;
                pwm_duty = gyver_gamma2(current_brightness);
            }
        }

        if (lamp_on && !is_holding) {
            uint32_t at = now - lamp_on_timestamp;
            if (at >= (16UL * 60UL * 1000UL)) {
                lamp_on = false;
                target_brightness = 0;
            } else if (at >= (15UL * 60UL * 1000UL)) {
                uint32_t fp = at - (15UL * 60UL * 1000UL);
                target_brightness = (uint8_t)((uint32_t)saved_brightness * (60000UL - fp) / 60000UL);
            }
        }

        uint8_t disp_val = bat_percent;
        uint8_t bars = 1;
        uint8_t icons = FH8016_ICON_PERCENT;
        fh8016_color_t eye_l = FH8016_COLOR_GREEN;
        fh8016_color_t eye_r = FH8016_COLOR_GREEN;

        if (now < show_brightness_until) {
            disp_val = current_brightness;
            icons = FH8016_ICON_PERCENT;
            bars = (current_brightness * 4U + 50U) / 100U;
            if (bars < 1) bars = 1;
            if (bars > 4) bars = 4;
            eye_l = eye_r = FH8016_COLOR_CYAN;
        } else {
            disp_val = bat_percent;
            if (is_charging) {
                icons |= FH8016_ICON_LIGHTNING;
                bars = ((now / 350) % 4) + 1;
                eye_l = eye_r = (bat_percent >= 100) ? FH8016_COLOR_BLUE : FH8016_COLOR_CYAN;
            } else {
                if (bat_percent >= 75) bars = 4;
                else if (bat_percent >= 50) bars = 3;
                else if (bat_percent >= 25) bars = 2;
                else bars = 1;

                if (bat_percent >= 60) eye_l = eye_r = FH8016_COLOR_GREEN;
                else if (bat_percent >= 25) eye_l = eye_r = FH8016_COLOR_YELLOW;
                else eye_l = eye_r = FH8016_COLOR_RED;
            }
        }

        fh8016_set_state(&disp, disp_val, bars, icons, eye_l, eye_r);
        fh8016_update(&disp);
        HAL_Delay(35);
    }
}
"""

with open('custom_firmware/main.c', 'w', encoding='utf-8') as f:
    f.write(content)
with open('custom_firmware/book_light.c', 'w', encoding='utf-8') as f:
    f.write('// Merged into main.c\n')
print('DONE!')
