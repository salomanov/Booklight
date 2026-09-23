#include "py32_board.h"
#include "py32f0xx.h"

// ─── Внутренние переменные ──────────────────────────────────────────────────
static volatile uint32_t _ms = 0;

// Виртуальный сенсор (для теста с ПК)
volatile uint32_t virtual_touch = 0; 

// ─── Обработчики прерываний (ISR) ───────────────────────────────────────────
void SysTick_Handler(void) {
    _ms++;
}

// ─── Реализация API ─────────────────────────────────────────────────────────
void board_init(void) {
    RCC->IOPENR |= RCC_IOPENR_GPIOAEN | RCC_IOPENR_GPIOBEN;
    RCC->APBENR2 |= RCC_APBENR2_TIM1EN;

    // PA0 → TIM1_CH1 (AF2): основной ШИМ-выход на филамент
    GPIOA->MODER = (GPIOA->MODER & ~(3U << 0)) | (2U << 0);
    GPIOA->AFR[0] = (GPIOA->AFR[0] & ~(0xFU << 0)) | (2U << 0);

    // PA5 → TIM1_CH3 (AF2): дублирующий ШИМ-выход (запараллелен с PA0)
    GPIOA->MODER = (GPIOA->MODER & ~(3U << 10)) | (2U << 10);   // PA5 = AF mode
    GPIOA->AFR[0] = (GPIOA->AFR[0] & ~(0xFU << 20)) | (2U << 20); // PA5 AF2 = TIM1_CH3

    // 1 кГц ШИМ (24MHz / 24 / 1000)
    TIM1->PSC = 23;
    TIM1->ARR = 999;
    // CH1: PWM mode 1
    TIM1->CCMR1 = (6U << 4) | TIM_CCMR1_OC1PE;
    // CH3: PWM mode 1
    TIM1->CCMR2 = (6U << 4) | TIM_CCMR2_OC3PE;
    // Enable CH1 + CH3 outputs
    TIM1->CCER = TIM_CCER_CC1E | TIM_CCER_CC3E;
    TIM1->BDTR = TIM_BDTR_MOE;
    TIM1->CR1 = TIM_CR1_CEN;

    // PB4 - Сенсорная кнопка (Input, Pull-down)
    GPIOB->MODER &= ~(3U << 8); 
    GPIOB->PUPDR = (GPIOB->PUPDR & ~(3U << 8)) | (2U << 8); 
    
    // PB5 - Статус зарядки (Input, Pull-up)
    GPIOB->MODER &= ~(3U << 10); 
    GPIOB->PUPDR = (GPIOB->PUPDR & ~(3U << 10)) | (1U << 10);

    SysTick_Config(SystemCoreClock / 1000U);
}

uint16_t board_read_adc(void) {
    // Временно заглушка. Настроим ADC позже, когда будем отвязываться от J-Link.
    return 4000;
}

bool board_read_charge(void) {
    return (GPIOB->IDR & (1U << 5)) == 0; // Active low (0 = заряжается)
}

uint32_t board_millis(void) {
    return _ms;
}

void board_set_pwm_raw(uint16_t pwm) {
    if (pwm > 1000) pwm = 1000;
    TIM1->CCR1 = pwm;  // PA0 — основной канал
    TIM1->CCR3 = pwm;  // PA5 — дублирующий канал
}

bool board_read_touch(void) {
    // Читаем физический пин ИЛИ виртуальный флаг с ПК
    bool phys = (GPIOB->IDR & (1U << 4)) != 0;
    return phys || (virtual_touch != 0);
}
