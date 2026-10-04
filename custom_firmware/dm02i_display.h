// SPDX-License-Identifier: BSD-3-Clause
/**
 * @file    dm02i_display.h
 * @brief   Complete Production C Driver for DM02i V03 6-Pin Charlieplexing Display
 *          Target MCU: Puya PY32C642 / PY32F002BW15 (QFN-16) or any ARM Cortex-M
 *
 * Physical Pinout (Contiguous Port B + Port C):
 *   Contact 1 <-> PB0 (MCU Leg 14)
 *   Contact 2 <-> PB1 (MCU Leg 13)
 *   Contact 3 <-> PB2 (MCU Leg 12)
 *   Contact 4 <-> PB3 (MCU Leg 11)
 *   Contact 5 <-> PB5 (MCU Leg 10)
 *   Contact 6 <-> PC1 (MCU Leg 9)
 *
 * Total directed pairs for 6 lines = 6 * (6 - 1) = 30 LED channels.
 */

#ifndef DM02I_DISPLAY_H
#define DM02I_DISPLAY_H

#include <stdint.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Total segments in the display matrix */
#define DM02I_NUM_SEGMENTS 30
#define DM02I_NUM_LINES    6

/**
 * Segment ID enumeration (0 .. 29)
 */
typedef enum {
    /* 💧 Капля жидкости (Центр) */
    DM02I_SEG_DROP_CENTER = 0,   // 1(+) -> 6(-)

    /* ⭕ Ободок капли (4 сегмента) */
    DM02I_SEG_DROP_TOP,          // 2(+) -> 6(-)
    DM02I_SEG_DROP_RIGHT,        // 5(+) -> 6(-)
    DM02I_SEG_DROP_BOT,          // 4(+) -> 6(-)
    DM02I_SEG_DROP_LEFT,         // 3(+) -> 6(-)

    /* ━━━ Полоски жидкости */
    DM02I_SEG_BAR1,              // 6(+) -> 5(-) (Нижняя)
    DM02I_SEG_BAR2,              // 4(+) -> 5(-) (Средняя)
    DM02I_SEG_BAR3,              // 3(+) -> 5(-) (Верхняя)

    /* ⚡ Молния и % */
    DM02I_SEG_LIGHTNING,         // 2(+) -> 5(-)
    DM02I_SEG_PERCENT,           // 6(+) -> 3(-)

    /* 💯 Сотня (Палочки "1") */
    DM02I_SEG_HUNDRED_TOP,       // 6(+) -> 4(-)
    DM02I_SEG_HUNDRED_BOT,       // 1(+) -> 5(-)

    /* 🚀 BOOST (4 квадранта) */
    DM02I_SEG_BOOST_TL,          // 1(+) -> 4(-) (Буква B)
    DM02I_SEG_BOOST_TR,          // 2(+) -> 4(-) (Буква T)
    DM02I_SEG_BOOST_BL,          // 3(+) -> 4(-) (Диод 2)
    DM02I_SEG_BOOST_BR,          // 5(+) -> 4(-) (Диод 4)

    /* 🔟 Цифра 1 (Десятки: 7 сегментов) */
    DM02I_SEG_D1_A,              // 2(+) -> 1(-)
    DM02I_SEG_D1_B,              // 3(+) -> 1(-)
    DM02I_SEG_D1_C,              // 4(+) -> 1(-)
    DM02I_SEG_D1_D,              // 5(+) -> 1(-)
    DM02I_SEG_D1_E,              // 6(+) -> 1(-)
    DM02I_SEG_D1_F,              // 1(+) -> 2(-)
    DM02I_SEG_D1_G,              // 3(+) -> 2(-)

    /* 🔢 Цифра 2 (Единицы: 7 сегментов) */
    DM02I_SEG_D2_A,              // 4(+) -> 2(-)
    DM02I_SEG_D2_B,              // 5(+) -> 2(-)
    DM02I_SEG_D2_C,              // 6(+) -> 2(-)
    DM02I_SEG_D2_D,              // 1(+) -> 3(-)
    DM02I_SEG_D2_E,              // 2(+) -> 3(-)
    DM02I_SEG_D2_F,              // 4(+) -> 3(-)
    DM02I_SEG_D2_G,              // 5(+) -> 3(-)

    DM02I_SEG_MAX
} dm02i_segment_t;

