// SPDX-License-Identifier: BSD-3-Clause
/**
 * @file    py32_dm02i_board.h
 * @brief   Board Support Package (BSP) for Vape Board DM02i V03 (2428)
 *          MCU: Puya PY32C642 / PY32F002BW15 (QFN-16)
 */

#ifndef PY32_DM02I_BOARD_H
#define PY32_DM02I_BOARD_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Позиции 3-позиционного переключателя BOOST
 */
typedef enum {
    DM02I_SWITCH_OFF = 0,
    DM02I_SWITCH_NORMAL,
    DM02I_SWITCH_BOOST
} dm02i_switch_pos_t;

/**
 * @brief Полная аппаратная инициализация платы DM02i
 *        - Системная частота 24 МГц (HSI)
 *        - Бессмертный режим отладки SWD (DBGMCU)
 *        - АЦП VREFINT для измерения напряжения АКБ
 *        - Дисплей Charlieplexing
 */
void dm02i_board_init(void);

/**
 * @brief Измерение напряжения аккумулятора в милливольтах (мВ)
 *        Использует внутренний источник опорного напряжения VREFINT (1.20 В)
 *        без необходимости внешних делителей. Точность: +/- 15 мВ.
 * @return Напряжение VDD/BAT в мВ (например, 4180 для 4.18V)
 */
uint16_t dm02i_board_get_battery_mv(void);

/**
 * @brief Расчет процента заряда аккумулятора (0 .. 100%) по кривой Li-Ion (3.30V - 4.20V)
 * @param vdd_mv Напряжение в мВ
 * @return Процент заряда 0 .. 100%
 */
uint8_t dm02i_board_calculate_battery_pct(uint16_t vdd_mv);

/**
 * @brief Чтение положения переключателя BOOST платы
 */
dm02i_switch_pos_t dm02i_board_get_switch_pos(void);

/**
 * @brief Проверка датчика затяжки (микрофона)
 * @return true если пользователь совершает затяжку
 */
bool dm02i_board_is_puffing(void);

/**
 * @brief Безопасный переход в режим глубокого сна (STOP) с пробуждением по затяжке
 */
void dm02i_board_enter_sleep(void);

#ifdef __cplusplus
}
#endif

#endif // PY32_DM02I_BOARD_H
