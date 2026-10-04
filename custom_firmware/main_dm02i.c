// SPDX-License-Identifier: BSD-3-Clause
/**
 * @file    main_dm02i.c
 * @brief   Complete Autonomous Firmware Demo for Vape Board DM02i V03 (2428)
 *          MCU: Puya PY32C642 / PY32F002BW15 (ARM Cortex-M0+ @ 24MHz)
 * 
 * Features demonstrated:
 *  - 24/7 immortal SWD debugging (DBGMCU active)
 *  - 30-segment Charlieplexing LED Display engine (crisp flicker-free multiplexing in SysTick)
 *  - VREFINT internal ADC battery voltage measurement (no external dividers)
 *  - Bootup splash sequence & smooth charging/puff animations
 *  - Independent control of drop center and animated droplet rim
 *  - Full screen blanking when powered down
 */

#include "py32f0xx.h"
#include "py32f002b_hal.h"
#include "py32_dm02i_board.h"
#include "dm02i_display.h"
#include <stdint.h>
#include <stdbool.h>

/* Shared memory structure for optional real-time SWD telemetry and tuning */
typedef struct {
    uint32_t magic;          // 0x444D3032 ("DM02")
    uint32_t vdd_mv;         // Battery voltage in mV
    uint32_t batt_pct;       // Battery level 0..100%
    uint32_t liquid_bars;    // Liquid level 0..3
    uint32_t drop_center;    // 0 = off, 1 = on
    uint32_t rim_mode;       // 0 = off, 1 = static, 2 = rotate_cw, 3 = rotate_ccw
    uint32_t boost_mode;     // 0 = off, 1 = static, 2 = blink, 3 = turbo_spin
    uint32_t lightning;      // 0 = off, 1 = solid, 2 = blink
    uint32_t demo_mode;      // 1 = running autonomous demo, 0 = manual SWD
} dm02i_telemetry_t;

volatile dm02i_telemetry_t g_telemetry;


/**
 * @brief Красивая вступительная анимация при подаче питания / пробуждении
 */
static void run_boot_sequence(void) {
    dm02i_clear();

    /* 1. Тест всех сегментов: короткая вспышка на 350 мс */
    dm02i_all_on();
    HAL_Delay(350);
    dm02i_clear();
    HAL_Delay(100);

    /* 2. Последовательное заполнение полосок бака */
    dm02i_set_liquid(1);
    HAL_Delay(120);
    dm02i_set_liquid(2);
    HAL_Delay(120);
    dm02i_set_liquid(3);
    HAL_Delay(150);

    /* 3. Зажигание капли и запуск вращения ободка */
    dm02i_set_drop(true);
    dm02i_set_rim(DM02I_RIM_ROTATE_CW);
    HAL_Delay(250);

    /* 4. Зажигание знака % */
    dm02i_set_percent(true);

    /* 5. Плавный отсчет процентов до реального заряда батареи */
    uint16_t vdd = dm02i_board_get_battery_mv();
    uint8_t target_pct = dm02i_board_calculate_battery_pct(vdd);
    if (target_pct > 100) target_pct = 100;

    for (int p = 0; p <= target_pct; p += 2) {
        dm02i_set_number(p);
        HAL_Delay(15);
    }
    dm02i_set_number(target_pct);
    HAL_Delay(300);
}

int main(void) {
    g_telemetry.magic = 0x444D3032;
    g_telemetry.demo_mode = 1;

    /* 1. Базовая инициализация HAL */
    HAL_Init();

    /* 2. Инициализация тактирования и периферии платы DM02i */
    dm02i_board_init();

    /* 3. Настройка SysTick на частоту 1000 Гц (1 мс) */
    HAL_SYSTICK_Config(SystemCoreClock / 1000);

    /* 4. Приветственная анимация */
    run_boot_sequence();

    /* Переменные для демо-цикла */
    uint32_t last_adc_time = 0;
    uint32_t last_anim_step = 0;
    uint8_t demo_state = 0;

    while (1) {
        uint32_t now = HAL_GetTick();

        /* Обновление телеметрии АКБ раз в 500 мс */
        if (now - last_adc_time >= 500) {
            last_adc_time = now;
            g_telemetry.vdd_mv = dm02i_board_get_battery_mv();
            g_telemetry.batt_pct = dm02i_board_calculate_battery_pct(g_telemetry.vdd_mv);
        }

        /* Если включен автономный демо-режим, циклически демонстрируем возможности */
        if (g_telemetry.demo_mode) {
            if (now - last_anim_step >= 3500) {
                last_anim_step = now;
                demo_state = (demo_state + 1) % 4;

                switch (demo_state) {
                    case 0:
                        /* Обычный режим: заряд батареи, 3 полоски, статичная капля */
                        dm02i_set_boost(DM02I_BOOST_OFF);
                        dm02i_set_lightning(false, false);
                        dm02i_set_rim(DM02I_RIM_OFF);
                        dm02i_set_drop(true);
                        dm02i_set_liquid(3);
                        dm02i_set_percent(true);
                        dm02i_set_number(g_telemetry.batt_pct);
                        break;

                    case 1:
                        /* Режим затяжки / BOOST: вращение ободка, турбо-раскрутка BOOST, уровень жидкости 2 */
                        dm02i_set_boost(DM02I_BOOST_TURBO_SPIN);
                        dm02i_set_rim(DM02I_RIM_ROTATE_CW);
                        dm02i_set_drop(true);
                        dm02i_set_liquid(2);
                        break;

                    case 2:
                        /* Режим зарядки: моргающая молния, статичный ободок, процент 88% */
                        dm02i_set_boost(DM02I_BOOST_OFF);
                        dm02i_set_lightning(true, true);
                        dm02i_set_rim(DM02I_RIM_STATIC);
                        dm02i_set_drop(true);
                        dm02i_set_liquid(1);
                        break;

                    case 3:
                        /* Режим энергосбережения / спящего экрана: полное отключение дисплея */
                        dm02i_clear();
                        break;
                }
            }
        }
    }
}
