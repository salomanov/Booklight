#include <Arduino.h>
#include <ESP8266WiFi.h>
#include "fh8016.h"

#include <SettingsESP.h>

// =============================================================================
// Конфигурация Wi-Fi
// =============================================================================
#define WIFI_SSID "Salomanov"
#define WIFI_PASS "salomanov"

// =============================================================================
// Дисплей вейпа (FH8016)
// Пины: D4 (GPIO2), D1 (GPIO5), D2 (GPIO4)
// =============================================================================
const int PINS[] = {2, 5, 4};
FH8016Driver display(PINS, 3);

// =============================================================================
// Веб-интерфейс Gyver Settings
// =============================================================================
SettingsESP sett("BookLight");

// =============================================================================
// Переменные состояния фонарика и аккумулятора
// =============================================================================
bool lampOn = true;                     // Состояние лампы: ВКЛ / ВЫКЛ
int  lampBrightness = 70;              // Яркость нити лампы: 5..100%
int  batteryPercent = 85;              // Заряд АКБ: 0..100%
bool isCharging = false;               // Подключение зарядки USB-C (5V VBUS)
bool deepSleep = false;                // Режим глубокого сна (STOP mode)
bool autoCycle = false;                // Демо-режим (авто-прогон процентов)

// Вспомогательные переменные для диммирования и анимаций
bool isDimming = false;
int  dimDirection = 1;                 // +1 или -1
uint32_t showBrightnessUntil = 0;      // Таймер показа % яркости на экране
uint32_t lastSimTick = 0;              // Таймер демо-цикла
int simStep = 1;

// Текущие вычисленные значения для индикаторов и экрана
uint8_t currentBars = 0;
sets::Colors currentEyeWebColor = sets::Colors::Green;
bool lightningLit = false;

// =============================================================================
// Логика пересчёта состояния дисплея и светодиодов
// =============================================================================
void calculateState() {
    uint32_t now = millis();

    // 1. Если глубокий сон или лампа выключена (и нет зарядки) — всё выключено
    if (deepSleep || (!lampOn && !isCharging)) {
        currentBars = 0;
        lightningLit = false;
        currentEyeWebColor = sets::Colors::Black;
        return;
    }

    // 2. Что отображается числом: яркость при диммировании или заряд АКБ
    uint8_t dispVal = (now < showBrightnessUntil) ? lampBrightness : batteryPercent;

    // 3. Деления круговой шкалы по ТЗ:
    //  0..20%:  0 делений
    // 21..40%:  1 деление
    // 41..60%:  2 деления
    // 61..80%:  3 деления
    // 81..100%: 4 деления
    if (dispVal >= 81)      currentBars = 4;
    else if (dispVal >= 61) currentBars = 3;
    else if (dispVal >= 41) currentBars = 2;
    else if (dispVal >= 21) currentBars = 1;
    else                    currentBars = 0;

    // 4. Моргание молнии при зарядке (такт 500 мс)
    if (isCharging) {
        lightningLit = ((now / 500) % 2) != 0;
    } else {
        lightningLit = false;
    }

    // 5. Цвет фар:
    if (isCharging || now < showBrightnessUntil) {
        currentEyeWebColor = sets::Colors::Aqua; // Бирюзовый / Электрик
    } else {
        if (batteryPercent >= 100) {
            currentEyeWebColor = sets::Colors::Blue;
        } else if (batteryPercent >= 67) {
            currentEyeWebColor = sets::Colors::Green;
        } else if (batteryPercent >= 34) {
            currentEyeWebColor = sets::Colors::Yellow;
        } else if (batteryPercent >= 15) {
            currentEyeWebColor = sets::Colors::Red;
        } else {
            // Критический разряд (< 15%): моргающий красный
            currentEyeWebColor = ((now / 300) % 2) ? sets::Colors::Red : sets::Colors::Black;
        }
    }
}

