# Graph Report - ВЕЙП  (2026-09-23)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 2425 nodes · 5759 edges · 89 communities (71 shown, 18 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 528 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `78d4f622`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- cmsis_gcc.h
- cmsis_armclang_ltm.h
- py32f002b_hal_tim.c
- __DSB
- py32f002b_hal_i2c.c
- py32f002b_hal
- cmsis_armclang.h
- cmsis_iccarm.h
- core_cm85.h
- py32f002b_hal_adc.c
- py32f002b_hal_lptim.c
- py32f002b_hal_spi.c
- py32f002b_hal_uart.c
- py32f002b_hal_tim_ex.c
- core_armv81mml.h
- core_cm55.h
- core_armv8mml.h
- core_cm33.h
- core_cm35p.h
- py32f002b_hal_usart.c
- core_armv8mbl.h
- core_cm23.h
- HAL_GPIO_Init
- stdint
- HAL_IncTick
- py32f002b_hal_flash.c
- py32f002b_hal.c
- FH8016Driver
- sys
- BookLightStudioWindow
- cmsis_armcc.h
- core_sc300.h
- core_cm3.h
- core_cm4.h
- core_cm7.h
- py32f002b_hal_def.h
- custom_firmware/py32f002b_it.c
- booklight_studio.py
- WORKING_BEFORE_SCENARIO/book_light.c
- py32f002b_hal_comp.c
- main
- FH8016DisplayWidget
- MainWindow
- main
- digit_counter/charlie.c
- main
- core_cm0.h
- core_cm1.h
- .__init__
- os
- core_cm0plus.h
- py32f002b_hal_cortex.c
- core_sc000.h
- pmu_armv8.h
- book_light_loop
- custom_firmware/charlie.c
- book_light_init
- py32f002b_bsp_printf.c
- py32f002b_hal_exti.c
- custom_firmware/book_light.c
- stdbool
- custom_firmware/fh8016_py32.c
- py32f002b_hal_crc.c
- py32f002b_hal_pwr.c
- enter_deep_sleep
- cmsis_compiler.h
- gyver_led.c
- digit_counter/py32f002b_it.c
- fet_measure/py32f002b_it.c
- fet_pwm/py32f002b_it.c
- gyver_timer.h
- __PACKED_STRUCT
- __PACKED_STRUCT
- __ROR
- system_py32f002b.c
- T_UINT32
- T_UINT32
- py32f002b_hal.h
- fh8016_t

## God Nodes (most connected - your core abstractions)
1. `__DSB()` - 95 edges
2. `__ISB()` - 74 edges
3. `HAL_GetTick()` - 45 edges
4. `HAL_GPIO_Init()` - 32 edges
5. `BookLightStudioWindow` - 31 edges
6. `TIM_CCxChannelCmd()` - 28 edges
7. `HAL_GPIO_WritePin()` - 25 edges
8. `TIM_CCxNChannelCmd()` - 18 edges
9. `HAL_IncTick()` - 18 edges
10. `FH8016DisplayWidget` - 17 edges

## Surprising Connections (you probably didn't know these)
- `init_gpio()` --calls--> `HAL_GPIO_Init()`  [INFERRED]
  custom_firmware/book_light.c → py32c642_vape/Libraries/PY32F002B_HAL_Driver/Src/py32f002b_hal_gpio.c
- `led_on()` --calls--> `HAL_GPIO_Init()`  [INFERRED]
  custom_firmware/charlie.c → py32c642_vape/Libraries/PY32F002B_HAL_Driver/Src/py32f002b_hal_gpio.c
- `leds_all_off()` --calls--> `HAL_GPIO_Init()`  [INFERRED]
  custom_firmware/charlie.c → py32c642_vape/Libraries/PY32F002B_HAL_Driver/Src/py32f002b_hal_gpio.c
- `fh8016_init()` --calls--> `HAL_GPIO_Init()`  [INFERRED]
  custom_firmware/fh8016_py32.c → py32c642_vape/Libraries/PY32F002B_HAL_Driver/Src/py32f002b_hal_gpio.c
