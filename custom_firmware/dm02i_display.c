// SPDX-License-Identifier: BSD-3-Clause
/**
 * @file    dm02i_display.c
 * @brief   Implementation of DM02i V03 6-Pin Charlieplexing Display Driver
 */

#include "dm02i_display.h"
#include "py32f0xx.h"
#include "py32f002b_hal.h"

/* Definition of the 6 physical display lines */
typedef struct {
    GPIO_TypeDef *port;
    uint16_t pin;
} DisplayPin_t;

static const DisplayPin_t DISPLAY_PINS[DM02I_NUM_LINES] = {
    {GPIOB, GPIO_PIN_0}, // 0: Contact 1 (Leg 14)
    {GPIOB, GPIO_PIN_1}, // 1: Contact 2 (Leg 13)
    {GPIOB, GPIO_PIN_2}, // 2: Contact 3 (Leg 12)
    {GPIOB, GPIO_PIN_3}, // 3: Contact 4 (Leg 11)
    {GPIOB, GPIO_PIN_5}, // 4: Contact 5 (Leg 10)
    {GPIOC, GPIO_PIN_1}, // 5: Contact 6 (Leg 9)
};

/* Pair definition: High line index and Low line index (0..5) */
typedef struct {
    uint8_t high;
    uint8_t low;
} CharliePair_t;

/* Exact 30 pairs matching the hardware ground truth */
static const CharliePair_t SEG_PAIRS[DM02I_NUM_SEGMENTS] = {
    /* 💧 Капля центр */
    [DM02I_SEG_DROP_CENTER] = {0, 5}, // 1(+) -> 6(-)

    /* ⭕ Ободок капли */
    [DM02I_SEG_DROP_TOP]    = {1, 5}, // 2(+) -> 6(-)
    [DM02I_SEG_DROP_RIGHT]  = {4, 5}, // 5(+) -> 6(-)
    [DM02I_SEG_DROP_BOT]    = {3, 5}, // 4(+) -> 6(-)
    [DM02I_SEG_DROP_LEFT]   = {2, 5}, // 3(+) -> 6(-)

    /* ━━━ Полоски жидкости */
    [DM02I_SEG_BAR1]        = {5, 4}, // 6(+) -> 5(-)
    [DM02I_SEG_BAR2]        = {3, 4}, // 4(+) -> 5(-)
    [DM02I_SEG_BAR3]        = {2, 4}, // 3(+) -> 5(-)

    /* ⚡ Молния и % */
    [DM02I_SEG_LIGHTNING]   = {1, 4}, // 2(+) -> 5(-)
    [DM02I_SEG_PERCENT]     = {5, 2}, // 6(+) -> 3(-)

    /* 💯 Сотня */
    [DM02I_SEG_HUNDRED_TOP] = {5, 3}, // 6(+) -> 4(-)
    [DM02I_SEG_HUNDRED_BOT] = {0, 4}, // 1(+) -> 5(-)

    /* 🚀 BOOST */
    [DM02I_SEG_BOOST_TL]    = {0, 3}, // 1(+) -> 4(-) (B)
    [DM02I_SEG_BOOST_TR]    = {1, 3}, // 2(+) -> 4(-) (T)
    [DM02I_SEG_BOOST_BL]    = {2, 3}, // 3(+) -> 4(-) (Диод 2)
    [DM02I_SEG_BOOST_BR]    = {4, 3}, // 5(+) -> 4(-) (Диод 4)

    /* 🔟 Цифра 1 (Десятки) */
    [DM02I_SEG_D1_A]        = {1, 0}, // 2(+) -> 1(-)
    [DM02I_SEG_D1_B]        = {2, 0}, // 3(+) -> 1(-)
    [DM02I_SEG_D1_C]        = {3, 0}, // 4(+) -> 1(-)
    [DM02I_SEG_D1_D]        = {4, 0}, // 5(+) -> 1(-)
    [DM02I_SEG_D1_E]        = {5, 0}, // 6(+) -> 1(-)
    [DM02I_SEG_D1_F]        = {0, 1}, // 1(+) -> 2(-)
    [DM02I_SEG_D1_G]        = {2, 1}, // 3(+) -> 2(-)

    /* 🔢 Цифра 2 (Единицы) */
    [DM02I_SEG_D2_A]        = {3, 1}, // 4(+) -> 2(-)
    [DM02I_SEG_D2_B]        = {4, 1}, // 5(+) -> 2(-)
    [DM02I_SEG_D2_C]        = {5, 1}, // 6(+) -> 2(-)
    [DM02I_SEG_D2_D]        = {0, 2}, // 1(+) -> 3(-)
    [DM02I_SEG_D2_E]        = {1, 2}, // 2(+) -> 3(-)
    [DM02I_SEG_D2_F]        = {3, 2}, // 4(+) -> 3(-)
    [DM02I_SEG_D2_G]        = {4, 2}, // 5(+) -> 3(-)
};

