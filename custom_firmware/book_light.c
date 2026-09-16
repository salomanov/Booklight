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

/* Lamp State Machine */
static volatile lamp_state_t lamp_state = LAMP_STATE_SLEEP;
static volatile uint8_t current_brightness = 0;        /* 0..100 */
static uint8_t saved_brightness = DEFAULT_BRIGHTNESS_PERCENT;

/* Touch & State Timers */
static bool btn_pressed = false;
static uint32_t press_start_time = 0;
static uint32_t state_timer = 0;
static uint32_t last_ramp_tick = 0;
static uint32_t reading_start_time = 0;
static uint32_t auto_fade_start_time = 0;
static uint8_t  auto_fade_start_brightness = 0;

/* Fast PWM state (used inside 20 kHz SysTick) */
static volatile uint8_t pwm_counter = 0;
static volatile uint8_t pwm_duty = 0;                  /* 0..100 */

/* Battery monitoring */
static uint16_t bat_millivolts = 3900;
static uint8_t  bat_percent = 85;
static bool     vbus_present = false;
static uint32_t last_bat_sample_ms = 0;
static uint32_t last_disp_update_ms = 0;

/* ==========================================================================
 * Internal Prototypes
 * ========================================================================== */
static void init_gpio(void);
static void init_adc(void);
static void update_battery_measure(void);
static uint8_t calc_battery_percent(uint16_t mv);
static void update_display_hardware(uint32_t now);
static void update_state_machine(uint32_t now);
static void on_touch_down(uint32_t now);
static void on_touch_up(uint32_t now);
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
    /* 1 ms timebase incremented via HAL_IncTick in SysTick */
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
 * Touch Button Handlers
 * ========================================================================== */

static void on_touch_down(uint32_t now)
{
    press_start_time = now;
    btn_pressed = true;

    /* 1. If 60s auto-fadeout is in progress: short tap cancels fade and restores reading */
    if (lamp_state == LAMP_STATE_AUTO_FADING) {
        lamp_state = LAMP_STATE_READING;
        current_brightness = saved_brightness;
        pwm_duty = gyver_gamma2(current_brightness);
        reading_start_time = now; /* Reset 15-minute timer */
        return;
    }

    /* 2. If awake showing battery: press starts ramping up brightness */
    if (lamp_state == LAMP_STATE_AWAKE_BATTERY) {
        lamp_state = LAMP_STATE_RAMPING_UP;
        current_brightness = 0;
        pwm_duty = 0;
        last_ramp_tick = now;
        return;
    }

    /* 3. If reading: press starts ramping down brightness towards 0 */
    if (lamp_state == LAMP_STATE_READING || lamp_state == LAMP_STATE_HOLD_BRIGHTNESS_WAIT) {
        lamp_state = LAMP_STATE_RAMPING_DOWN;
        last_ramp_tick = now;
        return;
    }
}

static void on_touch_up(uint32_t now)
{
    btn_pressed = false;

    /* 1. Was ramping up: lock selected brightness and wait 3s */
    if (lamp_state == LAMP_STATE_RAMPING_UP) {
        if (current_brightness > 0) {
            saved_brightness = current_brightness;
            lamp_state = LAMP_STATE_HOLD_BRIGHTNESS_WAIT;
            state_timer = now;
        } else {
            lamp_state = LAMP_STATE_SLEEP;
        }
        return;
    }

    /* 2. Was ramping down: if >0 lock brightness, if 0 wait 3s then sleep */
    if (lamp_state == LAMP_STATE_RAMPING_DOWN) {
        if (current_brightness > 0) {
            saved_brightness = current_brightness;
            lamp_state = LAMP_STATE_HOLD_BRIGHTNESS_WAIT;
            state_timer = now;
        } else {
            lamp_state = LAMP_STATE_ZERO_WAIT;
            state_timer = now;
        }
        return;
    }
}

/* ==========================================================================
 * State Machine Update
 * ========================================================================== */