- `init_gpio()` --calls--> `HAL_GPIO_Init()`  [INFERRED]
  custom_firmware/WORKING_BEFORE_SCENARIO/book_light.c → py32c642_vape/Libraries/PY32F002B_HAL_Driver/Src/py32f002b_hal_gpio.c

## Import Cycles
- None detected.

## Communities (89 total, 18 thin omitted)

### Community 0 - "cmsis_gcc.h"
Cohesion: 0.03
Nodes (132): __CLREX(), __CLZ(), __cmsis_start(), __disable_fault_irq(), __disable_irq(), __enable_fault_irq(), __enable_irq(), __get_APSR() (+124 more)

### Community 1 - "cmsis_armclang_ltm.h"
Cohesion: 0.03
Nodes (115): __CLZ(), __disable_fault_irq(), __disable_irq(), __enable_fault_irq(), __enable_irq(), __get_APSR(), __get_BASEPRI(), __get_CONTROL() (+107 more)

### Community 2 - "py32f002b_hal_tim.c"
Cohesion: 0.06
Nodes (109): HAL_TIM_CallbackIDTypeDef, pTIM_CallbackTypeDef, HAL_StatusTypeDef, HAL_TIM_StateTypeDef, TIM_HandleTypeDef, TIM_TypeDef, __weak, HAL_TIM_Base_DeInit() (+101 more)

### Community 3 - "__DSB"
Cohesion: 0.05
Nodes (106): MPU_Type, __STATIC_FORCEINLINE, SCB_CleanDCache(), SCB_CleanDCache_by_Addr(), SCB_CleanInvalidateDCache(), SCB_CleanInvalidateDCache_by_Addr(), SCB_DisableDCache(), SCB_DisableICache() (+98 more)

### Community 4 - "py32f002b_hal_i2c.c"
Cohesion: 0.06
Nodes (96): HAL_I2C_CallbackIDTypeDef, HAL_I2C_ModeTypeDef, HAL_I2C_StateTypeDef, I2C_HandleTypeDef, pI2C_AddrCallbackTypeDef, pI2C_CallbackTypeDef, HAL_GetTick(), FlagStatus (+88 more)

### Community 5 - "py32f002b_hal"
Cohesion: 0.09
Nodes (29): charlie_all_leds_off(), charlie_init(), charlie_led_off(), charlie_led_on(), digit_battery(), digit_percentage(), digit_show(), digit_teardrop() (+21 more)

### Community 6 - "cmsis_armclang.h"
Cohesion: 0.05
Nodes (69): __CLZ(), __disable_fault_irq(), __disable_irq(), __enable_fault_irq(), __enable_irq(), __get_APSR(), __get_BASEPRI(), __get_CONTROL() (+61 more)

### Community 7 - "cmsis_iccarm.h"
Cohesion: 0.06
Nodes (57): __IAR_FT, iccarm_builtin, intrinsics, __CLZ(), __get_APSR(), __get_MSPLIM(), __get_PSPLIM(), __packed (+49 more)

### Community 8 - "core_cm85.h"
Cohesion: 0.08
Nodes (56): DCB_GetAuthCtrl(), DCB_SetAuthCtrl(), DIB_GetAuthStatus(), IRQn_Type, __STATIC_INLINE, ITM_CheckChar(), ITM_ReceiveChar(), ITM_SendChar() (+48 more)

### Community 9 - "py32f002b_hal_adc.c"
Cohesion: 0.09
Nodes (50): ADC_AnalogWDGConfTypeDef, ADC_ChannelConfTypeDef, ADC_HandleTypeDef, init_adc(), init_adc(), HAL_ADC_CallbackIDTypeDef, HAL_ADCCalibStatusTypeDef, pADC_CallbackTypeDef (+42 more)

### Community 10 - "py32f002b_hal_lptim.c"
Cohesion: 0.08
Nodes (44): HAL_LPTIM_CallbackIDTypeDef, HAL_LPTIM_StateTypeDef, LPTIM_HandleTypeDef, pLPTIM_CallbackTypeDef, charlie_all_leds_off(), charlie_deinit(), charlie_init(), charlie_led_on() (+36 more)

