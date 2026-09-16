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

#define BOOT_GRACE_PERIOD_MS            3000UL                  /* 3s boot grace window: keeps SWD active and shows battery */
#define HOLD_TO_WAKE_MS                 1500UL                  /* >1.5s hold to prevent accidental wakeup */
#define AWAKE_BATTERY_TIMEOUT_MS        5000UL                  /* 5s battery % display before auto-sleep */
#define DISP_OFF_DELAY_MS               3000UL                  /* 3s display delay before blanking */
#define INACTIVITY_TIMEOUT_MS           (15UL * 60UL * 1000UL)  /* 15 minutes reading inactivity timer */
#define AUTO_FADEOUT_DURATION_MS        (60UL * 1000UL)         /* 60 seconds linear fadeout */
#define RAMP_STEP_MS                    25U                     /* 25 ms per 1% brightness change */
#define TOUCH_DEBOUNCE_MS               35U                     /* 35 ms touch button debounce filter */
#define BATTERY_CUTOFF_MV               3100U                   /* 3.10V low-voltage safety cutoff for Li-ion */

#define MIN_BRIGHTNESS_PERCENT          5U                      /* 5% nightlight floor */
#define MAX_BRIGHTNESS_PERCENT          100U                    /* 100% full reading brightness */
#define DEFAULT_BRIGHTNESS_PERCENT      70U                     /* Default brightness */

/* ==========================================================================
 * Lamp Operational States (User Scenario State Machine)
 * ========================================================================== */

typedef enum {
    LAMP_STATE_BOOT_WAIT = 0,         /* Startup grace window: core awake, SWD accessible, shows battery */
    LAMP_STATE_SLEEP,                 /* Full sleep: filament off, display off */
    LAMP_STATE_AWAKE_BATTERY,         /* Wakeup after >1.5s: filament off, display shows battery % */
    LAMP_STATE_RAMPING_UP,            /* Button held: brightness ramps 0..100%, display shows % */
    LAMP_STATE_HOLD_BRIGHTNESS_WAIT,  /* Button released: brightness locked, display waits 3s */
    LAMP_STATE_READING,               /* Reading mode: filament shines, display is OFF */
    LAMP_STATE_RAMPING_DOWN,          /* Button held while reading: brightness dims to 0, display shows % */
    LAMP_STATE_ZERO_WAIT,             /* Brightness reached 0: display shows 00%, waits 3s then sleep */
    LAMP_STATE_AUTO_FADING            /* 15 mins elapsed: 60s fadeout to 0. Short tap restores brightness! */
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