static void update_state_machine(uint32_t now)
{
    /* 1. Hold >1.5s in sleep to wake up and show battery */
    if (lamp_state == LAMP_STATE_SLEEP && btn_pressed) {
        if (now - press_start_time >= HOLD_TO_WAKE_MS) {
            lamp_state = LAMP_STATE_AWAKE_BATTERY;
            state_timer = now;
            current_brightness = 0;
            pwm_duty = 0;
        }
    }

    /* 2. Battery display timeout: 5s without press -> return to sleep */
    if (lamp_state == LAMP_STATE_AWAKE_BATTERY) {
        if (!btn_pressed && (now - state_timer >= AWAKE_BATTERY_TIMEOUT_MS)) {
            lamp_state = LAMP_STATE_SLEEP;
        }
    }

    /* 3. Smooth brightness ramp-up while held (+1% every 25 ms) */
    if (lamp_state == LAMP_STATE_RAMPING_UP && btn_pressed) {
        if (now - last_ramp_tick >= RAMP_STEP_MS) {
            last_ramp_tick = now;
            if (current_brightness < MAX_BRIGHTNESS_PERCENT) {
                current_brightness++;
                pwm_duty = gyver_gamma2(current_brightness);
            }
        }
    }

    /* 4. Display timeout (3s) after locking brightness */
    if (lamp_state == LAMP_STATE_HOLD_BRIGHTNESS_WAIT) {
        if (now - state_timer >= DISP_OFF_DELAY_MS) {
            lamp_state = LAMP_STATE_READING;
            reading_start_time = now; /* Start 15-minute inactivity timer */
        }
    }

    /* 5. Smooth brightness ramp-down while held (-1% every 25 ms) */
    if (lamp_state == LAMP_STATE_RAMPING_DOWN && btn_pressed) {
        if (now - last_ramp_tick >= RAMP_STEP_MS) {
            last_ramp_tick = now;
            if (current_brightness > 0) {
                current_brightness--;
                pwm_duty = gyver_gamma2(current_brightness);
            }
        }
    }

    /* 6. Brightness reached 0: wait 3s with '00' on screen then enter sleep */
    if (lamp_state == LAMP_STATE_ZERO_WAIT) {
        if (now - state_timer >= DISP_OFF_DELAY_MS) {
            lamp_state = LAMP_STATE_SLEEP;
            current_brightness = 0;
            pwm_duty = 0;
        }
    }

    /* 7. 15-minute reading inactivity check */
    if (lamp_state == LAMP_STATE_READING) {
        if (now - reading_start_time >= INACTIVITY_TIMEOUT_MS) {
            lamp_state = LAMP_STATE_AUTO_FADING;
            auto_fade_start_time = now;
            auto_fade_start_brightness = current_brightness;
        }
    }

    /* 8. 60-second linear auto-fadeout */
    if (lamp_state == LAMP_STATE_AUTO_FADING) {
        uint32_t elapsed = now - auto_fade_start_time;
        if (elapsed >= AUTO_FADEOUT_DURATION_MS) {
            current_brightness = 0;
            pwm_duty = 0;
            lamp_state = LAMP_STATE_SLEEP;
        } else {
            uint32_t remaining = AUTO_FADEOUT_DURATION_MS - elapsed;
            current_brightness = (uint8_t)((auto_fade_start_brightness * remaining) / AUTO_FADEOUT_DURATION_MS);
            pwm_duty = gyver_gamma2(current_brightness);
        }
    }
}

/* ==========================================================================
 * Display Hardware Update
 * ========================================================================== */

