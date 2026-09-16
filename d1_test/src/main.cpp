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
// Опциональный физический сенсор: D5 (GPIO14)
// =============================================================================
const int PINS[] = {2, 5, 4};
FH8016Driver display(PINS, 3);
#define TOUCH_PIN 14 // GPIO14 (D5)

// =============================================================================
// Веб-интерфейс Gyver Settings
// =============================================================================
SettingsESP sett("BookLight");

// =============================================================================
// Состояния системы по ТЗ пользователя
// =============================================================================
enum LampState {
    STATE_SLEEP = 0,             // Полный сон: нить выкл, дисплей выкл
    STATE_AWAKE_BATTERY,         // Проснулись по удержанию >1.5с: нить выкл, дисплей показывает % АКБ (5 сек)
    STATE_RAMPING_UP,            // Удержание: нить плавно прибавляет яркость 0..100%, дисплей показывает % яркости
    STATE_HOLD_BRIGHTNESS_WAIT,  // Отпустили кнопку: яркость зафиксирована, дисплей ждёт 3 сек перед сном
    STATE_READING,               // Режим чтения: нить светит, дисплей ПОЛНОСТЬЮ ВЫКЛЮЧЕН (не слепит)
    STATE_RAMPING_DOWN,          // Удержание во время чтения: яркость убавляется до 0, дисплей показывает % яркости
    STATE_ZERO_WAIT,             // Яркость убавлена до 0: дисплей показывает 00%, ждём 3 сек и уходим в STATE_SLEEP
    STATE_AUTO_FADING            // 15 минут прошло: 60 сек плавное угасание нити до нуля. Одиночный клик отменяет!
};

LampState state = STATE_SLEEP;

// Переменные яркости и батареи
float currentBrightness = 0.0f;        // Текущая яркость нити: 0..100%
float savedBrightness = 70.0f;         // Запомненная выбранная яркость
int   batteryPercent = 85;             // Заряд аккумулятора: 0..100%
bool  isCharging = false;              // Подключен кабель USB-C (5V VBUS)

// Таймеры
uint32_t pressStartTime = 0;           // Время начала нажатия кнопки
bool     btnPressed = false;           // Флаг зажатия кнопки
uint32_t stateTimer = 0;               // Универсальный таймер состояний
uint32_t lastRampTick = 0;             // Таймер плавного шага диммирования
uint32_t readingStartTime = 0;         // Время непрерывного чтения (для 15 минут)
uint32_t autoFadeStartTime = 0;        // Время старта 60-сек угасания
float    autoFadeStartBrightness = 0;  // Начальная яркость при угасании

// Настройки времени
const uint32_t HOLD_TO_WAKE_MS          = 1500;                 // 1.5 секунды защита от случайного нажатия
const uint32_t AWAKE_BATTERY_TIMEOUT_MS = 5000;                 // 5 сек показ батареи перед сном
const uint32_t DISP_OFF_DELAY_MS        = 3000;                 // 3 сек задержка выключения дисплея
const uint32_t INACTIVITY_TIMEOUT_MS    = (15UL * 60UL * 1000); // 15 минут бездействия
const uint32_t FADEOUT_DURATION_MS      = (60UL * 1000);        // 60 секунд на плавное угасание

// =============================================================================
// Обработка кнопки Touch (как виртуальной в Web, так и физической на D5)
// =============================================================================
void onTouchDown() {
    pressStartTime = millis();
    btnPressed = true;

    // Если шло 60-секундное угасание (автоотключение) — короткий клик отменяет его!
    if (state == STATE_AUTO_FADING) {
        state = STATE_READING;
        currentBrightness = savedBrightness;
        readingStartTime = millis(); // сброс 15-минутного таймера
        return;
    }

    // Если были в режиме ожидания батареи (проснулись) — нажатие начинает прибавление яркости
    if (state == STATE_AWAKE_BATTERY) {
        state = STATE_RAMPING_UP;
        currentBrightness = 0.0f;
        lastRampTick = millis();
        return;
    }

    // Если лампа светит в режиме чтения — нажатие начинает убавление яркости
    if (state == STATE_READING || state == STATE_HOLD_BRIGHTNESS_WAIT) {
        state = STATE_RAMPING_DOWN;
        lastRampTick = millis();
        return;
    }
}