/* 7-сегментный шрифт (биты: 0=A, 1=B, 2=C, 3=D, 4=E, 5=F, 6=G) */
static const uint8_t FONT_7SEG_BITS[10] = {
    0x3F, // 0: A B C D E F
    0x06, // 1: B C
    0x5B, // 2: A B D E G
    0x4F, // 3: A B C D G
    0x66, // 4: B C F G
    0x6D, // 5: A C D F G
    0x7D, // 6: A C D E F G
    0x07, // 7: A B C
    0x7F, // 8: A B C D E F G
    0x6F, // 9: A B C D F G
};

/* Display State Buffer */
static volatile uint32_t s_active_mask = 0; // Битовая маска 30 активных сегментов
static volatile uint8_t  s_active_pairs_count = 0;
static volatile uint8_t  s_active_pairs_list[DM02I_NUM_SEGMENTS];

/* Animation states */
static dm02i_rim_mode_t   s_rim_mode   = DM02I_RIM_OFF;
static dm02i_boost_mode_t s_boost_mode = DM02I_BOOST_OFF;
static bool               s_drop_on    = false;
static bool               s_ln_on      = false;
static bool               s_ln_blink   = false;
static int16_t            s_number     = -1;
static bool               s_percent_on = false;
static uint8_t            s_liquid_lvl = 0;

/* Internal millisecond animation counters */
static uint32_t s_ms_counter = 0;
static uint8_t  s_rim_anim_idx = 0;
static uint8_t  s_boost_anim_idx = 0;
static bool     s_blink_state_500ms = true;

/* Helper: Перевести все 6 линий в High-Z (высокоимпедансный вход) */
static inline void lines_all_high_z(void) {
    GPIO_InitTypeDef GPIO_InitStruct = {0};
    GPIO_InitStruct.Mode = GPIO_MODE_ANALOG; // Analog = High-Z (no pull, zero leakage)
    GPIO_InitStruct.Pull = GPIO_NOPULL;

    /* GPIOB lines (PB0, PB1, PB2, PB3, PB5) - SWDIO PB6 MUST NOT BE TOUCHED */
    GPIO_InitStruct.Pin = GPIO_PIN_0 | GPIO_PIN_1 | GPIO_PIN_2 | GPIO_PIN_3 | GPIO_PIN_5;
    HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

    /* GPIOC line (PC1) - NRST PC0 MUST NOT BE TOUCHED */
    GPIO_InitStruct.Pin = GPIO_PIN_1;
    HAL_GPIO_Init(GPIOC, &GPIO_InitStruct);
}

/* Helper: Аппаратная подача потенциалов на пару (High и Low) */
static inline void set_charlie_pair(uint8_t h_idx, uint8_t l_idx) {
    lines_all_high_z();

    if (h_idx == l_idx || h_idx >= DM02I_NUM_LINES || l_idx >= DM02I_NUM_LINES) return;

    GPIO_InitTypeDef GPIO_InitStruct = {0};
    GPIO_InitStruct.Mode  = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull  = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_HIGH;

    /* 1. Low pin (0V, sink) */
    HAL_GPIO_WritePin(DISPLAY_PINS[l_idx].port, DISPLAY_PINS[l_idx].pin, GPIO_PIN_RESET);
    GPIO_InitStruct.Pin = DISPLAY_PINS[l_idx].pin;
    HAL_GPIO_Init(DISPLAY_PINS[l_idx].port, &GPIO_InitStruct);

    /* 2. High pin (3.3V, source) */
    HAL_GPIO_WritePin(DISPLAY_PINS[h_idx].port, DISPLAY_PINS[h_idx].pin, GPIO_PIN_SET);
    GPIO_InitStruct.Pin = DISPLAY_PINS[h_idx].pin;
    HAL_GPIO_Init(DISPLAY_PINS[h_idx].port, &GPIO_InitStruct);
}

