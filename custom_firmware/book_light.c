#include "book_light.h"
#include "gyver_ubutton.h"
#include "gyver_rgbmath.h"
#include "py32f002b_hal_adc.h"
#include "py32f002b_hal_pwr.h"
#include <string.h>

/* ==========================================================================
 * State Variables
 * ========================================================================== */

/* Display driver instance */
static fh8016_t disp;

/* Gyver uButton state machine */
static ubutton_t touch_btn;

/* ADC Handle for Battery Reading */
static ADC_HandleTypeDef hadc_bat;

/* Lamp State */
static volatile lamp_state_t lamp_state = LAMP_STATE_OFF;
static volatile uint8_t current_brightness = 0;        /* 0..100 */
static volatile uint8_t target_brightness = 0;         /* 0..100 */
static uint8_t saved_brightness = DEFAULT_BRIGHTNESS_PERCENT;
static int8_t dim_direction = 1;                       /* +1 = brightening, -1 = dimming */
static bool auto_fade_cancelled = false;               /* Tracks if touch interrupted auto-fadeout */

/* Fast PWM state (used inside 20 kHz SysTick) */
static volatile uint8_t pwm_counter = 0;
static volatile uint8_t pwm_duty = 0;                  /* 0..100 */

/* Timers (incremented in 1 ms SysTick) */
static volatile uint32_t inactivity_timer_ms = 0;
static volatile uint32_t auto_fade_timer_ms = 0;
static volatile uint8_t  auto_fade_start_brightness = 0;
static volatile uint16_t fade_step_timer_ms = 0;

/* Battery monitoring */
static uint16_t bat_millivolts = 3900;
static uint8_t  bat_percent = 80;
static bool     vbus_present = false;
static uint32_t last_bat_sample_ms = 0;
static uint32_t last_disp_update_ms = 0;
static uint8_t  charge_anim_frame = 0;
static uint32_t show_brightness_until_ms = 0;

/* ==========================================================================
 * Internal Prototypes
 * ========================================================================== */
static void init_gpio(void);
static void init_adc(void);
static void update_battery_measure(void);
static uint8_t calc_battery_percent(uint16_t mv);
static void update_display(uint32_t now_ms);
static void enter_deep_sleep(void);

/* ==========================================================================
 * Hardware Initialization
 * ========================================================================== */

void book_light_init(void)
{
    init_gpio();
    init_adc();
    ubutton_init(&touch_btn);

    /* Initialize 1-Wire FH8016 display */
    fh8016_init(&disp, BOOK_LIGHT_DISP_PORT, BOOK_LIGHT_DISP_PIN);

    /* Blank display on boot */
    fh8016_set_raw(&disp, 0);
    fh8016_update(&disp);

    /* Initial battery sample */
    update_battery_measure();
}

static void init_gpio(void)
{
    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();

    GPIO_InitTypeDef g = {0};

    /* 1. LED Output Pin (PA0) */
    g.Pin = BOOK_LIGHT_LED_PIN;
    g.Mode = GPIO_MODE_OUTPUT_PP;
    g.Pull = GPIO_NOPULL;
    g.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(BOOK_LIGHT_LED_PORT, &g);
    HAL_GPIO_WritePin(BOOK_LIGHT_LED_PORT, BOOK_LIGHT_LED_PIN, GPIO_PIN_RESET);

    /* 2. Touch Button Input Pin with EXTI Interrupt */
    g.Pin = BOOK_LIGHT_TOUCH_PIN;
#if BOOK_LIGHT_TOUCH_ACTIVE_HIGH
    g.Mode = GPIO_MODE_IT_RISING_FALLING;
    g.Pull = GPIO_PULLDOWN;
#else
    g.Mode = GPIO_MODE_IT_RISING_FALLING;
    g.Pull = GPIO_PULLUP;
#endif
    g.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(BOOK_LIGHT_TOUCH_PORT, &g);

    HAL_NVIC_SetPriority(BOOK_LIGHT_TOUCH_IRQn, 1, 0);
    HAL_NVIC_EnableIRQ(BOOK_LIGHT_TOUCH_IRQn);

    /* 3. USB 5V VBUS Input Pin (PB4) */
    g.Pin = BOOK_LIGHT_VBUS_PIN;
    g.Mode = GPIO_MODE_INPUT;
    g.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(BOOK_LIGHT_VBUS_PORT, &g);
}

