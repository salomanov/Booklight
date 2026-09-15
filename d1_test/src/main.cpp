#include <Arduino.h>
#include "fh8016.h"

// Пины: D4 (GPIO2), D1 (GPIO5), D2 (GPIO4)
const int PINS[] = {2, 5, 4};
FH8016Driver display(PINS, 3);

const fh8016_color_t COLOR_PALETTE[] = {
    FH8016_COLOR_GREEN,
    FH8016_COLOR_CYAN,
    FH8016_COLOR_BLUE,
    FH8016_COLOR_MAGENTA,
    FH8016_COLOR_RED,
    FH8016_COLOR_YELLOW,
    FH8016_COLOR_WHITE
};
const int NUM_COLORS = 7;
const char* COLOR_NAMES[] = {"GREEN", "CYAN", "BLUE", "MAGENTA", "RED", "YELLOW", "WHITE"};

int currentPercent = 0;
int percentStep = 1;
int currentBar = 1;
int colorIdx = 0;
bool lightningOn = false;
bool isPaused = false;
bool autoAnim = true;

unsigned long lastSecTick = 0;
unsigned long lastBlinkTick = 0;

void applyDisplayState() {
    uint8_t icons = FH8016_ICON_PERCENT;
    if (lightningOn) icons |= FH8016_ICON_LIGHTNING;
    fh8016_color_t curColor = COLOR_PALETTE[colorIdx];
    display.setState(currentPercent, currentBar, icons, curColor, curColor);
}

void setup() {
    Serial.begin(115200);
    display.begin();
    display.setRawBits(0);
    display.update();
    Serial.println("\nFH8016_READY");
}

void loop() {
    while (Serial.available()) {
        String cmd = Serial.readStringUntil('\n');
        cmd.trim();
        if (cmd.length() > 0) {
            if (cmd == "ANIM") {
                autoAnim = true;
                isPaused = false;
                applyDisplayState();
                Serial.println("OK ANIM");
            } else if (cmd == "STOP") {
                autoAnim = false;
                display.setRawBits(0);
                display.update();
                Serial.println("OK STOP");
            } else if (cmd == "p") {
                isPaused = !isPaused;
                Serial.printf("OK PAUSE %d\n", isPaused);
            } else if (cmd.startsWith("s ")) {
                percentStep = cmd.substring(2).toInt();
                Serial.printf("OK STEP %d\n", percentStep);
            } else if (cmd.startsWith("H ")) {
                autoAnim = false;
                uint32_t raw = strtoul(cmd.substring(2).c_str(), NULL, 16);
                display.setRawBits(raw);
                display.update();
                Serial.printf("OK H 0x%08X\n", raw);
            } else if (cmd.startsWith("SET ")) {
                autoAnim = false;
                int p = 0, b = 0;
                sscanf(cmd.c_str(), "SET %d %d", &p, &b);
                currentPercent = p;
                currentBar = b;
                applyDisplayState();
                display.update();
                Serial.printf("OK SET %d %d\n", p, b);
            } else {
                autoAnim = false;
                uint32_t raw = strtoul(cmd.c_str(), NULL, 16);
                display.setRawBits(raw);
                display.update();
                Serial.printf("OK H 0x%08X\n", raw);
            }
        }
    }

    if (autoAnim && !isPaused) {
        unsigned long now = millis();
        if (now - lastBlinkTick >= 500) {
            lastBlinkTick = now;
            lightningOn = !lightningOn;
            applyDisplayState();
        }
        if (now - lastSecTick >= 1000) {
            lastSecTick = now;
            currentPercent = (currentPercent + percentStep) % 101;
            currentBar = (currentBar % 4) + 1;
            colorIdx = (colorIdx + 1) % NUM_COLORS;
            applyDisplayState();
            Serial.printf("[TICK] %3d%% | Bar: %d/4 | Lightning: %s | Headlights: %s\n",
                          currentPercent, currentBar, lightningOn ? "ON" : "OFF", COLOR_NAMES[colorIdx]);
        }
    }

    display.update();
    delay(20);
}