void onTouchUp() {
    uint32_t duration = millis() - pressStartTime;
    btnPressed = false;

    // 1. Были в режиме набора яркости — фиксируем выбранный уровень!
    if (state == STATE_RAMPING_UP) {
        if (currentBrightness > 0.0f) {
            savedBrightness = currentBrightness;
            state = STATE_HOLD_BRIGHTNESS_WAIT;
            stateTimer = millis(); // 3 секунды показ перед сном дисплея
        } else {
            state = STATE_SLEEP;
        }
        return;
    }

    // 2. Были в режиме убавления яркости
    if (state == STATE_RAMPING_DOWN) {
        if (currentBrightness > 0.0f) {
            savedBrightness = currentBrightness;
            state = STATE_HOLD_BRIGHTNESS_WAIT;
            stateTimer = millis();
        } else {
            // Убавили до нуля: ждём 3 секунды и уходим в сон
            state = STATE_ZERO_WAIT;
            stateTimer = millis();
        }
        return;
    }
}

// =============================================================================
// Обновление состояния физического дисплея вейпа и расчёт индикации
// =============================================================================
void updateDisplayHardware() {
    uint32_t now = millis();

    // 1. Режим зарядки USB-C: дисплей горит ПОСТОЯННО, полная гирлянда, молния мигает
    if (isCharging) {
        uint8_t bars = 0;
        if (batteryPercent >= 81)      bars = 4;
        else if (batteryPercent >= 61) bars = 3;
        else if (batteryPercent >= 41) bars = 2;
        else if (batteryPercent >= 21) bars = 1;

        uint8_t icons = FH8016_ICON_PERCENT;
        if ((now / 500) % 2) {
            icons |= FH8016_ICON_LIGHTNING; // мигающая молния
        }

        fh8016_color_t eye = FH8016_COLOR_CYAN;
        if (batteryPercent >= 100) eye = FH8016_COLOR_BLUE;

        display.setState(batteryPercent, bars, icons, eye, eye);
        display.update();
        return;
    }

    // 2. Режим сна: дисплей ПОЛНОСТЬЮ ВЫКЛЮЧЕН
    if (state == STATE_SLEEP) {
        display.setRawBits(0);
        display.update();
        return;
    }

    // 3. Режим чтения или авто-угасания: дисплей ВЫКЛЮЧЕН (не слепит в темноте)!
    if (state == STATE_READING || state == STATE_AUTO_FADING) {
        // Контроль низкого заряда (< 10%): фары РЕДКО моргают красным цветом!
        // Вспышка 150 мс каждые 3.5 секунды, цифры выключены
        if (batteryPercent < 10) {
            bool blink = (now % 3500) < 150;
            if (blink) {
                // Вспыхивают только красные фары, без цифр
                uint32_t frame = (1UL << 20); // Бит 20 — красный цвет фар
                display.setRawBits(frame);
            } else {
                display.setRawBits(0);
            }
        } else {
            display.setRawBits(0);
        }
        display.update();
        return;
    }

    // 4. Показ уровня заряда АКБ (после пробуждения по длинному нажатию)
    if (state == STATE_AWAKE_BATTERY) {
        uint8_t bars = 0;
        if (batteryPercent >= 81)      bars = 4;
        else if (batteryPercent >= 61) bars = 3;
        else if (batteryPercent >= 41) bars = 2;
        else if (batteryPercent >= 21) bars = 1;

        fh8016_color_t eye = FH8016_COLOR_GREEN;
        if (batteryPercent >= 100) eye = FH8016_COLOR_BLUE;
        else if (batteryPercent >= 67) eye = FH8016_COLOR_GREEN;
        else if (batteryPercent >= 34) eye = FH8016_COLOR_YELLOW;
        else eye = FH8016_COLOR_RED;

        display.setState(batteryPercent, bars, FH8016_ICON_PERCENT, eye, eye);
        display.update();
        return;
    }

    // 5. Настройка яркости (RAMPING_UP, RAMPING_DOWN, HOLD_BRIGHTNESS_WAIT, ZERO_WAIT)
    // На дисплее отображается % текущей яркости нити!
    uint8_t dispBrightness = (uint8_t)round(currentBrightness);
    uint8_t bars = 0;
    if (dispBrightness >= 81)      bars = 4;
    else if (dispBrightness >= 61) bars = 3;
    else if (dispBrightness >= 41) bars = 2;
    else if (dispBrightness >= 21) bars = 1;

    fh8016_color_t eye = (state == STATE_ZERO_WAIT) ? FH8016_COLOR_RED : FH8016_COLOR_CYAN;
    display.setState(dispBrightness, bars, FH8016_ICON_PERCENT, eye, eye);
    display.update();
}

