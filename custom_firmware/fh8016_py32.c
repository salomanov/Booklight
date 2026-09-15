#include "fh8016_py32.h"

// 7-segment lookup for digits 0..9 (segments: a, b, c, d, e, f, g)
static const uint8_t DIGIT_7SEG[10] = {
    0x3F, // 0: a, b, c, d, e, f
    0x06, // 1: b, c
    0x5B, // 2: a, b, d, e, g
    0x4F, // 3: a, b, c, d, g
    0x66, // 4: b, c, f, g
    0x6D, // 5: a, c, d, f, g
    0x7D, // 6: a, c, d, e, f, g
    0x07, // 7: a, b, c
    0x7F, // 8: a, b, c, d, e, f, g
    0x6F  // 9: a, b, c, d, f, g
};

// Calibrated microsecond delay for Cortex-M0+ at 24 MHz
// Each iteration of (sub, bne) takes 3 cycles.
// 24 MHz / 3 cycles = 8 iterations per microsecond.
static inline void delay_us(uint32_t us) {
    uint32_t count = us * 8;
    __asm__ volatile (
        "1: sub %0, %0, #1 \n"
        "   bne 1b         \n"
        : "+l" (count)
        :
        : "cc"
    );
}

static inline void set_pin(fh8016_t *dev, uint8_t level) {
    if (level) {
        dev->port->BSRR = dev->pin;
    } else {
        dev->port->BSRR = ((uint32_t)dev->pin << 16U);
    }
}

static void send_bit(fh8016_t *dev, bool val) {
    if (val) {
        set_pin(dev, 1);
        delay_us(395);
        set_pin(dev, 0);
        delay_us(95);
    } else {
        set_pin(dev, 1);
        delay_us(95);
        set_pin(dev, 0);
        delay_us(395);
    }
}

void fh8016_init(fh8016_t *dev, GPIO_TypeDef *port, uint16_t pin) {
    dev->port = port;
    dev->pin = pin;
    dev->raw_frame = 0;

    if (port == GPIOA) {
        __HAL_RCC_GPIOA_CLK_ENABLE();
    } else if (port == GPIOB) {
        __HAL_RCC_GPIOB_CLK_ENABLE();
    }

    GPIO_InitTypeDef g = {0};
    g.Pin = pin;
    g.Mode = GPIO_MODE_OUTPUT_PP;
    g.Pull = GPIO_NOPULL;
    g.Speed = GPIO_SPEED_FREQ_HIGH;
    HAL_GPIO_Init(port, &g);

    set_pin(dev, 1); // Idle line is HIGH
}

uint32_t fh8016_encode_frame(uint8_t percent, uint8_t bars, uint8_t icons, 
                             fh8016_color_t hl_l, fh8016_color_t hl_r) {
    uint32_t frame = 0;

    uint8_t tens = (percent / 10) % 10;
    uint8_t units = percent % 10;
    bool hundreds = (percent >= 100);

    // 1. Digits (interleaved segments)
    uint8_t seg_t = (percent < 10) ? 0 : DIGIT_7SEG[tens];
    uint8_t seg_u = DIGIT_7SEG[units];

    for (int k = 0; k < 7; k++) {
        if ((seg_u >> k) & 1) frame |= (1UL << (2 * k));
        if ((seg_t >> k) & 1) frame |= (1UL << (2 * k + 1));
    }

    // Hundreds digit '1'
    if (hundreds) {
        frame |= (1UL << 7) | (1UL << 9);
    }

    // 2. 4 divisions of circular scale (25%, 50%, 75%, 100%)
    if (bars >= 1) frame |= (1UL << 14); // Lower-Left arc
    if (bars >= 2) frame |= (1UL << 12); // Lower-Right arc
    if (bars >= 3) frame |= (1UL << 17); // Upper-Right arc
    if (bars >= 4) frame |= (1UL << 15); // Upper-Left arc

    // 3. Icons
    if (icons & FH8016_ICON_DROPLET)   frame |= (1UL << 0);
    if (icons & FH8016_ICON_PERCENT)   frame |= (1UL << 16);
    if (icons & FH8016_ICON_LIGHTNING) frame |= (1UL << 13);

    // 4. Headlights RGB
    // Left eye:
    switch (hl_l) {
        case FH8016_COLOR_RED:     frame |= (1UL << 21); break;
        case FH8016_COLOR_GREEN:   frame |= (1UL << 18); break;
        case FH8016_COLOR_BLUE:    frame |= (1UL << 22); break;
        case FH8016_COLOR_CYAN:    frame |= (1UL << 18) | (1UL << 22); break;
        case FH8016_COLOR_YELLOW:  frame |= (1UL << 18) | (1UL << 21); break;
        case FH8016_COLOR_MAGENTA: frame |= (1UL << 21) | (1UL << 22); break;
        case FH8016_COLOR_WHITE:   frame |= (1UL << 18) | (1UL << 21) | (1UL << 22); break;
        default: break;
    }

    // Right eye:
    switch (hl_r) {
        case FH8016_COLOR_RED:     frame |= (1UL << 20); break;
        case FH8016_COLOR_GREEN:   frame |= (1UL << 19); break;
        case FH8016_COLOR_BLUE:    frame |= (1UL << 23); break;
        case FH8016_COLOR_CYAN:    frame |= (1UL << 19) | (1UL << 23); break;
        case FH8016_COLOR_YELLOW:  frame |= (1UL << 19) | (1UL << 20); break;
        case FH8016_COLOR_MAGENTA: frame |= (1UL << 20) | (1UL << 23); break;
        case FH8016_COLOR_WHITE:   frame |= (1UL << 19) | (1UL << 20) | (1UL << 23); break;
        default: break;
    }

    return frame;
}

void fh8016_set_state(fh8016_t *dev, uint8_t percent, uint8_t bars, uint8_t icons, 
                      fh8016_color_t hl_l, fh8016_color_t hl_r) {
    dev->raw_frame = fh8016_encode_frame(percent, bars, icons, hl_l, hl_r);
}

void fh8016_set_raw(fh8016_t *dev, uint32_t raw_bits26) {
    dev->raw_frame = raw_bits26;
}

void fh8016_update(fh8016_t *dev) {
    uint32_t bits = dev->raw_frame;

    // Sync Break: 2000 us LOW
    set_pin(dev, 0);
    delay_us(2000);

    // Mark after break: 100 us HIGH
    set_pin(dev, 1);
    delay_us(100);

    // 26 data bits, LSB first
    for (int i = 0; i < 26; i++) {
        send_bit(dev, (bits >> i) & 1);
    }

    // Return to idle HIGH
    set_pin(dev, 1);
}