### Community 11 - "py32f002b_hal_spi.c"
Cohesion: 0.12
Nodes (49): HAL_SPI_CallbackIDTypeDef, HAL_SPI_StateTypeDef, pSPI_CallbackTypeDef, FlagStatus, HAL_StatusTypeDef, __weak, HAL_SPI_Abort(), HAL_SPI_Abort_IT() (+41 more)

### Community 12 - "py32f002b_hal_uart.c"
Cohesion: 0.12
Nodes (49): HAL_UART_CallbackIDTypeDef, HAL_UART_StateTypeDef, pUART_CallbackTypeDef, FlagStatus, HAL_StatusTypeDef, __weak, HAL_HalfDuplex_EnableReceiver(), HAL_HalfDuplex_EnableTransmitter() (+41 more)

### Community 13 - "py32f002b_hal_tim_ex.c"
Cohesion: 0.12
Nodes (48): DMA_HandleTypeDef, HAL_StatusTypeDef, HAL_TIM_StateTypeDef, TIM_HandleTypeDef, TIM_TypeDef, __weak, HAL_TIMEx_BreakCallback(), HAL_TIMEx_CommutCallback() (+40 more)

### Community 14 - "core_armv81mml.h"
Cohesion: 0.10
Nodes (47): DCB_GetAuthCtrl(), DCB_SetAuthCtrl(), DIB_GetAuthStatus(), IRQn_Type, __STATIC_INLINE, ITM_CheckChar(), ITM_ReceiveChar(), ITM_SendChar() (+39 more)

### Community 15 - "core_cm55.h"
Cohesion: 0.10
Nodes (47): DCB_GetAuthCtrl(), DCB_SetAuthCtrl(), DIB_GetAuthStatus(), IRQn_Type, __STATIC_INLINE, ITM_CheckChar(), ITM_ReceiveChar(), ITM_SendChar() (+39 more)

### Community 16 - "core_armv8mml.h"
Cohesion: 0.10
Nodes (46): DCB_GetAuthCtrl(), DCB_SetAuthCtrl(), DIB_GetAuthStatus(), IRQn_Type, __STATIC_INLINE, ITM_CheckChar(), ITM_ReceiveChar(), ITM_SendChar() (+38 more)

### Community 17 - "core_cm33.h"
Cohesion: 0.10
Nodes (46): DCB_GetAuthCtrl(), DCB_SetAuthCtrl(), DIB_GetAuthStatus(), IRQn_Type, __STATIC_INLINE, ITM_CheckChar(), ITM_ReceiveChar(), ITM_SendChar() (+38 more)

### Community 18 - "core_cm35p.h"
Cohesion: 0.10
Nodes (46): DCB_GetAuthCtrl(), DCB_SetAuthCtrl(), DIB_GetAuthStatus(), IRQn_Type, __STATIC_INLINE, ITM_CheckChar(), ITM_ReceiveChar(), ITM_SendChar() (+38 more)

### Community 19 - "py32f002b_hal_usart.c"
Cohesion: 0.14
Nodes (39): HAL_USART_CallbackIDTypeDef, HAL_USART_StateTypeDef, pUSART_CallbackTypeDef, FlagStatus, HAL_StatusTypeDef, __weak, HAL_USART_Abort(), HAL_USART_Abort_IT() (+31 more)

### Community 20 - "core_armv8mbl.h"
Cohesion: 0.12
Nodes (39): DCB_GetAuthCtrl(), DCB_SetAuthCtrl(), DIB_GetAuthStatus(), IRQn_Type, __STATIC_INLINE, __NVIC_ClearPendingIRQ(), NVIC_ClearTargetState(), NVIC_DecodePriority() (+31 more)

### Community 21 - "core_cm23.h"
Cohesion: 0.12
Nodes (39): DCB_GetAuthCtrl(), DCB_SetAuthCtrl(), DIB_GetAuthStatus(), IRQn_Type, __STATIC_INLINE, __NVIC_ClearPendingIRQ(), NVIC_ClearTargetState(), NVIC_DecodePriority() (+31 more)

### Community 22 - "HAL_GPIO_Init"
Cohesion: 0.09
Nodes (29): charlie_tick(), led_on(), leds_all_off(), GPIO_InitTypeDef, GPIO_PinState, APP_GpioConfig(), main(), charlie_all_leds_off() (+21 more)

