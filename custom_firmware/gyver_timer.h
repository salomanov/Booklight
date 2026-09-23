#ifndef GYVER_TIMER_H
#define GYVER_TIMER_H

/**
 * gyver_timer — порт GyverTimer от AlexGyver для PY32F002B
 *
 * Неблокирующий интервальный таймер на millis().
 * Заменяет HAL_Delay() в логике основного цикла.
 *
 * Использование:
 *   gtimer_t fade_tmr;
 *   gtimer_set(&fade_tmr, 5);          // срабатывать каждые 5 мс
 *
 *   while (1) {
 *       uint32_t now = millis();
 *       if (gtimer_ready(&fade_tmr, now)) {
 *           // плавное изменение яркости — каждые 5 мс
 *       }
 *   }
 */

#include <stdint.h>
#include <stdbool.h>

typedef struct {
    uint32_t tmr;       // момент последнего срабатывания
    uint32_t period;    // интервал в мс
    bool     started;   // был ли первый старт
} gtimer_t;

/**
 * Установить период таймера (не запускает).
 */
static inline void gtimer_set(gtimer_t *t, uint32_t period_ms) {
    t->period  = period_ms;
    t->started = false;
    t->tmr     = 0;
}

/**
 * Проверить: прошёл ли интервал?
 * Если да — перезаряжает таймер и возвращает true.
 * Вызывать каждый цикл с текущим millis().
 */
static inline bool gtimer_ready(gtimer_t *t, uint32_t now_ms) {
    if (!t->started) {
        t->started = true;
        t->tmr = now_ms;
        return false; // первый вызов — не срабатываем сразу
    }
    if ((now_ms - t->tmr) >= t->period) {
        t->tmr = now_ms;
        return true;
    }
    return false;
}

/**
 * Срабатывает один раз по истечении периода.
 * После срабатывания не перезаряжается автоматически.
 * Для повтора — снова вызови gtimer_set().
 */
static inline bool gtimer_once(gtimer_t *t, uint32_t now_ms) {
    if (!t->started) {
        t->started = true;
        t->tmr = now_ms;
        return false;
    }
    if (t->period != 0 && (now_ms - t->tmr) >= t->period) {
        t->period = 0; // одноразовый — отключаем после срабатывания
        return true;
    }
    return false;
}

/**
 * Принудительно перезапустить таймер с текущего момента.
 */
static inline void gtimer_reset(gtimer_t *t, uint32_t now_ms) {
    t->tmr     = now_ms;
    t->started = true;
}

#endif /* GYVER_TIMER_H */