static void init_adc(void)
{
    ADC_ChannelConfTypeDef sConfig = {0};

    __HAL_RCC_ADC_CLK_ENABLE();

    hadc_bat.Instance = ADC1;
    hadc_bat.Init.ClockPrescaler        = ADC_CLOCK_SYNC_PCLK_DIV32;
    hadc_bat.Init.Resolution            = ADC_RESOLUTION_12B;
    hadc_bat.Init.DataAlign             = ADC_DATAALIGN_RIGHT;
    hadc_bat.Init.ScanConvMode          = ADC_SCAN_DIRECTION_FORWARD;
    hadc_bat.Init.EOCSelection          = ADC_EOC_SINGLE_CONV;
    hadc_bat.Init.LowPowerAutoWait      = DISABLE;
    hadc_bat.Init.ContinuousConvMode    = DISABLE;
    hadc_bat.Init.DiscontinuousConvMode = DISABLE;
    hadc_bat.Init.ExternalTrigConv      = ADC_SOFTWARE_START;
    hadc_bat.Init.ExternalTrigConvEdge  = ADC_EXTERNALTRIGCONVEDGE_NONE;
    hadc_bat.Init.Overrun               = ADC_OVR_DATA_OVERWRITTEN;
    hadc_bat.Init.SamplingTimeCommon    = ADC_SAMPLETIME_41CYCLES_5;

    HAL_ADC_Init(&hadc_bat);

    /* Measure Internal 1.20V Bandgap against VCCA (Li-ion battery voltage) */
    sConfig.Rank    = ADC_RANK_CHANNEL_NUMBER;
    sConfig.Channel = ADC_CHANNEL_VREFINT;
    HAL_ADC_ConfigChannel(&hadc_bat, &sConfig);

    HAL_ADC_ConfigVrefBuf(&hadc_bat, ADC_VREFBUF_VCCA);
    HAL_ADCEx_Calibration_Start(&hadc_bat);
}

/* ==========================================================================
 * Fast PWM Tick (Called at 20 kHz from SysTick)
 * ========================================================================== */

void book_light_pwm_tick(void)
{
    if (pwm_duty == 0) {
        BOOK_LIGHT_LED_PORT->BSRR = ((uint32_t)BOOK_LIGHT_LED_PIN << 16U);
        return;
    }

    if (pwm_duty >= 100) {
        BOOK_LIGHT_LED_PORT->BSRR = BOOK_LIGHT_LED_PIN;
        return;
    }

    if (++pwm_counter >= 100) {
        pwm_counter = 0;
    }

    if (pwm_counter < pwm_duty) {
        BOOK_LIGHT_LED_PORT->BSRR = BOOK_LIGHT_LED_PIN;
    } else {
        BOOK_LIGHT_LED_PORT->BSRR = ((uint32_t)BOOK_LIGHT_LED_PIN << 16U);
    }
}

/* ==========================================================================
 * 1 ms System Timebase Tick (Called from SysTick)
 * ========================================================================== */