### Community 23 - "stdint"
Cohesion: 0.12
Nodes (7): py32f031x3, py32f031x4, py32f031x6, py32f031x7, py32f031x8, py32f07x_hal, stdint

### Community 24 - "HAL_IncTick"
Cohesion: 0.06
Nodes (8): book_light_pwm_tick(), SysTick_Handler(), SysTick_Handler(), SysTick_Handler(), SysTick_Handler(), SysTick_Handler(), SysTick_Handler(), HAL_IncTick()

### Community 25 - "py32f002b_hal_flash.c"
Cohesion: 0.15
Nodes (29): FLASH_EraseInitTypeDef, FLASH_OBBootProgramInitTypeDef, FLASH_OBProgramInitTypeDef, HAL_StatusTypeDef, __weak, FLASH_MassErase(), FLASH_OB_OptrConfig(), FLASH_PageErase() (+21 more)

### Community 26 - "py32f002b_hal.c"
Cohesion: 0.09
Nodes (12): GPIO_TypeDef, HAL_StatusTypeDef, __weak, HAL_SYSTICK_Config(), HAL_DeInit(), HAL_Init(), HAL_InitTick(), HAL_MspDeInit() (+4 more)

### Community 27 - "FH8016Driver"
Cohesion: 0.12
Nodes (24): arduino, Builder, fh8016_color_t, FH8016Driver, begin, encodeFrame, _numPins, _pins (+16 more)

### Community 28 - "sys"
Cohesion: 0.13
Nodes (11): log(), main(), pylink, pyocd_core_helpers, pyocd_core_session, pyocd_flash_eraser, pyocd_flash_file_programmer, sys (+3 more)

### Community 29 - "BookLightStudioWindow"
Cohesion: 0.10
Nodes (3): BookLightStudioWindow, QMainWindow, pyqtSlot

### Community 30 - "cmsis_armcc.h"
Cohesion: 0.14
Nodes (22): __get_APSR(), __get_BASEPRI(), __get_CONTROL(), __get_FAULTMASK(), __get_FPSCR(), __get_IPSR(), __get_MSP(), __get_PRIMASK() (+14 more)

### Community 31 - "core_sc300.h"
Cohesion: 0.18
Nodes (23): IRQn_Type, __STATIC_INLINE, ITM_CheckChar(), ITM_ReceiveChar(), ITM_SendChar(), __NVIC_ClearPendingIRQ(), NVIC_DecodePriority(), __NVIC_DisableIRQ() (+15 more)

### Community 32 - "core_cm3.h"
Cohesion: 0.19
Nodes (23): IRQn_Type, __STATIC_INLINE, ITM_CheckChar(), ITM_ReceiveChar(), ITM_SendChar(), __NVIC_ClearPendingIRQ(), NVIC_DecodePriority(), __NVIC_DisableIRQ() (+15 more)

### Community 33 - "core_cm4.h"
Cohesion: 0.19
Nodes (23): IRQn_Type, __STATIC_INLINE, ITM_CheckChar(), ITM_ReceiveChar(), ITM_SendChar(), __NVIC_ClearPendingIRQ(), NVIC_DecodePriority(), __NVIC_DisableIRQ() (+15 more)

### Community 34 - "core_cm7.h"
Cohesion: 0.19
Nodes (23): IRQn_Type, __STATIC_INLINE, ITM_CheckChar(), ITM_ReceiveChar(), ITM_SendChar(), __NVIC_ClearPendingIRQ(), NVIC_DecodePriority(), __NVIC_DisableIRQ() (+15 more)

### Community 35 - "py32f002b_hal_def.h"
Cohesion: 0.09
Nodes (3): py32f002b_ll_exti, py32f0xx_hal, stdio

### Community 36 - "custom_firmware/py32f002b_it.c"
Cohesion: 0.10
Nodes (11): EXTI0_1_IRQHandler(), EXTI2_3_IRQHandler(), EXTI4_15_IRQHandler(), book_light_on_touch_irq(), EXTI0_1_IRQHandler(), EXTI2_3_IRQHandler(), EXTI4_15_IRQHandler(), HAL_GPIO_EXTI_Callback() (+3 more)