/**
 * Режимы работы обводки капли ⭕
 */
typedef enum {
    DM02I_RIM_OFF = 0,           // Ободок выключен
    DM02I_RIM_STATIC,            // Горят все 4 сегмента ободка
    DM02I_RIM_ROTATE_CW,         // Вращение бегущего огонька по часовой стрелке
    DM02I_RIM_ROTATE_CCW         // Вращение против часовой стрелки
} dm02i_rim_mode_t;

/**
 * Режимы работы индикатора BOOST 🚀
 */
typedef enum {
    DM02I_BOOST_OFF = 0,         // Выключен
    DM02I_BOOST_STATIC,          // Горят все 4 квадранта
    DM02I_BOOST_BLINK,           // Моргание всеми сегментами
    DM02I_BOOST_TURBO_SPIN       // Турбо-раскрутка по квадрантам
} dm02i_boost_mode_t;

/* ========================================================================= */
/*                              API ФУНКЦИИ                                  */
/* ========================================================================= */

/**
 * @brief Инициализация GPIO линий и таймера дисплея DM02i
 */
void dm02i_init(void);

/**
 * @brief Полная очистка дисплея (погасить все сегменты)
 */
void dm02i_clear(void);

/**
 * @brief Зажечь все 30 сегментов экрана одновременно (тест матрицы)
 */
void dm02i_all_on(void);

/**
 * @brief Установка числа на дисплее
 * @param number Число от 0 до 100. Если < 0, цифры гаснут.
 *               При 100 автоматически зажигаются палочки сотни и "00".
 */
void dm02i_set_number(int16_t number);

/**
 * @brief Включение/выключение знака процента '%'
 */
void dm02i_set_percent(bool enable);

/**
 * @brief Установка делений полосок жидкости
 * @param level 0 = пусто, 1 = нижняя, 2 = нижняя+средняя, 3 = все три
 */
void dm02i_set_liquid(uint8_t level);

/**
 * @brief Управление центральной каплей 💧 (строго независимо от ободка)
 * @param enable true = горит, false = выключена
 */
void dm02i_set_drop(bool enable);

/**
 * @brief Управление обводкой (ободком) капли ⭕
 * @param mode DM02I_RIM_OFF, DM02I_RIM_STATIC, DM02I_RIM_ROTATE_CW
 */
void dm02i_set_rim(dm02i_rim_mode_t mode);

/**
 * @brief Управление индикатором зарядки (Молния ⚡)
 * @param enable true = включена
 * @param blink  true = мигание (режим процесса зарядки)
 */
void dm02i_set_lightning(bool enable, bool blink);

/**
 * @brief Управление индикатором BOOST 🚀
 * @param mode Режим (выкл / горит / мигает / турбо-раскрутка)
 */
void dm02i_set_boost(dm02i_boost_mode_t mode);

/**
 * @brief Прямое включение/выключение отдельного сегмента по ID
 */
void dm02i_set_raw_segment(dm02i_segment_t seg, bool state);

/**
 * @brief Вызывается в таймере анимации раз в 1 мс (SysTick_Handler)
 *        Обновляет кадры бегущих огоньков и мигания
 */
void dm02i_tick_1ms(void);

/**
 * @brief Быстрый шаг мультиплексинга (вызывается с частотой ~1 .. 3 кГц)
 *        Зажигает следующий активный сегмент и переключает High-Z
 */
void dm02i_render_step(void);

#ifdef __cplusplus
}
#endif

#endif // DM02I_DISPLAY_H