void book_light_tick_1ms(void)
{
    /* 1. Manual Fade In / Fade Out Transitions (~350 ms) */
    if (lamp_state == LAMP_STATE_FADE_IN || lamp_state == LAMP_STATE_FADE_OUT) {
        if (++fade_step_timer_ms >= (MANUAL_FADE_DURATION_MS / 100)) {
            fade_step_timer_ms = 0;
            if (current_brightness < target_brightness) {
                current_brightness++;
                pwm_duty = gyver_gamma2(current_brightness);
                if (current_brightness >= target_brightness) {
                    lamp_state = LAMP_STATE_ON;
                    inactivity_timer_ms = 0;
                }
            } else if (current_brightness > target_brightness) {
                current_brightness--;
                pwm_duty = gyver_gamma2(current_brightness);
                if (current_brightness == 0) {
                    lamp_state = LAMP_STATE_OFF;
                }
            }
        }
    }

    /* 2. 15-Minute Inactivity Monitoring */
    if (lamp_state == LAMP_STATE_ON) {
        inactivity_timer_ms++;
        if (inactivity_timer_ms >= INACTIVITY_TIMEOUT_MS) {
            /* 15 minutes of inactivity reached: begin smooth 60s auto fade-out */
            lamp_state = LAMP_STATE_AUTO_FADING;
            auto_fade_timer_ms = 0;
            auto_fade_start_brightness = current_brightness;
        }
    }

    /* 3. 60-Second Linear Fade-Out to 0 */
    if (lamp_state == LAMP_STATE_AUTO_FADING) {
        auto_fade_timer_ms++;
        if (auto_fade_timer_ms >= AUTO_FADEOUT_DURATION_MS) {
            current_brightness = 0;
            pwm_duty = 0;
            lamp_state = LAMP_STATE_OFF;
        } else {
            uint32_t remaining = AUTO_FADEOUT_DURATION_MS - auto_fade_timer_ms;
            current_brightness = (uint8_t)((auto_fade_start_brightness * remaining) / AUTO_FADEOUT_DURATION_MS);
            pwm_duty = gyver_gamma2(current_brightness);
        }
    }
}

/* ==========================================================================
 * Battery Measurement (Bandgap ADC)
 * ========================================================================== */

static void update_battery_measure(void)
{
    /* Read USB-C 5V presence */
    vbus_present = (HAL_GPIO_ReadPin(BOOK_LIGHT_VBUS_PORT, BOOK_LIGHT_VBUS_PIN) == GPIO_PIN_SET);

    /* Poll ADC for internal 1.20V Bandgap reference */
    HAL_ADC_Start(&hadc_bat);
    if (HAL_ADC_PollForConversion(&hadc_bat, 5000) == HAL_OK) {
        uint32_t val = HAL_ADC_GetValue(&hadc_bat);
        if (val > 500 && val < 4095) {
            uint16_t measured_mv = (uint16_t)((4095UL * 1200UL) / val);

            /* Exponential smoothing filter */
            bat_millivolts = (uint16_t)(((uint32_t)bat_millivolts * 7 + measured_mv) / 8);
            bat_percent = calc_battery_percent(bat_millivolts);
        }
    }
}

static uint8_t calc_battery_percent(uint16_t mv)
{
    if (mv >= 4150) return 100;
    if (mv >= 4050) return 90 + (uint8_t)(((mv - 4050) * 10) / 100);
    if (mv >= 3950) return 80 + (uint8_t)(((mv - 3950) * 10) / 100);
    if (mv >= 3850) return 65 + (uint8_t)(((mv - 3850) * 15) / 100);
    if (mv >= 3780) return 50 + (uint8_t)(((mv - 3780) * 15) / 70);
    if (mv >= 3700) return 35 + (uint8_t)(((mv - 3700) * 15) / 80);
    if (mv >= 3600) return 20 + (uint8_t)(((mv - 3600) * 15) / 100);
    if (mv >= 3450) return 10 + (uint8_t)(((mv - 3450) * 10) / 150);
    if (mv >= 3300) return 1  + (uint8_t)(((mv - 3300) * 9)  / 150);
    return 0;
}

/* ==========================================================================
 * Display State Update
 * ========================================================================== */