### Community 37 - "booklight_studio.py"
Cohesion: 0.10
Nodes (14): calc_battery_percent_from_mv(), encode_fh8016_frame(), FilamentLampWidget, gyver_gamma2(), main(), Кривая разряда Li-ion из прошивки main.c, BOOKLIGHT STUDIO & HARDWARE CONTROLLER…, Реалистичная визуализация филаментной светодиодной лампы для чтения. Яркость и… (+6 more)

### Community 38 - "WORKING_BEFORE_SCENARIO/book_light.c"
Cohesion: 0.16
Nodes (16): book_light_loop(), book_light_pwm_tick(), book_light_tick_1ms(), calc_battery_percent(), update_battery_measure(), gyver_gamma2(), ubutton_t, ubutton_click() (+8 more)

### Community 39 - "py32f002b_hal_comp.c"
Cohesion: 0.21
Nodes (20): COMP_HandleTypeDef, HAL_COMP_CallbackIDTypeDef, HAL_COMP_StateTypeDef, pCOMP_CallbackTypeDef, HAL_StatusTypeDef, __weak, HAL_COMP_DeInit(), HAL_COMP_GetError() (+12 more)

### Community 40 - "main"
Cohesion: 0.19
Nodes (15): charlie_all_leds_off(), charlie_init(), charlie_led_off(), charlie_led_on(), charlie_tick(), led_on(), leds_all_off(), digit_battery() (+7 more)

### Community 41 - "FH8016DisplayWidget"
Cohesion: 0.21
Nodes (8): FH8016DisplayWidget, Векторная модель дисплея вейпа Husky 20000 / контроллера FH8016. Поддерживает…, Отрисовка левой и правой фары с физическим эффектом рассеянного света, Отрисовка 4 дуговых делений шкалы вокруг цифр, Пиктограмма зарядки ⚡, Отрисовка 7-сегментных цифр процента и знака %, QPainter, QPolygonF

### Community 42 - "MainWindow"
Cohesion: 0.12
Nodes (4): MainWindow, QMainWindow, QThread, SwdWorker

### Community 43 - "main"
Cohesion: 0.19
Nodes (14): charlie_all_leds_off(), charlie_init(), charlie_led_off(), charlie_led_on(), charlie_tick(), led_on(), leds_all_off(), digit_battery() (+6 more)

### Community 44 - "digit_counter/charlie.c"
Cohesion: 0.19
Nodes (13): charlie_all_leds_off(), charlie_init(), charlie_led_off(), charlie_led_on(), charlie_tick(), led_on(), leds_all_off(), digit_battery() (+5 more)

### Community 45 - "main"
Cohesion: 0.20
Nodes (15): charlie_all_leds_off(), charlie_init(), charlie_led_off(), charlie_led_on(), charlie_tick(), led_on(), leds_all_off(), digit_battery() (+7 more)

### Community 46 - "core_cm0.h"
Cohesion: 0.25
Nodes (17): IRQn_Type, __STATIC_INLINE, __NVIC_ClearPendingIRQ(), NVIC_DecodePriority(), __NVIC_DisableIRQ(), __NVIC_EnableIRQ(), NVIC_EncodePriority(), __NVIC_GetEnableIRQ() (+9 more)

### Community 47 - "core_cm1.h"
Cohesion: 0.25
Nodes (17): IRQn_Type, __STATIC_INLINE, __NVIC_ClearPendingIRQ(), NVIC_DecodePriority(), __NVIC_DisableIRQ(), __NVIC_EnableIRQ(), NVIC_EncodePriority(), __NVIC_GetEnableIRQ() (+9 more)

### Community 48 - ".__init__"
Cohesion: 0.12
Nodes (6): HardwareWorker, QThread, Интерактивная сенсорная кнопка: - Различает короткий клик (<350 мс) и удержание…, Фоновый воркер опроса микроконтроллера по SWD (PyOCD / PyLink). Поддерживает…, TouchSensorButton, QPushButton

### Community 49 - "os"
Cohesion: 0.14
Nodes (7): log(), main(), notify(), Отправляет уведомление на salomanov@ya.ru через систему mail_system, os, subprocess, notify()

