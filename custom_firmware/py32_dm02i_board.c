// SPDX-License-Identifier: BSD-3-Clause
/**
 * @file    py32_dm02i_board.c
 * @brief   Board Support Package Implementation for DM02i V03 Vape Board
 */

#include "py32_dm02i_board.h"
#include "dm02i_display.h"
#include "py32f0xx.h"
#include "py32f002b_hal.h"
#include "py32f002b_hal_adc.h"

static ADC_HandleTypeDef s_hadc;

static void board_adc_init(void) {
    __HAL_RCC_ADC_CLK_ENABLE();
    s_hadc.Instance                   = ADC1;
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

    HAL_ADCEx_Calibration_Start(&s_hadc);
}

void dm02i_board_init(void) {
    /* 1. Бессмертный режим отладки SWD 24/7: DBGMCU всегда активен, таймеры замораживаются при паузе */
    RCC->APBENR1 |= RCC_APBENR1_DBGEN;
    DBGMCU->CR |= DBGMCU_CR_DBG_STOP;
    DBGMCU->APBFZ1 |= 0xFFFFFFFF;

    /* 2. Тактирование портов GPIOA, GPIOB, GPIOC */
    RCC->IOPENR |= RCC_IOPENR_GPIOAEN | RCC_IOPENR_GPIOBEN | RCC_IOPENR_GPIOCEN;
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_GPIOC_CLK_ENABLE();

    /* 3. АЦП для измерения батареи */
    board_adc_init();

    /* 4. Дисплей */
    dm02i_init();
}

uint16_t dm02i_board_get_battery_mv(void) {
    HAL_ADC_Start(&s_hadc);
    if (HAL_ADC_PollForConversion(&s_hadc, 10) == HAL_OK) {
        uint32_t raw = HAL_ADC_GetValue(&s_hadc);
        if (raw > 0) {
            /* VDD = (VREFINT_CAL_mV * 4095) / RAW */
            /* На чипах Puya VREFINT номинально равен 1200 мВ */
            uint32_t mv = (1200UL * 4095UL) / raw;
            return (uint16_t)mv;
        }
    }
    return 3300;
}

uint8_t dm02i_board_calculate_battery_pct(uint16_t vdd_mv) {
    /* Кривая 1S Li-Ion: 3.30V = 0%, 4.20V = 100% */
    if (vdd_mv <= 3300) return 0;
    if (vdd_mv >= 4200) return 100;

    /* Кусочно-линейная аппроксимация для точного процента */
    if (vdd_mv < 3600) {
        // 3.30V - 3.60V: 0% .. 10%
        return (uint8_t)((vdd_mv - 3300) * 10 / 300);
    } else if (vdd_mv < 3800) {
        // 3.60V - 3.80V: 10% .. 50%
        return (uint8_t)(10 + (vdd_mv - 3600) * 40 / 200);
    } else if (vdd_mv < 4000) {
        // 3.80V - 4.00V: 50% .. 85%
        return (uint8_t)(50 + (vdd_mv - 3800) * 35 / 200);
    } else {
        // 4.00V - 4.20V: 85% .. 100%
        return (uint8_t)(85 + (vdd_mv - 4000) * 15 / 200);
    }
}

dm02i_switch_pos_t dm02i_board_get_switch_pos(void) {
    /* Считывание положений переключателя (по умолчанию NORMAL) */
    return DM02I_SWITCH_NORMAL;
}

bool dm02i_board_is_puffing(void) {
    /* Считывание датчика затяжки */
    return false;
}

void dm02i_board_enter_sleep(void) {
    /* Гасим дисплей */
    dm02i_clear();

    /* Перевод в режим Stop с пробуждением по EXTI */
    HAL_PWR_EnterSTOPMode(PWR_LOWPOWERREGULATOR_ON, PWR_STOPENTRY_WFI);
}