static void update_display(uint32_t now_ms)
{
    /* If lamp is OFF and not charging, display is completely turned OFF */
    if (lamp_state == LAMP_STATE_OFF && !vbus_present) {
        fh8016_set_raw(&disp, 0);
        fh8016_update(&disp);
        return;
    }

    uint8_t disp_val;
    uint8_t icons = FH8016_ICON_PERCENT;
    uint8_t bars;
    fh8016_color_t eye_l = FH8016_COLOR_GREEN;
    fh8016_color_t eye_r = FH8016_COLOR_GREEN;

    /* Display Mode: Brightness level during dimming OR Battery % normally */
    if (now_ms < show_brightness_until_ms) {
        disp_val = current_brightness;
        eye_l = FH8016_COLOR_CYAN;
        eye_r = FH8016_COLOR_CYAN;
    } else {
        disp_val = bat_percent;
        if (bat_percent > 30) {
            eye_l = eye_r = FH8016_COLOR_GREEN;
        } else if (bat_percent > 15) {
            eye_l = eye_r = FH8016_COLOR_YELLOW;
        } else {
            /* Critical battery warning (< 15%): blink headlights red */
            eye_l = eye_r = ((now_ms / 300) & 1) ? FH8016_COLOR_RED : FH8016_COLOR_OFF;
        }
    }

    /* Circular scale bars & charging animation */
    if (vbus_present) {
        /* Мигающая молния при зарядке (такт 500 мс) */
        if ((now_ms / 500) % 2) {
            icons |= FH8016_ICON_LIGHTNING;
        }
        eye_l = eye_r = FH8016_COLOR_CYAN;
    }

    /* Шкала по ТЗ: 
     *  0..20%:  0 делений
     * 21..40%:  1 деление
     * 41..60%:  2 деления
     * 61..80%:  3 деления
     * 81..100%: 4 деления
     */
    if (disp_val >= 81)      bars = 4;
    else if (disp_val >= 61) bars = 3;
    else if (disp_val >= 41) bars = 2;
    else if (disp_val >= 21) bars = 1;
    else                     bars = 0;

    /* Цвета глаз в зависимости от уровня заряда (если не в режиме диммирования и не на зарядке) */
    if (now_ms >= show_brightness_until_ms && !vbus_present) {
        if (bat_percent >= 100) {
            eye_l = eye_r = FH8016_COLOR_BLUE;
        } else if (bat_percent >= 67) {
            eye_l = eye_r = FH8016_COLOR_GREEN;
        } else if (bat_percent >= 34) {
            eye_l = eye_r = FH8016_COLOR_YELLOW;
        } else if (bat_percent >= 15) {
            eye_l = eye_r = FH8016_COLOR_RED;
        } else {
            /* Критический разряд (< 15%): моргающий красный */
            eye_l = eye_r = ((now_ms / 300) & 1) ? FH8016_COLOR_RED : FH8016_COLOR_OFF;
        }
    }

    fh8016_set_state(&disp, disp_val, bars, icons, eye_l, eye_r);
    fh8016_update(&disp);
}

/* ==========================================================================
 * Deep Sleep (STOP Mode)
 * ========================================================================== */

static void enter_deep_sleep(void)
{
    /* 1. Blank display */
    fh8016_set_raw(&disp, 0);
    fh8016_update(&disp);

    /* 2. Turn off LED filament */
    BOOK_LIGHT_LED_PORT->BSRR = ((uint32_t)BOOK_LIGHT_LED_PIN << 16U);
    pwm_duty = 0;

    /* 3. Suspend SysTick */
    HAL_SuspendTick();

    /* 4. Enter ultra low power STOP mode with WFI */
    HAL_PWR_EnterSTOPMode(PWR_LOWPOWERREGULATOR_ON, PWR_STOPENTRY_WFI);

    /* --- Woken up by EXTI interrupt on touch pin --- */
    HAL_ResumeTick();

    GPIO_PinState pin = HAL_GPIO_ReadPin(BOOK_LIGHT_TOUCH_PORT, BOOK_LIGHT_TOUCH_PIN);
#if BOOK_LIGHT_TOUCH_ACTIVE_HIGH
    bool wakeup_active = (pin == GPIO_PIN_SET);
#else
    bool wakeup_active = (pin == GPIO_PIN_RESET);
#endif

    /* Reset uButton state */
    ubutton_reset(&touch_btn);
    auto_fade_cancelled = false;

    if (wakeup_active) {
        /* Smoothly turn ON lamp */
        target_brightness = (saved_brightness >= MIN_BRIGHTNESS_PERCENT) ? saved_brightness : DEFAULT_BRIGHTNESS_PERCENT;
        lamp_state = LAMP_STATE_FADE_IN;
        fade_step_timer_ms = 0;
        inactivity_timer_ms = 0;
    }
}

/* ==========================================================================
 * Touch EXTI Wakeup Interrupt Callback
 * ========================================================================== */

void book_light_on_touch_irq(void)
{
    /* EXTI flag is cleared in HAL_GPIO_EXTI_IRQHandler */
}