### Community 50 - "core_cm0plus.h"
Cohesion: 0.28
Nodes (16): IRQn_Type, __STATIC_INLINE, __NVIC_ClearPendingIRQ(), NVIC_DecodePriority(), __NVIC_DisableIRQ(), __NVIC_EnableIRQ(), NVIC_EncodePriority(), __NVIC_GetEnableIRQ() (+8 more)

### Community 51 - "py32f002b_hal_cortex.c"
Cohesion: 0.20
Nodes (13): init_gpio(), BSP_USART_Config(), IRQn_Type, __weak, HAL_NVIC_ClearPendingIRQ(), HAL_NVIC_DisableIRQ(), HAL_NVIC_EnableIRQ(), HAL_NVIC_GetPendingIRQ() (+5 more)

### Community 52 - "core_sc000.h"
Cohesion: 0.29
Nodes (15): IRQn_Type, __STATIC_INLINE, __NVIC_ClearPendingIRQ(), __NVIC_DisableIRQ(), __NVIC_EnableIRQ(), __NVIC_GetEnableIRQ(), __NVIC_GetPendingIRQ(), __NVIC_GetPriority() (+7 more)

### Community 53 - "pmu_armv8.h"
Cohesion: 0.23
Nodes (15): ARM_PMU_CNTR_Disable(), ARM_PMU_CNTR_Enable(), ARM_PMU_CNTR_Increment(), ARM_PMU_CYCCNT_Reset(), ARM_PMU_Disable(), ARM_PMU_Enable(), ARM_PMU_EVCNTR_ALL_Reset(), ARM_PMU_Get_CCNTR() (+7 more)

### Community 54 - "book_light_loop"
Cohesion: 0.27
Nodes (13): book_light_loop(), ubutton_t, ubutton_t, ubutton_click(), ubutton_hold(), ubutton_init(), ubutton_is_pressed(), ubutton_press() (+5 more)

### Community 55 - "custom_firmware/charlie.c"
Cohesion: 0.24
Nodes (11): charlie_all_leds_off(), charlie_init(), charlie_led_off(), charlie_led_on(), charlie_tick(), led_on(), leds_all_off(), digit_battery() (+3 more)

### Community 56 - "book_light_init"
Cohesion: 0.33
Nodes (13): book_light_init(), update_display(), fh8016_color_t, fh8016_t, GPIO_TypeDef, delay_us(), fh8016_encode_frame(), fh8016_init() (+5 more)

### Community 57 - "py32f002b_bsp_printf.c"
Cohesion: 0.14
Nodes (6): errno, pid_t, _kill(), py32f002b_bsp_printf, stat, unistd

### Community 58 - "py32f002b_hal_exti.c"
Cohesion: 0.29
Nodes (13): EXTI_CallbackIDTypeDef, EXTI_ConfigTypeDef, EXTI_HandleTypeDef, HAL_StatusTypeDef, HAL_EXTI_ClearConfigLine(), HAL_EXTI_ClearPending(), HAL_EXTI_GenerateSWI(), HAL_EXTI_GetConfigLine() (+5 more)

### Community 59 - "custom_firmware/book_light.c"
Cohesion: 0.21
Nodes (8): book_light_init(), book_light_on_touch_irq(), book_light_tick_1ms(), calc_battery_percent(), init_gpio(), update_battery_measure(), gyver_gamma2(), HAL_GPIO_EXTI_Callback()

### Community 60 - "stdbool"
Cohesion: 0.18
Nodes (3): main(), main(), stdbool

### Community 61 - "custom_firmware/fh8016_py32.c"
Cohesion: 0.35
Nodes (12): update_display(), fh8016_color_t, fh8016_t, GPIO_TypeDef, delay_us(), fh8016_encode_frame(), fh8016_init(), fh8016_set_raw() (+4 more)

### Community 62 - "py32f002b_hal_crc.c"
Cohesion: 0.32
Nodes (11): CRC_HandleTypeDef, HAL_CRC_StateTypeDef, HAL_StatusTypeDef, __weak, HAL_CRC_Accumulate(), HAL_CRC_Calculate(), HAL_CRC_DeInit(), HAL_CRC_GetState() (+3 more)