// Отправка кадра на физический экран вейпа
void updatePhysicalDisplay() {
    uint32_t now = millis();

    if (deepSleep || (!lampOn && !isCharging)) {
        display.setRawBits(0);
        display.update();
        return;
    }

    uint8_t dispVal = (now < showBrightnessUntil) ? lampBrightness : batteryPercent;
    uint8_t icons = FH8016_ICON_PERCENT;
    if (lightningLit) {
        icons |= FH8016_ICON_LIGHTNING;
    }

    fh8016_color_t eyeColor;
    if (isCharging || now < showBrightnessUntil) {
        eyeColor = FH8016_COLOR_CYAN;
    } else {
        if (batteryPercent >= 100) {
            eyeColor = FH8016_COLOR_BLUE;
        } else if (batteryPercent >= 67) {
            eyeColor = FH8016_COLOR_GREEN;
        } else if (batteryPercent >= 34) {
            eyeColor = FH8016_COLOR_YELLOW;
        } else if (batteryPercent >= 15) {
            eyeColor = FH8016_COLOR_RED;
        } else {
            eyeColor = ((now / 300) % 2) ? FH8016_COLOR_RED : FH8016_COLOR_OFF;
        }
    }

    display.setState(dispVal, currentBars, icons, eyeColor, eyeColor);
    display.update();
}

// =============================================================================
// Билдер веб-панели Gyver Settings
// =============================================================================
void build(sets::Builder& b) {
    calculateState();

    // --- СЕКЦИЯ 1: СЕНСОРНАЯ КНОПКА И УПРАВЛЕНИЕ ЛАМПОЙ ---
    {
        sets::Group g(b, "Сенсорная кнопка (Touch Button)");

        if (b.beginButtons()) {
            if (b.Button("Короткий клик (ВКЛ / ВЫКЛ)")) {
                deepSleep = false;
                lampOn = !lampOn;
            }
            b.endButtons();
        }

        if (b.ButtonHold("Удержание кнопки (Диммирование)")) {
            deepSleep = false;
            if (b.build.pressed()) {
                isDimming = true;
            } else {
                isDimming = false;
                dimDirection = -dimDirection; // Меняем направление при следующем удержании
            }
        }

        b.Switch("Лампа включена", &lampOn);
        b.Slider("Яркость нити лампы", 5, 100, 1, "%", &lampBrightness);
    }

    // --- СЕКЦИЯ 2: СВЕТОДИОДЫ И ИНДИКАЦИЯ (WIDGETS LED) ---
    {
        sets::Group g(b, "Индикация и светодиоды (Виджеты LED)");

        b.LED("Нить лампы (3V Filament)", lampOn && !deepSleep, sets::Colors::Gray, sets::Colors::Orange);
        b.LED("Левая фара (Глаз L)", (lampOn || isCharging) && !deepSleep, sets::Colors::Black, currentEyeWebColor);
        b.LED("Правая фара (Глаз R)", (lampOn || isCharging) && !deepSleep, sets::Colors::Black, currentEyeWebColor);
        b.LED("Молния (Зарядка)", lightningLit && !deepSleep, sets::Colors::Gray, sets::Colors::Aqua);
        b.LED("Капля (Экран активен)", (lampOn || isCharging) && !deepSleep, sets::Colors::Gray, sets::Colors::Blue);

        b.LED("Шкала 1 (21-40%)", currentBars >= 1 && !deepSleep, sets::Colors::Gray, sets::Colors::Green);
        b.LED("Шкала 2 (41-60%)", currentBars >= 2 && !deepSleep, sets::Colors::Gray, sets::Colors::Green);
        b.LED("Шкала 3 (61-80%)", currentBars >= 3 && !deepSleep, sets::Colors::Gray, sets::Colors::Green);
        b.LED("Шкала 4 (81-100%)", currentBars >= 4 && !deepSleep, sets::Colors::Gray, sets::Colors::Green);
    }

    // --- СЕКЦИЯ 3: ПИТАНИЕ И АККУМУЛЯТОР ---
    {
        sets::Group g(b, "Питание и аккумулятор");

        b.Switch("USB-C Зарядка (VBUS)", &isCharging);
        b.Slider("Уровень заряда АКБ", 0, 100, 1, "%", &batteryPercent);
        b.Switch("Авто-цикл (Демо разряд / заряд)", &autoCycle);

        if (b.beginButtons()) {
            if (b.Button("100% (Синий)")) {
                batteryPercent = 100;
                deepSleep = false;
            }
            if (b.Button("50% (Жёлтый)")) {
                batteryPercent = 50;
                deepSleep = false;
            }
            if (b.Button("10% (Красный blink)")) {
                batteryPercent = 10;
                deepSleep = false;
            }
            if (b.Button("Сон (STOP)")) {
                deepSleep = true;
                lampOn = false;
                isCharging = false;
            }
            b.endButtons();
        }
    }
}