/* Внутренняя функция пересчёта списка активных пар из состояний */
static void rebuild_active_mask(void) {
    uint32_t mask = 0;

    /* 1. Цифры и Сотня */
    if (s_number >= 0) {
        if (s_percent_on) {
            mask |= (1UL << DM02I_SEG_PERCENT);
        }

        if (s_number >= 100) {
            mask |= (1UL << DM02I_SEG_HUNDRED_TOP);
            mask |= (1UL << DM02I_SEG_HUNDRED_BOT);
            uint8_t f0 = FONT_7SEG_BITS[0];
            for (int b = 0; b < 7; b++) {
                if (f0 & (1 << b)) {
                    mask |= (1UL << (DM02I_SEG_D1_A + b));
                    mask |= (1UL << (DM02I_SEG_D2_A + b));
                }
            }
        } else {
            uint8_t d1 = s_number / 10;
            uint8_t d2 = s_number % 10;
            if (s_number >= 10) {
                uint8_t f1 = FONT_7SEG_BITS[d1];
                for (int b = 0; b < 7; b++) {
                    if (f1 & (1 << b)) mask |= (1UL << (DM02I_SEG_D1_A + b));
                }
            }
            uint8_t f2 = FONT_7SEG_BITS[d2];
            for (int b = 0; b < 7; b++) {
                if (f2 & (1 << b)) mask |= (1UL << (DM02I_SEG_D2_A + b));
            }
        }
    }

    /* 2. Полоски жидкости */
    if (s_liquid_lvl >= 1) mask |= (1UL << DM02I_SEG_BAR1);
    if (s_liquid_lvl >= 2) mask |= (1UL << DM02I_SEG_BAR2);
    if (s_liquid_lvl >= 3) mask |= (1UL << DM02I_SEG_BAR3);

    /* 3. Капля 💧 (Центр) */
    if (s_drop_on) {
        mask |= (1UL << DM02I_SEG_DROP_CENTER);
    }

    /* 4. Ободок капли ⭕ */
    if (s_rim_mode == DM02I_RIM_STATIC) {
        mask |= (1UL << DM02I_SEG_DROP_TOP);
        mask |= (1UL << DM02I_SEG_DROP_RIGHT);
        mask |= (1UL << DM02I_SEG_DROP_BOT);
        mask |= (1UL << DM02I_SEG_DROP_LEFT);
    } else if (s_rim_mode == DM02I_RIM_ROTATE_CW || s_rim_mode == DM02I_RIM_ROTATE_CCW) {
        dm02i_segment_t rim_order[4] = {
            DM02I_SEG_DROP_TOP, DM02I_SEG_DROP_RIGHT, DM02I_SEG_DROP_BOT, DM02I_SEG_DROP_LEFT
        };
        uint8_t idx = (s_rim_mode == DM02I_RIM_ROTATE_CW) ? s_rim_anim_idx : ((4 - s_rim_anim_idx) % 4);
        mask |= (1UL << rim_order[idx]);
    }

    /* 5. Молния ⚡ */
    if (s_ln_on) {
        if (!s_ln_blink || s_blink_state_500ms) {
            mask |= (1UL << DM02I_SEG_LIGHTNING);
        }
    }

    /* 6. BOOST 🚀 */
    if (s_boost_mode == DM02I_BOOST_STATIC) {
        mask |= (1UL << DM02I_SEG_BOOST_TL);
        mask |= (1UL << DM02I_SEG_BOOST_TR);
        mask |= (1UL << DM02I_SEG_BOOST_BL);
        mask |= (1UL << DM02I_SEG_BOOST_BR);
    } else if (s_boost_mode == DM02I_BOOST_BLINK) {
        if (s_blink_state_500ms) {
            mask |= (1UL << DM02I_SEG_BOOST_TL);
            mask |= (1UL << DM02I_SEG_BOOST_TR);
            mask |= (1UL << DM02I_SEG_BOOST_BL);
            mask |= (1UL << DM02I_SEG_BOOST_BR);
        }
    } else if (s_boost_mode == DM02I_BOOST_TURBO_SPIN) {
        dm02i_segment_t boost_quads[4] = {
            DM02I_SEG_BOOST_TL, DM02I_SEG_BOOST_TR, DM02I_SEG_BOOST_BR, DM02I_SEG_BOOST_BL
        };
        mask |= (1UL << boost_quads[s_boost_anim_idx]);
    }

    /* Сохраняем компактный список активных сегментов для быстрого рендера */
    uint8_t count = 0;
    for (int i = 0; i < DM02I_NUM_SEGMENTS; i++) {
        if (mask & (1UL << i)) {
            s_active_pairs_list[count++] = (uint8_t)i;
        }
    }
    s_active_mask = mask;
    s_active_pairs_count = count;
}

