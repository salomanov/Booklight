#ifndef GYVER_LED_H
#define GYVER_LED_H

#include <stdint.h>
#include <stdbool.h>

/**
 * C-порт библиотеки GyverLED для одноцветных ШИМ светодиодов.
 * Оптимизирован для слабых МК: использует только целочисленную математику,
 * не блокирует выполнение, включает гамма-коррекцию 2.0.
 */

typedef struct {
    uint8_t current;        // Текущая яркость (0-255)
    uint8_t target;         // Целевая яркость (0-255)
    uint32_t tmr;           // Таймер для фейда
    uint32_t step_time;     // Время одного шага (мс)
    bool gamma_en;          // Включена ли гамма-коррекция
    uint16_t out_max;       // Максимальный выходной ШИМ
    uint16_t pwm_val;       // Рассчитанное значение ШИМ для таймера
} gyver_led_t;

// Инициализация (pwm_max - предел вашего аппаратного таймера)
void gled_init(gyver_led_t *l, uint16_t pwm_max);

// Вкл/выкл гамма-коррекцию (по умолчанию включена)
void gled_set_gamma(gyver_led_t *l, bool enable);

// Запустить плавный переход к target (0-255) за fade_time_ms
void gled_fade(gyver_led_t *l, uint8_t target, uint32_t fade_time_ms);

// Мгновенно установить яркость (без фейда)
void gled_set(gyver_led_t *l, uint8_t val);

// Вызывать в главном цикле. Возвращает true, если значение ШИМ изменилось
bool gled_tick(gyver_led_t *l, uint32_t now_ms);

#endif /* GYVER_LED_H */