// =============================================================================
// SETUP
// =============================================================================
void setup() {
    Serial.begin(115200);
    Serial.println();
    Serial.println("========================================");
    Serial.println("   BOOKLIGHT TESTBED WITH GYVER SETTINGS");
    Serial.println("========================================");

    // 1. Инициализация дисплея вейпа
    display.begin();
    display.setRawBits(0);
    display.update();

    // 2. Подключение к WiFi
    Serial.printf("Подключение к Wi-Fi '%s'...\n", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASS);

    uint8_t tries = 25;
    while (WiFi.status() != WL_CONNECTED && tries > 0) {
        delay(500);
        Serial.print(".");
        tries--;
    }
    Serial.println();

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println(">>> УСПЕШНО ПОДКЛЮЧЕНО К WI-FI! <<<");
        Serial.print(">>> IP-адрес платы: http://");
        Serial.println(WiFi.localIP());
        Serial.println(">>> Также доступно по адресу: http://booklight.local");
    } else {
        Serial.println("[-] Не удалось подключиться к роутеру, запускаю точку доступа BookLight-AP...");
        WiFi.mode(WIFI_AP);
        WiFi.softAP("BookLight-AP");
        Serial.print(">>> IP точки доступа: http://");
        Serial.println(WiFi.softAPIP());
    }

    // 3. Запуск веб-интерфейса Gyver Settings
    sett.begin(true, "booklight");
    sett.onBuild(build);

    Serial.println("Веб-интерфейс Gyver Settings готов к работе!");
    Serial.println("========================================");
}

// =============================================================================
// LOOP
// =============================================================================
void loop() {
    uint32_t now = millis();

    // 1. Обработка веб-сервера Gyver Settings
    sett.tick();

    // 2. Диммирование во время удержания виртуальной кнопки тач
    static uint32_t lastDimTick = 0;
    if (isDimming && lampOn && !deepSleep) {
        if (now - lastDimTick >= 25) { // шаг каждые 25 мс
            lastDimTick = now;
            lampBrightness += dimDirection;
            if (lampBrightness >= 100) {
                lampBrightness = 100;
                dimDirection = -1;
            } else if (lampBrightness <= 5) {
                lampBrightness = 5;
                dimDirection = 1;
            }
            showBrightnessUntil = now + 1500; // на 1.5 сек показываем яркость на экране
        }
    }

    // 3. Авто-цикл симуляции (если включен)
    if (autoCycle && (now - lastSimTick >= 800)) {
        lastSimTick = now;
        batteryPercent += simStep;
        if (batteryPercent >= 100) {
            batteryPercent = 100;
            simStep = -2; // Разряжаемся
        } else if (batteryPercent <= 5) {
            batteryPercent = 5;
            simStep = 2;  // Заряжаемся
        }
    }

    // 4. Обновление физического экрана вейпа каждые 30 мс
    static uint32_t lastDispUpdate = 0;
    if (now - lastDispUpdate >= 30) {
        lastDispUpdate = now;
        calculateState();
        updatePhysicalDisplay();
    }
}

