#pragma once
#include <Arduino.h>

// Цвета для RGB фар
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

// Иконки
#define FH8016_ICON_NONE       0x00
#define FH8016_ICON_DROPLET    0x01
#define FH8016_ICON_LIGHTNING  0x02
#define FH8016_ICON_PERCENT    0x04

class FH8016Driver {
public:
    FH8016Driver(const int* pins, int numPins);
    void begin();
    
    // Установка параметров экрана
    void setState(uint8_t percent_0_100, uint8_t bars_0_4, uint8_t icons, fh8016_color_t hl_left, fh8016_color_t hl_right);
    void setRawBits(uint32_t bits26);
    
    // Отправка кадра (вызывать периодически, ~20-50 Гц)
    void update();

private:
    const int* _pins;
    int _numPins;
    uint32_t _rawBits;

    void setPins(int level);
    void sendBit(bool val);
    void sendPacket(uint32_t bits26);
    uint32_t encodeFrame(uint8_t percent, uint8_t bars, uint8_t icons, fh8016_color_t hl_left, fh8016_color_t hl_right);
};
