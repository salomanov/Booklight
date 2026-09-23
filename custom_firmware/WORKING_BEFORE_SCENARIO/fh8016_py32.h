#ifndef FH8016_PY32_H
#define FH8016_PY32_H

#include "py32f002b_hal.h"
#include <stdint.h>
#include <stdbool.h>

// Headlight RGB Colors
typedef enum {
    FH8016_COLOR_OFF = 0,
    FH8016_COLOR_RED,
    FH8016_COLOR_GREEN,
    FH8016_COLOR_BLUE,
    FH8016_COLOR_CYAN,
    FH8016_COLOR_MAGENTA,
    FH8016_COLOR_YELLOW,
    FH8016_COLOR_WHITE
} fh8016_color_t;

// Indicator Icons
#define FH8016_ICON_NONE       0x00
#define FH8016_ICON_DROPLET    0x01
#define FH8016_ICON_LIGHTNING  0x02
#define FH8016_ICON_PERCENT    0x04

// Driver configuration and state structure
typedef struct {
    GPIO_TypeDef *port;
    uint16_t pin;
    uint32_t raw_frame;
} fh8016_t;

// Initialization
void fh8016_init(fh8016_t *dev, GPIO_TypeDef *port, uint16_t pin);

// High-level state setting
void fh8016_set_state(fh8016_t *dev, uint8_t percent, uint8_t bars, uint8_t icons, 
                      fh8016_color_t hl_left, fh8016_color_t hl_right);

// Direct raw 26-bit frame setting
void fh8016_set_raw(fh8016_t *dev, uint32_t raw_bits26);

// Encode frame from parameters
uint32_t fh8016_encode_frame(uint8_t percent, uint8_t bars, uint8_t icons, 
                             fh8016_color_t hl_left, fh8016_color_t hl_right);

// Transmit current frame over 1-Wire line (call periodically, ~20-50 Hz)
void fh8016_update(fh8016_t *dev);

#endif // FH8016_PY32_H