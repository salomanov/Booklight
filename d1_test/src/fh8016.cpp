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
    delayMicroseconds(2000);  // RESET — без синк-бита, данные сразу после LOW

    for (int i = 0; i < 26; i++) {
        sendBit((bits26 >> i) & 1);
    }
    setPins(HIGH);
}

void FH8016Driver::setRawBits(uint32_t bits26) {
    _rawBits = bits26;
}

uint32_t FH8016Driver::encodeFrame(uint8_t percent, uint8_t bars, uint8_t icons, fh8016_color_t hl_l, fh8016_color_t hl_r) {
    if (percent == 0 && bars == 0 && icons == 0 && hl_l == FH8016_COLOR_OFF && hl_r == FH8016_COLOR_OFF) {
        return 0; // Полный сон дисплея
    }

    uint32_t frame = 0;

    // 1. Цифры (аппаратный декодер FH8016)
    if (percent >= 100) {
        frame |= (1UL << 7); // Бит 7 зажигает сотни '100'
    } else if (percent > 0) {
        frame |= (percent & 0x7F); // Число 1..99
    }

    // 2. Деления круговой шкалы (проверено по камере)
    if (bars == 1) {
        frame |= (1UL << 12);                         // 1 деление
    } else if (bars == 2) {
        frame |= (1UL << 12) | (1UL << 13);            // 2 деления
    } else if (bars == 3) {
        frame |= (1UL << 14);                         // 3 деления
    } else if (bars >= 4) {
        frame |= (1UL << 15);                         // 4 деления
    }

    // 3. Пиктограмма зарядки (молния)
    if (icons & FH8016_ICON_LIGHTNING) {
        frame |= (1UL << 17); // Бит 17 — молния
    }

    // 4. Фары (RGB) — проверено по камере
    if (hl_l == FH8016_COLOR_RED || hl_l == FH8016_COLOR_YELLOW || hl_l == FH8016_COLOR_MAGENTA || hl_l == FH8016_COLOR_WHITE) {
        frame |= (1UL << 20); // Общий красный
    }
    if (hl_l == FH8016_COLOR_GREEN || hl_l == FH8016_COLOR_YELLOW || hl_l == FH8016_COLOR_BLUE || hl_l == FH8016_COLOR_CYAN || hl_l == FH8016_COLOR_WHITE) {
        frame |= (1UL << 18); // Нижний зелёный
    }
    if (hl_r == FH8016_COLOR_GREEN || hl_r == FH8016_COLOR_YELLOW || hl_r == FH8016_COLOR_BLUE || hl_r == FH8016_COLOR_CYAN || hl_r == FH8016_COLOR_WHITE) {
        frame |= (1UL << 19); // Верхний зелёный
    }
    if (hl_l == FH8016_COLOR_BLUE || hl_l == FH8016_COLOR_CYAN || hl_l == FH8016_COLOR_MAGENTA || hl_l == FH8016_COLOR_WHITE) {
        frame |= (1UL << 22); // Нижний синий
    }
    if (hl_r == FH8016_COLOR_BLUE || hl_r == FH8016_COLOR_CYAN || hl_r == FH8016_COLOR_MAGENTA || hl_r == FH8016_COLOR_WHITE) {
        frame |= (1UL << 23); // Верхний синий
    }

    return frame;
}

void FH8016Driver::setState(uint8_t percent, uint8_t bars, uint8_t icons, fh8016_color_t hl_l, fh8016_color_t hl_r) {
    _rawBits = encodeFrame(percent, bars, icons, hl_l, hl_r);
}

void FH8016Driver::update() {
    sendPacket(_rawBits);
}
