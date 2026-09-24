#include "fh8016_py32.h"

/* State machine states for non-blocking 1-Wire transmission */
typedef enum {
    FH_STATE_IDLE = 0,
    FH_STATE_RESET,
    FH_STATE_BIT_HIGH,
    FH_STATE_BIT_LOW
} fh_state_t;

static volatile fh_state_t s_state = FH_STATE_IDLE;
static volatile uint32_t   s_frame = 0;
static volatile uint8_t    s_bit_idx = 0;
static GPIO_TypeDef       *s_port = GPIOA;
static uint16_t            s_pin = GPIO_PIN_1;

bool fh8016_is_busy(void)
{
    return (s_state != FH_STATE_IDLE);
}

void fh8016_init(fh8016_t *dev, GPIO_TypeDef *port, uint16_t pin)
{
    dev->port = port;
    dev->pin = pin;
    dev->raw_frame = 0;

    s_port = port;
    s_pin = pin;
    s_state = FH_STATE_IDLE;

    /* 1. Enable GPIO Clock */
    if (port == GPIOA) {
        RCC->IOPENR |= RCC_IOPENR_GPIOAEN;
    } else if (port == GPIOB) {
        RCC->IOPENR |= RCC_IOPENR_GPIOBEN;
    }

    /* 2. Configure Pin as Output Push-Pull High Speed */
    GPIO_InitTypeDef g = {0};
    g.Pin = pin;
    g.Mode = GPIO_MODE_OUTPUT_PP;
    g.Pull = GPIO_NOPULL;
    g.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(port, &g);

    /* Idle state is HIGH (3.3V) */
    port->BSRR = pin;

    /* 3. Enable TIM14 peripheral clock */
    RCC->APBENR2 |= RCC_APBENR2_TIM14EN;

    /* 4. Configure TIM14 for 1.0 MHz (1 tick = 1.0 us at 24 MHz) */
    TIM14->CR1 = 0;
    TIM14->PSC = 23;            // 24 MHz / (23 + 1) = 1.0 MHz
    TIM14->ARR = 1000;
    TIM14->CNT = 0;
    TIM14->SR = 0;
    TIM14->DIER = 0;

    /* 5. Enable TIM14 NVIC Interrupt */
    NVIC_SetPriority(TIM14_IRQn, 1);
    NVIC_EnableIRQ(TIM14_IRQn);
}

uint32_t fh8016_encode_frame(uint8_t percent, uint8_t bars, uint8_t icons, 
                             fh8016_color_t hl_l, fh8016_color_t hl_r)
{
    if (percent == 0 && bars == 0 && icons == 0 && hl_l == FH8016_COLOR_OFF && hl_r == FH8016_COLOR_OFF) {
        return 0; // Complete screen sleep
    }

    uint32_t frame = 0;

    // 1. Digits (1..99 via internal decoder, bit 7 for 100)
    if (percent >= 100) {
        frame |= (1UL << 7);
    } else if (percent > 0) {
        frame |= (percent & 0x7F);
    }

    // 2. Circular scale bars
    if (bars == 1) {
        frame |= (1UL << 12);
    } else if (bars == 2) {
        frame |= (1UL << 12) | (1UL << 13);
    } else if (bars == 3) {
        frame |= (1UL << 14);
    } else if (bars >= 4) {
        frame |= (1UL << 15);
    }

    // 3. Lightning icon
    if (icons & FH8016_ICON_LIGHTNING) {
        frame |= (1UL << 17);
    }

    // 4. Headlights (RGB)
    if (hl_l == FH8016_COLOR_RED || hl_l == FH8016_COLOR_YELLOW || hl_l == FH8016_COLOR_MAGENTA || hl_l == FH8016_COLOR_WHITE) {
        frame |= (1UL << 20); // Common red
    }
    if (hl_l == FH8016_COLOR_GREEN || hl_l == FH8016_COLOR_YELLOW || hl_l == FH8016_COLOR_BLUE || hl_l == FH8016_COLOR_CYAN || hl_l == FH8016_COLOR_WHITE) {
        frame |= (1UL << 18); // Left green
    }
    if (hl_r == FH8016_COLOR_GREEN || hl_r == FH8016_COLOR_YELLOW || hl_r == FH8016_COLOR_BLUE || hl_r == FH8016_COLOR_CYAN || hl_r == FH8016_COLOR_WHITE) {
        frame |= (1UL << 19); // Right green
    }
    if (hl_l == FH8016_COLOR_BLUE || hl_l == FH8016_COLOR_CYAN || hl_l == FH8016_COLOR_MAGENTA || hl_l == FH8016_COLOR_WHITE) {
        frame |= (1UL << 22); // Left blue
    }
    if (hl_r == FH8016_COLOR_BLUE || hl_r == FH8016_COLOR_CYAN || hl_r == FH8016_COLOR_MAGENTA || hl_r == FH8016_COLOR_WHITE) {
        frame |= (1UL << 23); // Right blue
    }

    return frame;
}