/* ========================================================================= */
/*                              API ФУНКЦИИ                                  */
/* ========================================================================= */

void dm02i_init(void) {
    /* 1. Включение тактирования портов B и C */
    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_GPIOC_CLK_ENABLE();

    /* 2. Все линии в безопасный High-Z */
    lines_all_high_z();

    /* 3. Очистка буфера */
    dm02i_clear();
}

void dm02i_clear(void) {
    s_number     = -1;
    s_percent_on = false;
    s_liquid_lvl = 0;
    s_drop_on    = false;
    s_rim_mode   = DM02I_RIM_OFF;
    s_ln_on      = false;
    s_ln_blink   = false;
    s_boost_mode = DM02I_BOOST_OFF;

    s_active_mask = 0;
    s_active_pairs_count = 0;
    lines_all_high_z();
}

void dm02i_all_on(void) {
    uint8_t count = 0;
    for (int i = 0; i < DM02I_NUM_SEGMENTS; i++) {
        s_active_pairs_list[count++] = (uint8_t)i;
    }
    s_active_mask = 0x3FFFFFFF;
    s_active_pairs_count = count;
}

void dm02i_set_number(int16_t number) {
    s_number = number;
    rebuild_active_mask();
}

void dm02i_set_percent(bool enable) {
    s_percent_on = enable;
    rebuild_active_mask();
}

void dm02i_set_liquid(uint8_t level) {
    s_liquid_lvl = (level > 3) ? 3 : level;
    rebuild_active_mask();
}

void dm02i_set_drop(bool enable) {
    s_drop_on = enable;
    rebuild_active_mask();
}

void dm02i_set_rim(dm02i_rim_mode_t mode) {
    s_rim_mode = mode;
    rebuild_active_mask();
}

void dm02i_set_lightning(bool enable, bool blink) {
    s_ln_on = enable;
    s_ln_blink = blink;
    rebuild_active_mask();
}

void dm02i_set_boost(dm02i_boost_mode_t mode) {
    s_boost_mode = mode;
    rebuild_active_mask();
}

void dm02i_set_raw_segment(dm02i_segment_t seg, bool state) {
    if (seg >= DM02I_NUM_SEGMENTS) return;
    if (state) {
        s_active_mask |= (1UL << seg);
    } else {
        s_active_mask &= ~(1UL << seg);
    }
    uint8_t count = 0;
    for (int i = 0; i < DM02I_NUM_SEGMENTS; i++) {
        if (s_active_mask & (1UL << i)) {
            s_active_pairs_list[count++] = (uint8_t)i;
        }
    }
    s_active_pairs_count = count;
}

void dm02i_tick_1ms(void) {
    s_ms_counter++;

    /* Анимация ободка капли (шаг каждые 120 мс) */
    if (s_ms_counter % 120 == 0) {
        s_rim_anim_idx = (s_rim_anim_idx + 1) % 4;
        if (s_rim_mode == DM02I_RIM_ROTATE_CW || s_rim_mode == DM02I_RIM_ROTATE_CCW) {
            rebuild_active_mask();
        }
    }

    /* Анимация турбо-раскрутки BOOST (шаг каждые 70 мс) */
    if (s_ms_counter % 70 == 0) {
        s_boost_anim_idx = (s_boost_anim_idx + 1) % 4;
        if (s_boost_mode == DM02I_BOOST_TURBO_SPIN) {
            rebuild_active_mask();
        }
    }

    /* Моргание 1 Гц (период 500 мс) для зарядки и буста */
    if (s_ms_counter % 500 == 0) {
        s_blink_state_500ms = !s_blink_state_500ms;
        if ((s_ln_on && s_ln_blink) || (s_boost_mode == DM02I_BOOST_BLINK)) {
            rebuild_active_mask();
        }
    }
}

void dm02i_render_step(void) {
    static uint8_t s_cur_step = 0;

    uint8_t total = s_active_pairs_count;
    if (total == 0) {
        lines_all_high_z();
        return;
    }

    if (s_cur_step >= total) {
        s_cur_step = 0;
    }

    uint8_t seg_id = s_active_pairs_list[s_cur_step];
    CharliePair_t p = SEG_PAIRS[seg_id];

    /* Зажигаем текущий сегмент */
    set_charlie_pair(p.high, p.low);

    s_cur_step++;
}
