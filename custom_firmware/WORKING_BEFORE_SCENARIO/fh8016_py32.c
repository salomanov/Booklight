#include "fh8016_py32.h"


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
    if (percent == 0 && bars == 0 && icons == 0 && hl_l == FH8016_COLOR_OFF && hl_r == FH8016_COLOR_OFF) {
        return 0; // ╨Я╨╛╨╗╨╜╤Л╨╣ ╤Б╨╛╨╜ ╨┤╨╕╤Б╨┐╨╗╨╡╤П
    }

    uint32_t frame = 0;

    // 1. ╨ж╨╕╤Д╤А╤Л (╨░╨┐╨┐╨░╤А╨░╤В╨╜╤Л╨╣ ╨┤╨╡╨║╨╛╨┤╨╡╤А FH8016)
    if (percent >= 100) {
        frame |= (1UL << 7); // ╨С╨╕╤В 7 ╨╖╨░╨╢╨╕╨│╨░╨╡╤В ╤Б╨╛╤В╨╜╨╕ '100'
    } else if (percent > 0) {
        frame |= (percent & 0x7F); // ╨з╨╕╤Б╨╗╨╛ 1..99
    }

    // 2. ╨Ф╨╡╨╗╨╡╨╜╨╕╤П ╨║╤А╤Г╨│╨╛╨▓╨╛╨╣ ╤И╨║╨░╨╗╤Л (╨┐╤А╨╛╨▓╨╡╤А╨╡╨╜╨╛ ╨┐╨╛ ╨║╨░╨╝╨╡╤А╨╡)
    if (bars == 1) {
        frame |= (1UL << 12);                         // 1 ╨┤╨╡╨╗╨╡╨╜╨╕╨╡
    } else if (bars == 2) {
        frame |= (1UL << 12) | (1UL << 13);            // 2 ╨┤╨╡╨╗╨╡╨╜╨╕╤П
    } else if (bars == 3) {
        frame |= (1UL << 14);                         // 3 ╨┤╨╡╨╗╨╡╨╜╨╕╤П
    } else if (bars >= 4) {
        frame |= (1UL << 15);                         // 4 ╨┤╨╡╨╗╨╡╨╜╨╕╤П
    }

    // 3. ╨Я╨╕╨║╤В╨╛╨│╤А╨░╨╝╨╝╨░ ╨╖╨░╤А╤П╨┤╨║╨╕ (╨╝╨╛╨╗╨╜╨╕╤П)
    if (icons & FH8016_ICON_LIGHTNING) {
        frame |= (1UL << 17); // ╨С╨╕╤В 17 тАФ ╨╝╨╛╨╗╨╜╨╕╤П
    }

    // 4. ╨д╨░╤А╤Л (RGB) тАФ ╨┐╤А╨╛╨▓╨╡╤А╨╡╨╜╨╛ ╨┐╨╛ ╨║╨░╨╝╨╡╤А╨╡
    if (hl_l == FH8016_COLOR_RED || hl_l == FH8016_COLOR_YELLOW || hl_l == FH8016_COLOR_MAGENTA || hl_l == FH8016_COLOR_WHITE) {
        frame |= (1UL << 20); // ╨Ю╨▒╤Й╨╕╨╣ ╨║╤А╨░╤Б╨╜╤Л╨╣
    }
    if (hl_l == FH8016_COLOR_GREEN || hl_l == FH8016_COLOR_YELLOW || hl_l == FH8016_COLOR_BLUE || hl_l == FH8016_COLOR_CYAN || hl_l == FH8016_COLOR_WHITE) {
        frame |= (1UL << 18); // ╨Э╨╕╨╢╨╜╨╕╨╣ ╨╖╨╡╨╗╤С╨╜╤Л╨╣
    }
    if (hl_r == FH8016_COLOR_GREEN || hl_r == FH8016_COLOR_YELLOW || hl_r == FH8016_COLOR_BLUE || hl_r == FH8016_COLOR_CYAN || hl_r == FH8016_COLOR_WHITE) {
        frame |= (1UL << 19); // ╨Т╨╡╤А╤Е╨╜╨╕╨╣ ╨╖╨╡╨╗╤С╨╜╤Л╨╣
    }
    if (hl_l == FH8016_COLOR_BLUE || hl_l == FH8016_COLOR_CYAN || hl_l == FH8016_COLOR_MAGENTA || hl_l == FH8016_COLOR_WHITE) {
        frame |= (1UL << 22); // ╨Э╨╕╨╢╨╜╨╕╨╣ ╤Б╨╕╨╜╨╕╨╣
    }
    if (hl_r == FH8016_COLOR_BLUE || hl_r == FH8016_COLOR_CYAN || hl_r == FH8016_COLOR_MAGENTA || hl_r == FH8016_COLOR_WHITE) {
        frame |= (1UL << 23); // ╨Т╨╡╤А╤Е╨╜╨╕╨╣ ╤Б╨╕╨╜╨╕╨╣
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

    // Reset: 2000 us LOW (╨▒╨╡╨╖ ╨┐╨░╤А╨░╨╖╨╕╤В╨╜╨╛╨│╨╛ ╨╕╨╝╨┐╤Г╨╗╤М╤Б╨░ ╨┐╨╛╤Б╨╗╨╡ ╤Б╨▒╤А╨╛╤Б╨░)
    set_pin(dev, 0);
    delay_us(2000);

    // 26 data bits, LSB first (╨╜╨░╤З╨╕╨╜╨░╨╡╤В╤Б╤П ╤Б╤А╨░╨╖╤Г ╨┐╨╛╤Б╨╗╨╡ LOW)
    for (int i = 0; i < 26; i++) {
        send_bit(dev, (bits >> i) & 1);
    }

    // ╨Т╨╛╨╖╨▓╤А╨░╤В ╨▓ idle HIGH
    set_pin(dev, 1);
}