// =============================================================================
// Главный конечный автомат (State Machine)
// =============================================================================
void updateStateMachine() {
    uint32_t now = millis();

    // 1. Проверка удержания кнопки в режиме сна (> 1.5 сек для пробуждения)
    if (state == STATE_SLEEP && btnPressed) {
        if (now - pressStartTime >= HOLD_TO_WAKE_MS) {
            state = STATE_AWAKE_BATTERY;
            stateTimer = now;
            currentBrightness = 0.0f; // Подсветка пока НЕ включена!
        }
    }

    // 2. В режиме показа батареи: если пользователь не нажал за 5 сек — уходим в сон
    if (state == STATE_AWAKE_BATTERY) {
        if (!btnPressed && (now - stateTimer >= AWAKE_BATTERY_TIMEOUT_MS)) {
            state = STATE_SLEEP;
        }
    }

    // 3. Плавный набор яркости с нуля (пока кнопка удерживается)
    if (state == STATE_RAMPING_UP && btnPressed) {
        if (now - lastRampTick >= 25) { // +1% каждые 25 мс (~2.5 сек на 0..100%)
            lastRampTick = now;
            if (currentBrightness < 100.0f) {
                currentBrightness += 1.0f;
                if (currentBrightness > 100.0f) currentBrightness = 100.0f;
            }
        }
    }

    // 4. Ожидание 3 секунды после настройки яркости перед отключением дисплея
    if (state == STATE_HOLD_BRIGHTNESS_WAIT) {
        if (now - stateTimer >= DISP_OFF_DELAY_MS) {
            state = STATE_READING;
            readingStartTime = now; // Запуск 15-минутного таймера чтения
        }
    }

    // 5. Плавное убавление яркости до нуля (пока кнопка удерживается во время чтения)
    if (state == STATE_RAMPING_DOWN && btnPressed) {
        if (now - lastRampTick >= 25) {
            lastRampTick = now;
            if (currentBrightness > 0.0f) {
                currentBrightness -= 1.0f;
                if (currentBrightness < 0.0f) currentBrightness = 0.0f;
            }
        }
    }

    // 6. Если яркость дошла до нуля — ждём 3 секунды и выключаем лампу в сон
    if (state == STATE_ZERO_WAIT) {
        if (now - stateTimer >= DISP_OFF_DELAY_MS) {
            state = STATE_SLEEP;
            currentBrightness = 0.0f;
        }
    }

    // 7. Таймер 15 минут чтения без касаний -> запуск 60-секундного угасания
    if (state == STATE_READING) {
        if (now - readingStartTime >= INACTIVITY_TIMEOUT_MS) {
            state = STATE_AUTO_FADING;
            autoFadeStartTime = now;
            autoFadeStartBrightness = currentBrightness;
        }
    }

    // 8. 60-секундное плавное угасание яркости до 0
    if (state == STATE_AUTO_FADING) {
        uint32_t elapsed = now - autoFadeStartTime;
        if (elapsed >= FADEOUT_DURATION_MS) {
            currentBrightness = 0.0f;
            state = STATE_SLEEP;
        } else {
            float remainRatio = (float)(FADEOUT_DURATION_MS - elapsed) / (float)FADEOUT_DURATION_MS;
            currentBrightness = autoFadeStartBrightness * remainRatio;
        }
    }
}