static void update_display_hardware(uint32_t now)
{
    /* 1. USB-C Charging overlay: display stays ON constantly */
    if (vbus_present) {
        uint8_t bars = 0;
        if (bat_percent >= 81)      bars = 4;
        else if (bat_percent >= 61) bars = 3;
        else if (bat_percent >= 41) bars = 2;
        else if (bat_percent >= 21) bars = 1;

        uint8_t icons = FH8016_ICON_PERCENT;
        if ((now / 500) % 2) {
            icons |= FH8016_ICON_LIGHTNING;
        }
        fh8016_set_state(&disp, bat_percent, bars, icons, FH8016_COLOR_CYAN, FH8016_COLOR_CYAN);
        fh8016_update(&disp);
        return;
    }

    /* 2. When completely asleep, display is off */
    if (lamp_state == LAMP_STATE_SLEEP) {
        fh8016_set_raw(&disp, 0);
        fh8016_update(&disp);
        return;
    }

    /* 3. Reading mode or Auto-fading: display is OFF to protect eyes */
    if (lamp_state == LAMP_STATE_READING || lamp_state == LAMP_STATE_AUTO_FADING) {
        /* Low battery alert (< 10%): gentle red headlights blink 150 ms every 3.5s */
        if (bat_percent < 10) {
            if ((now % 3500) < 150) {
                fh8016_set_state(&disp, 0, 0, FH8016_ICON_NONE, FH8016_COLOR_RED, FH8016_COLOR_RED);
            } else {
                fh8016_set_raw(&disp, 0);
            }
        } else {
            fh8016_set_raw(&disp, 0);
        }
        fh8016_update(&disp);
        return;
    }

    /* 4. Display active during wake battery check, ramp up, ramp down, and hold wait */
    uint8_t disp_val = 0;
    fh8016_color_t eye = FH8016_COLOR_CYAN;

    if (lamp_state == LAMP_STATE_AWAKE_BATTERY) {
        disp_val = bat_percent;
        if (bat_percent >= 100)      eye = FH8016_COLOR_BLUE;
        else if (bat_percent >= 67)  eye = FH8016_COLOR_GREEN;
        else if (bat_percent >= 34)  eye = FH8016_COLOR_YELLOW;
        else                         eye = FH8016_COLOR_RED;
    } else if (lamp_state == LAMP_STATE_RAMPING_UP ||
               lamp_state == LAMP_STATE_HOLD_BRIGHTNESS_WAIT ||
               lamp_state == LAMP_STATE_RAMPING_DOWN ||
               lamp_state == LAMP_STATE_ZERO_WAIT) {
        disp_val = current_brightness;
        eye = (lamp_state == LAMP_STATE_ZERO_WAIT) ? FH8016_COLOR_RED : FH8016_COLOR_CYAN;
    }

    uint8_t bars = 0;
    if (disp_val >= 81)      bars = 4;
    else if (disp_val >= 61) bars = 3;
    else if (disp_val >= 41) bars = 2;
    else if (disp_val >= 21) bars = 1;

    fh8016_set_state(&disp, disp_val, bars, FH8016_ICON_PERCENT, eye, eye);
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

    if (wakeup_active) {
        btn_pressed = true;
        press_start_time = HAL_GetTick();
    } else {
        btn_pressed = false;
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

    /* 1. Read Touch Pin and Detect Press/Release Edges */
    GPIO_PinState pin_state = HAL_GPIO_ReadPin(BOOK_LIGHT_TOUCH_PORT, BOOK_LIGHT_TOUCH_PIN);
#if BOOK_LIGHT_TOUCH_ACTIVE_HIGH
    bool pin_active = (pin_state == GPIO_PIN_SET);
#else
    bool pin_active = (pin_state == GPIO_PIN_RESET);
#endif

    static bool last_pin_active = false;
    if (pin_active != last_pin_active) {
        last_pin_active = pin_active;
        if (pin_active) {
            on_touch_down(now);
        } else {
            on_touch_up(now);
        }
    }

    /* 2. Update State Machine */
    update_state_machine(now);

    /* 3. Sample Battery Voltage every 500 ms */
    if (now - last_bat_sample_ms >= 500) {
        last_bat_sample_ms = now;
        update_battery_measure();
    }

    /* 4. Update FH8016 Display Hardware at ~30 Hz (every 33 ms) */
    if (now - last_disp_update_ms >= 33) {
        last_disp_update_ms = now;
        update_display_hardware(now);
    }

    /* 5. Sleep check: If lamp is in SLEEP and not pressed and not on USB-C charger */
    if (lamp_state == LAMP_STATE_SLEEP && !btn_pressed && !vbus_present) {
        enter_deep_sleep();
    }
}
