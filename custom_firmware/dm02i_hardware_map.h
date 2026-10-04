// SPDX-License-Identifier: BSD-3-Clause
/**
 * @file    dm02i_hardware_map.h
 * @brief   Complete 30-element Charlieplexing Matrix for DM02i V03 (2428)
 *          Mapped via physical multimeter diode test by User.
 *
 * Physical Pinout (QFN-16 contiguous Port B block):
 *  - Display Contact 1 <-> MCU Leg 14 (PB0)
 *  - Display Contact 2 <-> MCU Leg 13 (PB1)
 *  - Display Contact 3 <-> MCU Leg 12 (PB2)
 *  - Display Contact 4 <-> MCU Leg 11 (PB3)
 *  - Display Contact 5 <-> MCU Leg 10 (PB4 / PB5)
 *  - Display Contact 6 <-> MCU Leg 9  (PB5 / PB4)
 *
 * Total directed pairs for 6 lines = 6 * (6 - 1) = 30 LED channels.
 */

#ifndef DM02I_HARDWARE_MAP_H
#define DM02I_HARDWARE_MAP_H

#include <stdint.h>

typedef struct {
    const char *name;
    const char *id;
    uint8_t plus_contact;   // 1 .. 6
    uint8_t minus_contact;  // 1 .. 6
} HardwareMap_t;

static const HardwareMap_t DM02I_HARDWARE_MAP[] = {
    /* --- 💧 КАПЛЯ ЖИДКОСТИ (5 СЕГМЕНТОВ) --- */
    {"💧 Капля: Центр",             "drop_center",   1, 6},
    {"💧 Капля: Верх ободка",       "drop_top",      2, 6},
    {"💧 Капля: Лево ободка",       "drop_left",     3, 6},
    {"💧 Капля: Низ",               "drop_bot",      4, 6},
    {"💧 Капля: Право ободка",      "drop_right",    5, 6},

    /* --- ЛИНИЯ КОНТАКТА 6 (+) --- */
    {"Цифра 1 (Десятки) - Сег E",   "d1_e",          6, 1},
    {"Цифра 2 (Единицы) - Сег C",   "d2_c",          6, 2},
    {"% (Знак процента)",           "percent",       6, 3},
    {"Сотня '1' (Верхняя палочка)", "hundred_top",   6, 4},
    {"Полоска жидкости 1 (Нижняя)", "bar1",          6, 5},

    /* --- ПОЛОСКИ ЖИДКОСТИ И ЗАРЯД --- */
    {"⚡ Молния (Индикатор заряда)", "lightning",     2, 5},
    {"Полоска жидкости 3 (Верхняя)","bar3",          3, 5},
    {"Полоска жидкости 2 (Средняя)","bar2",          4, 5},
    {"Сотня '1' (Нижняя палочка)",  "hundred_bot",   1, 5},

    /* --- 🚀 ИНДИКАТОР BOOST (4 КВАДРАНТА) --- */
    {"BOOST: Верх-Лево (Буква B)",   "boost_tl",      1, 4},
    {"BOOST: Верх-Право (Буква T)",  "boost_tr",      2, 4},
    {"BOOST: Низ-Лево (Диод 2)",     "boost_bl",      3, 4},
    {"BOOST: Низ-Право (Диод 4)",    "boost_br",      4, 5}, // или 5->4

    /* --- 🔟 ЦИФРА 1 (ДЕСЯТКИ: A, B, C, D, F, G) --- */
    {"Цифра 1 - Сегмент A",          "d1_a",          2, 1},
    {"Цифра 1 - Сегмент B",          "d1_b",          3, 1},
    {"Цифра 1 - Сегмент C",          "d1_c",          4, 1},
    {"Цифра 1 - Сегмент D",          "d1_d",          5, 1},
    {"Цифра 1 - Сегмент F",          "d1_f",          1, 2},
    {"Цифра 1 - Сегмент G",          "d1_g",          3, 2},

    /* --- 🔢 ЦИФРА 2 (ЕДИНИЦЫ: A, B, D, E, F, G) --- */
    {"Цифра 2 - Сегмент A",          "d2_a",          4, 2},
    {"Цифра 2 - Сегмент B",          "d2_b",          5, 2},
    {"Цифра 2 - Сегмент D",          "d2_d",          1, 3},
    {"Цифра 2 - Сегмент E",          "d2_e",          2, 3},
    {"Цифра 2 - Сегмент F",          "d2_f",          4, 3},
    {"Цифра 2 - Сегмент G",          "d2_g",          5, 3},
};

#define DM02I_TOTAL_SEGMENTS (sizeof(DM02I_HARDWARE_MAP) / sizeof(DM02I_HARDWARE_MAP[0]))

#endif // DM02I_HARDWARE_MAP_H