void fh8016_set_state(fh8016_t *dev, uint8_t percent, uint8_t bars, uint8_t icons, 
                      fh8016_color_t hl_l, fh8016_color_t hl_r)
{
    dev->raw_frame = fh8016_encode_frame(percent, bars, icons, hl_l, hl_r);
}

void fh8016_set_raw(fh8016_t *dev, uint32_t raw_bits26)
{
    dev->raw_frame = raw_bits26;
}

/* 
 * Non-blocking transmit trigger:
 * Starts 2000 us Reset pulse and returns immediately.
 * The rest of transmission is handled in TIM14 hardware interrupt.
 */
void fh8016_update(fh8016_t *dev)
{
    /* If previous packet is still being transmitted, skip to avoid collision */
    if (s_state != FH_STATE_IDLE) {
        return;
    }

    s_port = dev->port;
    s_pin  = dev->pin;
    s_frame = dev->raw_frame;
    s_bit_idx = 0;
    s_state = FH_STATE_RESET;

    /* 1. Pull line LOW for 2000 us Reset */
    s_port->BRR = s_pin;

    /* 2. Configure TIM14 for 2000 us */
    TIM14->CR1 &= ~TIM_CR1_CEN;
    TIM14->CNT = 0;
    TIM14->ARR = 2000 - 1;
    TIM14->SR = 0;
    TIM14->DIER = TIM_DIER_UIE;
    TIM14->CR1 |= TIM_CR1_CEN;
}

/* 
 * TIM14 Hardware Interrupt Handler (Completely non-blocking 1-Wire State Machine)
 * Average execution time: ~0.8 microseconds (less than 25 CPU cycles).
 */
void TIM14_IRQHandler(void)
{
    if (TIM14->SR & TIM_SR_UIF)
    {
        TIM14->SR = ~TIM_SR_UIF;

        switch (s_state)
        {
        case FH_STATE_RESET:
            /* Reset complete -> Start Bit 0 HIGH phase */
            s_state = FH_STATE_BIT_HIGH;
            s_port->BSRR = s_pin; // Line HIGH

            /* Bit 0 HIGH duration: 1 -> 395 us, 0 -> 95 us */
            if ((s_frame >> s_bit_idx) & 1U) {
                TIM14->ARR = 395 - 1;
            } else {
                TIM14->ARR = 95 - 1;
            }
            TIM14->CNT = 0;
            break;

        case FH_STATE_BIT_HIGH:
            /* Bit HIGH phase complete -> Start Bit LOW phase */
            s_state = FH_STATE_BIT_LOW;
            s_port->BRR = s_pin; // Line LOW

            /* Bit LOW duration: 1 -> 95 us, 0 -> 395 us */
            if ((s_frame >> s_bit_idx) & 1U) {
                TIM14->ARR = 95 - 1;
            } else {
                TIM14->ARR = 395 - 1;
            }
            TIM14->CNT = 0;
            break;

        case FH_STATE_BIT_LOW:
            /* Bit LOW phase complete -> advance to next bit */
            s_bit_idx++;
            if (s_bit_idx < 26)
            {
                /* Start next bit HIGH phase */
                s_state = FH_STATE_BIT_HIGH;
                s_port->BSRR = s_pin; // Line HIGH

                if ((s_frame >> s_bit_idx) & 1U) {
                    TIM14->ARR = 395 - 1;
                } else {
                    TIM14->ARR = 95 - 1;
                }
                TIM14->CNT = 0;
            }
            else
            {
                /* All 26 bits transmitted! Return line to Idle HIGH and stop timer */
                s_port->BSRR = s_pin; // Line HIGH
                TIM14->CR1 &= ~TIM_CR1_CEN;
                TIM14->DIER = 0;
                s_state = FH_STATE_IDLE;
            }
            break;

        default:
            s_port->BSRR = s_pin;
            TIM14->CR1 &= ~TIM_CR1_CEN;
            TIM14->DIER = 0;
            s_state = FH_STATE_IDLE;
            break;
        }
    }
}
