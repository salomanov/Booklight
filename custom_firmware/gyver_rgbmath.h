#ifndef GYVER_RGBMATH_H
#define GYVER_RGBMATH_H

#include <stdint.h>
#include <stdbool.h>

/**
 * AlexGyver RGBMath & Perceptual Color/Brightness utilities for embedded C.
 */

/* 100-step Gamma 2.2 correction table (0..100% -> 0..100% duty) */
uint8_t gyver_gamma2(uint8_t val);

/* 256-step Gamma 2.2 correction table (0..255 -> 0..255 duty) */
uint8_t gyver_gamma8(uint8_t val);

/* 256-step high-resolution Gamma 2.2 table directly mapping 0..255 to 0..1000 PWM */
uint16_t gyver_gamma10(uint8_t val);

/* Scale high-resolution gamma output to arbitrary out_max */
uint16_t gyver_gamma_pwm(uint8_t val, uint16_t out_max);

/* Smooth linear interpolation (lerp) */
static inline uint8_t gyver_lerp(uint8_t a, uint8_t b, uint8_t t) {
    return (uint8_t)(a + (int16_t)(b - a) * t / 255);
}

#endif /* GYVER_RGBMATH_H */
