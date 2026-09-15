#include "fh8016.h"

// 7-сегментная таблица для цифр 0..9 (биты: a, b, c, d, e, f, g)
// Стандартные сегменты: a=0x01, b=0x02, c=0x04, d=0x08, e=0x10, f=0x20, g=0x40
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

FH8016Driver::FH8016Driver(const int* pins, int numPins) 
    : _pins(pins), _numPins(numPins), _rawBits(0) {
}

void FH8016Driver::begin() {
    for (int i = 0; i < _numPins; i++) {
        pinMode(_pins[i], OUTPUT);
        digitalWrite(_pins[i], HIGH);
    }
}

void FH8016Driver::setPins(int level) {
    for (int i = 0; i < _numPins; i++) {
        digitalWrite(_pins[i], level);
    }
}

void FH8016Driver::sendBit(bool val) {
    if (val) {
        setPins(HIGH);
        delayMicroseconds(395);
        setPins(LOW);
        delayMicroseconds(95);
    } else {
        setPins(HIGH);
        delayMicroseconds(95);
        setPins(LOW);
        delayMicroseconds(395);
    }
}

void FH8016Driver::sendPacket(uint32_t bits26) {
    setPins(LOW);
    delayMicroseconds(2000);
    setPins(HIGH);
    delayMicroseconds(100);

    for (int i = 0; i < 26; i++) {
        sendBit((bits26 >> i) & 1);
    }
    setPins(HIGH);
}

void FH8016Driver::setRawBits(uint32_t bits26) {
    _rawBits = bits26;
}

uint32_t FH8016Driver::encodeFrame(uint8_t percent, uint8_t bars, uint8_t icons, fh8016_color_t hl_l, fh8016_color_t hl_r) {
    uint32_t frame = 0;
    
    // Базовая раскладка при 0..100%:
    // Разделение на десятки и единицы
    uint8_t tens = (percent / 10) % 10;
    uint8_t units = percent % 10;
    bool hundreds = (percent >= 100);

    // 1. Кодирование цифр (чередующиеся биты)
    uint8_t seg_t = (percent < 10) ? 0 : DIGIT_7SEG[tens];
    uint8_t seg_u = DIGIT_7SEG[units];

    // Сегменты единиц и десятков
    for (int k = 0; k < 7; k++) {
        if ((seg_u >> k) & 1) frame |= (1UL << (2 * k));
        if ((seg_t >> k) & 1) frame |= (1UL << (2 * k + 1));
    }

    // Старшая единица (100%)
    if (hundreds) {
        frame |= (1UL << 7) | (1UL << 9);
    }

    // 2. 4 деления шкалы (бары вокруг иконки)
    if (bars >= 1) frame |= (1UL << 14); // Bar 1 (нижне-левый)
    if (bars >= 2) frame |= (1UL << 12); // Bar 2 (нижне-правый)
    if (bars >= 3) frame |= (1UL << 17); // Bar 3 (верхне-правый)
    if (bars >= 4) frame |= (1UL << 15); // Bar 4 (верхне-левый)

    // 3. Пиктограммы
    if (icons & FH8016_ICON_DROPLET)   frame |= (1UL << 0);
    if (icons & FH8016_ICON_PERCENT)   frame |= (1UL << 16);
    if (icons & FH8016_ICON_LIGHTNING) frame |= (1UL << 13);

    // 4. Цвета фар (RGB для каждого глаза)
    // Левая фара:
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

    // Правая фара:
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

void FH8016Driver::setState(uint8_t percent, uint8_t bars, uint8_t icons, fh8016_color_t hl_l, fh8016_color_t hl_r) {
    _rawBits = encodeFrame(percent, bars, icons, hl_l, hl_r);
}

void FH8016Driver::update() {
    sendPacket(_rawBits);
}
