#include "gyver_led.h"
#include "gyver_rgbmath.h"

void gled_init(gyver_led_t *l, uint16_t pwm_max) {
    l->current = 0;
    l->target = 0;
    l->tmr = 0;
    l->step_time = 0;
    l->gamma_en = true;
    l->out_max = pwm_max;
    l->pwm_val = 0;
}

void gled_set_gamma(gyver_led_t *l, bool enable) {
    l->gamma_en = enable;
}

static void update_pwm(gyver_led_t *l) {
    if (l->gamma_en) {
        // Gamma 2.2 через таблицу AlexGyver (100 шагов → 0..100)
        // current = 0..255, масштабируем до 0..100 для таблицы
        uint8_t pct = (uint8_t)((uint32_t)l->current * 100 / 255);
        uint8_t gamma_val = gyver_gamma2(pct); // 0..100
        l->pwm_val = (uint16_t)((uint32_t)gamma_val * l->out_max / 100);
        
        // Защита от полного затухания, если значение больше 0
        if (l->current > 0 && l->pwm_val == 0) {
            l->pwm_val = 1; 
        }
    } else {
        // Линейно
        l->pwm_val = (l->current * l->out_max) / 255;
    }
}

void gled_set(gyver_led_t *l, uint8_t val) {
    l->current = val;
    l->target = val;
    update_pwm(l);
}

void gled_fade(gyver_led_t *l, uint8_t target, uint32_t fade_time_ms) {
    l->target = target;
    if (l->current == l->target) {
        l->step_time = 0;
        return;
    }
    
    // Рассчитываем, сколько миллисекунд должен длиться один шаг (1/255)
    uint32_t diff = (target > l->current) ? (target - l->current) : (l->current - target);
    l->step_time = fade_time_ms / diff;
    if (l->step_time == 0) l->step_time = 1; // Защита от деления на 0
}

bool gled_tick(gyver_led_t *l, uint32_t now_ms) {
    if (l->current != l->target) {
        // Проверяем, пришло ли время сделать следующий шаг
        if (now_ms - l->tmr >= l->step_time) {
            l->tmr = now_ms;
            
            if (l->current < l->target) l->current++;
            else l->current--;
            
            update_pwm(l);
            return true;
        }
    }
    return false;
}