### Community 63 - "py32f002b_hal_pwr.c"
Cohesion: 0.18
Nodes (5): PWR_BIASConfigTypeDef, PWR_StopModeConfigTypeDef, HAL_StatusTypeDef, HAL_PWR_ConfigBIAS(), HAL_PWR_ConfigStopMode()

### Community 64 - "enter_deep_sleep"
Cohesion: 0.31
Nodes (10): enter_deep_sleep(), enter_deep_sleep(), ubutton_t, ubutton_init(), ubutton_reset(), ubutton_tick(), nap(), HAL_ResumeTick() (+2 more)

### Community 65 - "cmsis_compiler.h"
Cohesion: 0.27
Nodes (9): cmsis_ccs, cmsis_csm, packed, __PACKED_STRUCT, T_UINT16_READ(), T_UINT16_WRITE(), T_UINT32(), T_UINT32_READ() (+1 more)

### Community 67 - "gyver_led.c"
Cohesion: 0.50
Nodes (7): gled_fade(), gled_init(), gled_set(), gled_set_gamma(), gled_tick(), update_pwm(), gyver_led_t

### Community 71 - "gyver_timer.h"
Cohesion: 0.53
Nodes (5): gtimer_once(), gtimer_ready(), gtimer_reset(), gtimer_set(), gtimer_t

### Community 73 - "__PACKED_STRUCT"
Cohesion: 0.40
Nodes (5): __PACKED_STRUCT, T_UINT16_READ(), T_UINT16_WRITE(), T_UINT32_READ(), T_UINT32_WRITE()

### Community 74 - "__PACKED_STRUCT"
Cohesion: 0.40
Nodes (5): __PACKED_STRUCT, T_UINT16_READ(), T_UINT16_WRITE(), T_UINT32_READ(), T_UINT32_WRITE()

### Community 75 - "__ROR"
Cohesion: 0.40
Nodes (5): __ROR(), __SXTAB16(), __SXTAB16_RORn(), __SXTB16(), __SXTB16_RORn()

## Knowledge Gaps
- **6 isolated node(s):** `_numPins`, `_pins`, `_rawBits`, `v`, `v` (+1 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 302 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **18 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `HAL_GetTick()` connect `py32f002b_hal_i2c.c` to `py32f002b_hal`, `WORKING_BEFORE_SCENARIO/book_light.c`, `py32f002b_hal_adc.c`, `py32f002b_hal_spi.c`, `py32f002b_hal_uart.c`, `py32f002b_hal_usart.c`, `book_light_loop`, `HAL_GPIO_Init`, `py32f002b_hal_flash.c`, `py32f002b_hal.c`?**
  _High betweenness centrality (0.019) - this node is a cross-community bridge._
- **Why does `BSP_USART_Config()` connect `py32f002b_hal_cortex.c` to `py32f002b_bsp_printf.c`, `py32f002b_hal_uart.c`, `HAL_GPIO_Init`?**
  _High betweenness centrality (0.014) - this node is a cross-community bridge._
- **Why does `__DSB()` connect `__DSB` to `cmsis_gcc.h`, `core_cm3.h`, `core_cm4.h`, `core_cm7.h`, `core_cm85.h`, `core_armv81mml.h`, `core_cm0.h`, `core_armv8mml.h`, `core_cm1.h`, `core_cm0plus.h`, `core_cm33.h`, `core_armv8mbl.h`, `core_cm23.h`, `core_cm35p.h`, `core_cm55.h`, `core_sc000.h`, `core_sc300.h`?**
  _High betweenness centrality (0.014) - this node is a cross-community bridge._
- **Are the 93 inferred relationships involving `__DSB()` (e.g. with `SCB_CleanDCache()` and `SCB_CleanDCache_by_Addr()`) actually correct?**
  _`__DSB()` has 93 INFERRED edges - model-reasoned connections that need verification._
- **What connects `_numPins`, `_pins`, `_rawBits` to the rest of the system?**
  _6 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `cmsis_gcc.h` be split into smaller, more focused modules?**
  _Cohesion score 0.02984734563681932 - nodes in this community are weakly interconnected._
- **Should `cmsis_armclang_ltm.h` be split into smaller, more focused modules?**
  _Cohesion score 0.034182908545727135 - nodes in this community are weakly interconnected._