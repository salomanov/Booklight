#ifndef BOOK_LIGHT_H
#define BOOK_LIGHT_H

#include "py32f002b_hal.h"
#include "fh8016_py32.h"
#include <stdint.h>
#include <stdbool.h>

/* ==========================================================================
 * Hardware Pinout Configuration
 * ========================================================================== */

/* LED Filament Output (Logo MOSFET Gate) */
#define BOOK_LIGHT_LED_PORT             GPIOA
#define BOOK_LIGHT_LED_PIN              GPIO_PIN_0

/* Capacitive Touch Button Input (replaces puff microphone) */
#define BOOK_LIGHT_TOUCH_PORT           GPIOB
#define BOOK_LIGHT_TOUCH_PIN            GPIO_PIN_5
#define BOOK_LIGHT_TOUCH_ACTIVE_HIGH    1       /* 1 = High when touched (TTP223 default) */

/* Alternate Touch Pins available on board (PB5, PA3, PA1) */
#define BOOK_LIGHT_TOUCH_IRQn           EXTI4_15_IRQn

/* 1-Wire FH8016 Display Data Pin (replaces old 8-pin display) */
#define BOOK_LIGHT_DISP_PORT            GPIOA
#define BOOK_LIGHT_DISP_PIN             GPIO_PIN_4

/* USB-C 5V VBUS Detection Pin */
#define BOOK_LIGHT_VBUS_PORT            GPIOB
#define BOOK_LIGHT_VBUS_PIN             GPIO_PIN_4

/* ==========================================================================
 * Operating Parameters & Timing
 * ========================================================================== */

#define INACTIVITY_TIMEOUT_MS           (15UL * 60UL * 1000UL)  /* 15 minutes = 900,000 ms */
#define AUTO_FADEOUT_DURATION_MS        (60UL * 1000UL)         /* 1 minute = 60,000 ms */

#define MANUAL_FADE_DURATION_MS         350U                    /* Smooth on/off transition (ms) */
#define LONG_PRESS_THRESHOLD_MS         400U                    /* Threshold to distinguish tap vs hold */
#define DIMMING_RAMP_STEP_MS            22U                     /* Time per 1% brightness change */

#define MIN_BRIGHTNESS_PERCENT          5U                      /* 5% nightlight floor */
#define MAX_BRIGHTNESS_PERCENT          100U                    /* 100% full reading brightness */
#define DEFAULT_BRIGHTNESS_PERCENT      70U                     /* Default brightness on first power-on */

/* ==========================================================================
 * Lamp Operational States
 * ========================================================================== */

typedef enum {
    LAMP_STATE_OFF = 0,
    LAMP_STATE_FADE_IN,
    LAMP_STATE_ON,
    LAMP_STATE_DIMMING,
    LAMP_STATE_AUTO_FADING,
    LAMP_STATE_FADE_OUT
} lamp_state_t;

/* ==========================================================================
 * Public API
 * ========================================================================== */

void book_light_init(void);
void book_light_loop(void);

/* Called at 20 kHz from SysTick handler: 200 Hz PWM across 100 duty steps */
void book_light_pwm_tick(void);

/* Called every 1 ms from SysTick handler */
void book_light_tick_1ms(void);

/* Touch interrupt wakeup callback */
void book_light_on_touch_irq(void);

#endif /* BOOK_LIGHT_H */