/* ==========================================================================
 * Main Polling Loop
 * ========================================================================== */

void book_light_loop(void)
{
    uint32_t now = HAL_GetTick();

    /* 1. Read Touch Pin and Tick Gyver uButton State Machine */
    GPIO_PinState pin_state = HAL_GPIO_ReadPin(BOOK_LIGHT_TOUCH_PORT, BOOK_LIGHT_TOUCH_PIN);
#if BOOK_LIGHT_TOUCH_ACTIVE_HIGH
    bool pin_active = (pin_state == GPIO_PIN_SET);
#else
    bool pin_active = (pin_state == GPIO_PIN_RESET);
#endif

    ubutton_tick(&touch_btn, pin_active, now);

    /* --- Gyver uButton Event Dispatching --- */

    /* A. Touch Press Down Event */
    if (ubutton_press(&touch_btn)) {
        /* INTERRUPT FADE-OUT: Touching button during 60s fade cancels fade and restores reading level */
        if (lamp_state == LAMP_STATE_AUTO_FADING) {
            target_brightness = (saved_brightness >= MIN_BRIGHTNESS_PERCENT) ? saved_brightness : DEFAULT_BRIGHTNESS_PERCENT;
            lamp_state = LAMP_STATE_FADE_IN;
            fade_step_timer_ms = 0;
            inactivity_timer_ms = 0;
            auto_fade_cancelled = true;
        }
    }

    /* B. Short Click (< 400 ms) Event -> Toggle Light ON / OFF */
    if (ubutton_click(&touch_btn)) {
        if (auto_fade_cancelled) {
            /* If this click was the touch that interrupted auto-fade, keep lamp ON */
            auto_fade_cancelled = false;
        } else {
            if (lamp_state == LAMP_STATE_OFF) {
                target_brightness = (saved_brightness >= MIN_BRIGHTNESS_PERCENT) ? saved_brightness : DEFAULT_BRIGHTNESS_PERCENT;
                lamp_state = LAMP_STATE_FADE_IN;
                fade_step_timer_ms = 0;
                inactivity_timer_ms = 0;
            } else if (lamp_state == LAMP_STATE_ON || lamp_state == LAMP_STATE_FADE_IN) {
                target_brightness = 0;
                lamp_state = LAMP_STATE_FADE_OUT;
                fade_step_timer_ms = 0;
            }
        }
    }

    /* C. Step Event during Long-Press Hold (fires every UB_STEP_PRD_MS = 25 ms) */
    if (ubutton_step(&touch_btn)) {
        if (lamp_state == LAMP_STATE_ON || lamp_state == LAMP_STATE_DIMMING) {
            lamp_state = LAMP_STATE_DIMMING;
            inactivity_timer_ms = 0;
            show_brightness_until_ms = now + 1500;

            if (dim_direction > 0) {
                if (current_brightness < MAX_BRIGHTNESS_PERCENT) {
                    current_brightness++;
                }
            } else {
                if (current_brightness > MIN_BRIGHTNESS_PERCENT) {
                    current_brightness--;
                }
            }
            saved_brightness = current_brightness;
            pwm_duty = gyver_gamma2(current_brightness);
        }
    }

    /* D. Release after Hold/Step Dimming */
    if (ubutton_release_step(&touch_btn)) {
        /* Invert ramp direction for next long press */
        dim_direction = -dim_direction;
        if (lamp_state == LAMP_STATE_DIMMING) {
            lamp_state = LAMP_STATE_ON;
            inactivity_timer_ms = 0;
        }
    }

    /* 2. Sample Battery Voltage every 500 ms */
    if (now - last_bat_sample_ms >= 500) {
        last_bat_sample_ms = now;
        update_battery_measure();
    }

    /* 3. Update FH8016 Display every 50 ms (20 Hz) */
    if (now - last_disp_update_ms >= 50) {
        last_disp_update_ms = now;
        update_display(now);
    }

    /* 4. Sleep check: If lamp is completely OFF and not on USB charger, enter STOP mode */
    if (lamp_state == LAMP_STATE_OFF && !vbus_present && !ubutton_is_pressed(&touch_btn)) {
        enter_deep_sleep();
    }
}