// =============================================================================
// Билдер веб-панели Gyver Settings
// =============================================================================
const char* getStateName() {
    switch (state) {
        case STATE_SLEEP:                return "💤 СОН (Лампа и экран выкл)";
        case STATE_AWAKE_BATTERY:        return "🔋 ПОКАЗ ЗАРЯДА АКБ (Нить выкл)";
        case STATE_RAMPING_UP:           return "📈 НАБОР ЯРКОСТИ (0..100%)";
        case STATE_HOLD_BRIGHTNESS_WAIT: return "⏳ ЯРКОСТЬ ВЫБРАНА (Экран гаснет через 3с)";
        case STATE_READING:              return "📖 РЕЖИМ ЧТЕНИЯ (Экран выкл, нить светит)";
        case STATE_RAMPING_DOWN:         return "📉 УБАВЛЕНИЕ ЯРКОСТИ (До 0 = выкл)";
        case STATE_ZERO_WAIT:            return "🌑 ЯРКОСТЬ 0 (Выключение через 3с)";
        case STATE_AUTO_FADING:          return "⏱ 15 МИН: УГАСАНИЕ ЗА 60 СЕК (Клик отменяет!)";
        default:                         return "—";
    }
}

void build(sets::Builder& b) {
    // --- ГРУППА 1: СТАТУС И СЕНСОРНАЯ КНОПКА ---
    {
        sets::Group g(b, "Сенсорное управление (Touch Button)");

        b.Label("Текущий режим", getStateName());

        // Главная кнопка с удержанием
        if (b.ButtonHold("СЕНСОРНАЯ КНОПКА (Зажать / Отпустить)")) {
            if (b.build.pressed()) {
                onTouchDown();
            } else {
                onTouchUp();
            }
        }

        if (b.beginButtons()) {
            if (b.Button("Короткий клик [Отмена угасания]")) {
                onTouchDown();
                delay(100);
                onTouchUp();
            }
            if (b.Button("Зажать на 2 сек [Пробуждение]")) {
                onTouchDown();
                // Эмуляция удержания > 1.5 сек
                state = STATE_AWAKE_BATTERY;
                stateTimer = millis();
                btnPressed = false;
            }
            b.endButtons();
        }
    }

    // --- ГРУППА 2: ИНДИКАЦИЯ И СВЕТОДИОДЫ ---
    {
        sets::Group g(b, "Индикация и светодиоды (Виджеты LED)");

        b.LED("Нить лампы (3V Filament)", currentBrightness > 0, sets::Colors::Gray, sets::Colors::Orange);
        b.LabelNum("Яркость нити лампы", (int)round(currentBrightness));

        bool dispActive = (isCharging || state == STATE_AWAKE_BATTERY || state == STATE_RAMPING_UP || 
                           state == STATE_HOLD_BRIGHTNESS_WAIT || state == STATE_RAMPING_DOWN || state == STATE_ZERO_WAIT);
        
        b.LED("Дисплей активен", dispActive, sets::Colors::Gray, sets::Colors::Blue);

        // Индикация фар
        sets::Colors eyeCol = sets::Colors::Black;
        if (isCharging) {
            eyeCol = (batteryPercent >= 100) ? sets::Colors::Blue : sets::Colors::Aqua;
        } else if (state == STATE_READING && batteryPercent < 10) {
            eyeCol = ((millis() % 3500) < 150) ? sets::Colors::Red : sets::Colors::Black;
        } else if (dispActive) {
            if (state == STATE_AWAKE_BATTERY) {
                if (batteryPercent >= 100) eyeCol = sets::Colors::Blue;
                else if (batteryPercent >= 67) eyeCol = sets::Colors::Green;
                else if (batteryPercent >= 34) eyeCol = sets::Colors::Yellow;
                else eyeCol = sets::Colors::Red;
            } else {
                eyeCol = sets::Colors::Aqua;
            }
        }

        b.LED("Фары RGB", dispActive || (state == STATE_READING && batteryPercent < 10), sets::Colors::Black, eyeCol);
        b.LED("Молния (Зарядка)", isCharging && ((millis() / 500) % 2), sets::Colors::Gray, sets::Colors::Aqua);
    }

    // --- ГРУППА 3: ПИТАНИЕ И ТЕСТОВЫЕ СЦЕНАРИИ ---
    {
        sets::Group g(b, "Аккумулятор и тестовые сценарии");

        b.Switch("USB-C Зарядка (Кабель подключен)", &isCharging);
        b.Slider("Заряд аккумулятора", 0, 100, 1, "%", &batteryPercent);

        if (b.beginButtons()) {
            if (b.Button("Тест: АКБ 8% (Редкий красный blink)")) {
                batteryPercent = 8;
            }
            if (b.Button("Тест: 15 минут прошло (Запустить 60с угасание)")) {
                if (currentBrightness > 0) {
                    state = STATE_AUTO_FADING;
                    autoFadeStartTime = millis();
                    autoFadeStartBrightness = currentBrightness;
                }
            }
            if (b.Button("Выключить в сон (STOP)")) {
                state = STATE_SLEEP;
                currentBrightness = 0.0f;
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
    Serial.println("   BOOKLIGHT: ПОЛНЫЙ СЦЕНАРИЙ ФОНАРИКА  ");
    Serial.println("========================================");

    // 1. Инициализация дисплея
    display.begin();
    display.setRawBits(0);
    display.update();

    // 2. Инициализация физического пина сенсора
    pinMode(TOUCH_PIN, INPUT_PULLDOWN_16);

    // 3. Подключение к Wi-Fi
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
        Serial.println(">>> Локальный адрес: http://booklight.local");
    } else {
        Serial.println("[-] Запускаю точку доступа BookLight-AP...");
        WiFi.mode(WIFI_AP);
        WiFi.softAP("BookLight-AP");
        Serial.print(">>> IP точки доступа: http://");
        Serial.println(WiFi.softAPIP());
    }

    // 4. Запуск веб-сервера Gyver Settings
    sett.begin(true, "booklight");
    sett.onBuild(build);

    Serial.println("Система готова! Устройство в режиме сна (STATE_SLEEP).");
    Serial.println("Зажмите кнопку на 1.5 сек для пробуждения.");
    Serial.println("========================================");
}

// =============================================================================
// LOOP
// =============================================================================
void loop() {
    // 1. Обработка веб-сервера
    sett.tick();

    // 2. Опрос физической кнопки на пине D5 (GPIO14)
    static bool lastPhysicalTouch = false;
    bool physicalTouch = digitalRead(TOUCH_PIN);
    if (physicalTouch != lastPhysicalTouch) {
        lastPhysicalTouch = physicalTouch;
        if (physicalTouch) {
            onTouchDown();
        } else {
            onTouchUp();
        }
    }

    // 3. Автомат состояний
    updateStateMachine();

    // 4. Обновление физического экрана вейпа (~35 Гц)
    static uint32_t lastDispUpdate = 0;
    if (millis() - lastDispUpdate >= 30) {
        lastDispUpdate = millis();
        updateDisplayHardware();
    }
}


