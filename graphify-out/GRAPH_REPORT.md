# Graph Report - ВЕЙП  (2026-09-16)

## Corpus Check
- Large corpus: 613 files · ~1,566,694 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder.

## Summary
- 2130 nodes · 4964 edges · 95 communities (55 shown, 40 thin omitted)
- Extraction: 91% EXTRACTED · 9% INFERRED · 0% AMBIGUOUS · INFERRED: 462 edges (avg confidence: 0.85)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20
- Community 21
- Community 22
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 47
- Community 48
- Community 49
- Community 50
- Community 51
- Community 52
- Community 53
- Community 54
- Community 55
- Community 56
- Community 57
- Community 61
- Community 62
- Community 63
- Community 64
- Community 65
- Community 66
- Community 77
- Community 78

## God Nodes (most connected - your core abstractions)
1. `__DSB()` - 95 edges
2. `__ISB()` - 74 edges
3. `HAL_GetTick()` - 45 edges
4. `HAL_GPIO_Init()` - 28 edges
5. `TIM_CCxChannelCmd()` - 28 edges
6. `HAL_GPIO_WritePin()` - 22 edges
7. `TIM_CCxNChannelCmd()` - 18 edges
8. `HAL_IncTick()` - 17 edges
9. `HAL_I2C_EV_IRQHandler()` - 16 edges
10. `I2C_WaitOnFlagUntilTimeout()` - 16 edges

## Surprising Connections (you probably didn't know these)
- `init_gpio()` --calls--> `HAL_GPIO_Init()`  [INFERRED]
  custom_firmware/book_light.c → py32c642_vape/Libraries/PY32F002B_HAL_Driver/Src/py32f002b_hal_gpio.c
- `init_gpio()` --calls--> `HAL_GPIO_WritePin()`  [INFERRED]
  custom_firmware/book_light.c → py32c642_vape/Libraries/PY32F002B_HAL_Driver/Src/py32f002b_hal_gpio.c
- `update_battery_measure()` --calls--> `HAL_ADC_GetValue()`  [INFERRED]
  custom_firmware/book_light.c → py32c642_vape/Libraries/PY32F002B_HAL_Driver/Src/py32f002b_hal_adc.c
- `update_battery_measure()` --calls--> `HAL_ADC_Start()`  [INFERRED]
  custom_firmware/book_light.c → py32c642_vape/Libraries/PY32F002B_HAL_Driver/Src/py32f002b_hal_adc.c
- `enter_deep_sleep()` --calls--> `HAL_GetTick()`  [INFERRED]
  custom_firmware/book_light.c → py32c642_vape/Libraries/PY32F002B_HAL_Driver/Src/py32f002b_hal.c

## Import Cycles
- None detected.

## Communities (95 total, 40 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.03
Nodes (132): __CLREX(), __CLZ(), __cmsis_start(), __disable_fault_irq(), __disable_irq(), __enable_fault_irq(), __enable_irq(), __get_APSR() (+124 more)

### Community 1 - "Community 1"
Cohesion: 0.03
Nodes (115): __CLZ(), __disable_fault_irq(), __disable_irq(), __enable_fault_irq(), __enable_irq(), __get_APSR(), __get_BASEPRI(), __get_CONTROL() (+107 more)

### Community 2 - "Community 2"
Cohesion: 0.06
Nodes (109): HAL_TIM_CallbackIDTypeDef, pTIM_CallbackTypeDef, HAL_StatusTypeDef, HAL_TIM_StateTypeDef, TIM_HandleTypeDef, TIM_TypeDef, __weak, HAL_TIM_Base_DeInit() (+101 more)

### Community 3 - "Community 3"
Cohesion: 0.05
Nodes (106): MPU_Type, __STATIC_FORCEINLINE, SCB_CleanDCache(), SCB_CleanDCache_by_Addr(), SCB_CleanInvalidateDCache(), SCB_CleanInvalidateDCache_by_Addr(), SCB_DisableDCache(), SCB_DisableICache() (+98 more)

### Community 4 - "Community 4"
Cohesion: 0.08
Nodes (84): HAL_I2C_CallbackIDTypeDef, HAL_I2C_ModeTypeDef, HAL_I2C_StateTypeDef, I2C_HandleTypeDef, IWDG_HandleTypeDef, pI2C_AddrCallbackTypeDef, pI2C_CallbackTypeDef, HAL_GetTick() (+76 more)

### Community 5 - "Community 5"
Cohesion: 0.06
Nodes (64): ADC_AnalogWDGConfTypeDef, ADC_ChannelConfTypeDef, ADC_HandleTypeDef, init_adc(), HAL_ADC_CallbackIDTypeDef, HAL_ADCCalibStatusTypeDef, pADC_CallbackTypeDef, charlie_all_leds_off() (+56 more)

### Community 6 - "Community 6"
Cohesion: 0.05
Nodes (69): __CLZ(), __disable_fault_irq(), __disable_irq(), __enable_fault_irq(), __enable_irq(), __get_APSR(), __get_BASEPRI(), __get_CONTROL() (+61 more)

### Community 7 - "Community 7"
Cohesion: 0.07
Nodes (61): DCB_GetAuthCtrl(), DCB_SetAuthCtrl(), DIB_GetAuthStatus(), IRQn_Type, __STATIC_INLINE, ITM_CheckChar(), ITM_ReceiveChar(), ITM_SendChar() (+53 more)

### Community 8 - "Community 8"
Cohesion: 0.07
Nodes (56): packed, __PACKED_STRUCT, T_UINT16_READ(), T_UINT16_WRITE(), T_UINT32(), T_UINT32_READ(), T_UINT32_WRITE(), IRQn_Type (+48 more)

### Community 9 - "Community 9"
Cohesion: 0.08
Nodes (56): DCB_GetAuthCtrl(), DCB_SetAuthCtrl(), DIB_GetAuthStatus(), IRQn_Type, __STATIC_INLINE, ITM_CheckChar(), ITM_ReceiveChar(), ITM_SendChar() (+48 more)

### Community 10 - "Community 10"
Cohesion: 0.07
Nodes (55): __IAR_FT, __CLZ(), __get_APSR(), __get_MSPLIM(), __get_PSPLIM(), __packed, __STATIC_FORCEINLINE, __STATIC_INLINE (+47 more)

### Community 11 - "Community 11"
Cohesion: 0.08
Nodes (19): IRQn_Type, __STATIC_INLINE, __NVIC_ClearPendingIRQ(), NVIC_DecodePriority(), __NVIC_DisableIRQ(), __NVIC_EnableIRQ(), NVIC_EncodePriority(), __NVIC_GetEnableIRQ() (+11 more)

### Community 12 - "Community 12"
Cohesion: 0.12
Nodes (49): HAL_SPI_CallbackIDTypeDef, HAL_SPI_StateTypeDef, pSPI_CallbackTypeDef, FlagStatus, HAL_StatusTypeDef, __weak, HAL_SPI_Abort(), HAL_SPI_Abort_IT() (+41 more)

### Community 13 - "Community 13"
Cohesion: 0.12
Nodes (49): HAL_UART_CallbackIDTypeDef, HAL_UART_StateTypeDef, pUART_CallbackTypeDef, FlagStatus, HAL_StatusTypeDef, __weak, HAL_HalfDuplex_EnableReceiver(), HAL_HalfDuplex_EnableTransmitter() (+41 more)

### Community 14 - "Community 14"
Cohesion: 0.12
Nodes (48): DMA_HandleTypeDef, HAL_StatusTypeDef, HAL_TIM_StateTypeDef, TIM_HandleTypeDef, TIM_TypeDef, __weak, HAL_TIMEx_BreakCallback(), HAL_TIMEx_CommutCallback() (+40 more)

### Community 15 - "Community 15"
Cohesion: 0.10
Nodes (47): DCB_GetAuthCtrl(), DCB_SetAuthCtrl(), DIB_GetAuthStatus(), IRQn_Type, __STATIC_INLINE, ITM_CheckChar(), ITM_ReceiveChar(), ITM_SendChar() (+39 more)

### Community 16 - "Community 16"
Cohesion: 0.10
Nodes (46): DCB_GetAuthCtrl(), DCB_SetAuthCtrl(), DIB_GetAuthStatus(), IRQn_Type, __STATIC_INLINE, ITM_CheckChar(), ITM_ReceiveChar(), ITM_SendChar() (+38 more)

### Community 17 - "Community 17"
Cohesion: 0.10
Nodes (46): DCB_GetAuthCtrl(), DCB_SetAuthCtrl(), DIB_GetAuthStatus(), IRQn_Type, __STATIC_INLINE, ITM_CheckChar(), ITM_ReceiveChar(), ITM_SendChar() (+38 more)

### Community 18 - "Community 18"
Cohesion: 0.10
Nodes (46): DCB_GetAuthCtrl(), DCB_SetAuthCtrl(), DIB_GetAuthStatus(), IRQn_Type, __STATIC_INLINE, ITM_CheckChar(), ITM_ReceiveChar(), ITM_SendChar() (+38 more)

### Community 19 - "Community 19"
Cohesion: 0.14
Nodes (39): HAL_USART_CallbackIDTypeDef, HAL_USART_StateTypeDef, pUSART_CallbackTypeDef, FlagStatus, HAL_StatusTypeDef, __weak, HAL_USART_Abort(), HAL_USART_Abort_IT() (+31 more)

### Community 20 - "Community 20"
Cohesion: 0.12
Nodes (39): DCB_GetAuthCtrl(), DCB_SetAuthCtrl(), DIB_GetAuthStatus(), IRQn_Type, __STATIC_INLINE, __NVIC_ClearPendingIRQ(), NVIC_ClearTargetState(), NVIC_DecodePriority() (+31 more)

### Community 21 - "Community 21"
Cohesion: 0.12
Nodes (39): DCB_GetAuthCtrl(), DCB_SetAuthCtrl(), DIB_GetAuthStatus(), IRQn_Type, __STATIC_INLINE, __NVIC_ClearPendingIRQ(), NVIC_ClearTargetState(), NVIC_DecodePriority() (+31 more)

### Community 22 - "Community 22"
Cohesion: 0.15
Nodes (29): FLASH_EraseInitTypeDef, FLASH_OBBootProgramInitTypeDef, FLASH_OBProgramInitTypeDef, HAL_StatusTypeDef, __weak, FLASH_MassErase(), FLASH_OB_OptrConfig(), FLASH_PageErase() (+21 more)

### Community 23 - "Community 23"
Cohesion: 0.17
Nodes (28): HAL_LPTIM_CallbackIDTypeDef, HAL_LPTIM_StateTypeDef, LPTIM_HandleTypeDef, pLPTIM_CallbackTypeDef, HAL_StatusTypeDef, __weak, HAL_LPTIM_AutoReloadMatchCallback(), HAL_LPTIM_AutoReloadUpdateCompletedCallback() (+20 more)

### Community 24 - "Community 24"
Cohesion: 0.09
Nodes (9): GPIO_TypeDef, HAL_StatusTypeDef, HAL_DeInit(), HAL_Init(), HAL_MspDeInit(), HAL_MspInit(), HAL_SetTickFreq(), HAL_SYSCFG_DisableGPIONoiseFilter() (+1 more)

### Community 25 - "Community 25"
Cohesion: 0.14
Nodes (21): Builder, fh8016_color_t, FH8016Driver, begin, encodeFrame, _numPins, _pins, _rawBits (+13 more)

### Community 26 - "Community 26"
Cohesion: 0.14
Nodes (22): __get_APSR(), __get_BASEPRI(), __get_CONTROL(), __get_FAULTMASK(), __get_FPSCR(), __get_IPSR(), __get_MSP(), __get_PRIMASK() (+14 more)

### Community 27 - "Community 27"
Cohesion: 0.13
Nodes (20): GPIO_InitTypeDef, GPIO_PinState, charlie_tick(), led_on(), leds_all_off(), APP_GpioConfig(), main(), charlie_tick() (+12 more)

### Community 28 - "Community 28"
Cohesion: 0.19
Nodes (23): IRQn_Type, __STATIC_INLINE, ITM_CheckChar(), ITM_ReceiveChar(), ITM_SendChar(), __NVIC_ClearPendingIRQ(), NVIC_DecodePriority(), __NVIC_DisableIRQ() (+15 more)

### Community 29 - "Community 29"
Cohesion: 0.19
Nodes (23): IRQn_Type, __STATIC_INLINE, ITM_CheckChar(), ITM_ReceiveChar(), ITM_SendChar(), __NVIC_ClearPendingIRQ(), NVIC_DecodePriority(), __NVIC_DisableIRQ() (+15 more)

### Community 30 - "Community 30"
Cohesion: 0.19
Nodes (23): IRQn_Type, __STATIC_INLINE, ITM_CheckChar(), ITM_ReceiveChar(), ITM_SendChar(), __NVIC_ClearPendingIRQ(), NVIC_DecodePriority(), __NVIC_DisableIRQ() (+15 more)

### Community 31 - "Community 31"
Cohesion: 0.19
Nodes (23): IRQn_Type, __STATIC_INLINE, ITM_CheckChar(), ITM_ReceiveChar(), ITM_SendChar(), __NVIC_ClearPendingIRQ(), NVIC_DecodePriority(), __NVIC_DisableIRQ() (+15 more)

### Community 32 - "Community 32"
Cohesion: 0.14
Nodes (19): HAL_SYSTICK_Config(), HAL_InitTick(), HAL_StatusTypeDef, __weak, HAL_RCCEx_GetPeriphCLKFreq(), HAL_RCC_ClockConfig(), HAL_RCC_CSSCallback(), HAL_RCC_DeInit() (+11 more)

### Community 33 - "Community 33"
Cohesion: 0.21
Nodes (20): COMP_HandleTypeDef, HAL_COMP_CallbackIDTypeDef, HAL_COMP_StateTypeDef, pCOMP_CallbackTypeDef, HAL_StatusTypeDef, __weak, HAL_COMP_DeInit(), HAL_COMP_GetError() (+12 more)

### Community 34 - "Community 34"
Cohesion: 0.19
Nodes (15): charlie_all_leds_off(), charlie_init(), charlie_led_off(), charlie_led_on(), charlie_tick(), led_on(), leds_all_off(), digit_battery() (+7 more)

### Community 35 - "Community 35"
Cohesion: 0.19
Nodes (13): charlie_all_leds_off(), charlie_init(), charlie_led_off(), charlie_led_on(), charlie_tick(), led_on(), leds_all_off(), digit_battery() (+5 more)

### Community 37 - "Community 37"
Cohesion: 0.18
Nodes (14): charlie_all_leds_off(), charlie_init(), charlie_led_on(), charlie_tick(), led_on(), leds_all_off(), APP_ErrorHandler(), APP_RCCOscConfig() (+6 more)

### Community 38 - "Community 38"
Cohesion: 0.20
Nodes (13): init_gpio(), BSP_USART_Config(), IRQn_Type, __weak, HAL_NVIC_ClearPendingIRQ(), HAL_NVIC_DisableIRQ(), HAL_NVIC_EnableIRQ(), HAL_NVIC_GetPendingIRQ() (+5 more)

### Community 39 - "Community 39"
Cohesion: 0.24
Nodes (10): book_light_loop(), calc_battery_percent(), enter_deep_sleep(), on_touch_down(), on_touch_up(), update_battery_measure(), update_display_hardware(), update_state_machine() (+2 more)

### Community 40 - "Community 40"
Cohesion: 0.24
Nodes (11): charlie_all_leds_off(), charlie_init(), charlie_led_off(), charlie_led_on(), charlie_tick(), led_on(), leds_all_off(), digit_battery() (+3 more)

### Community 41 - "Community 41"
Cohesion: 0.20
Nodes (10): charlie_all_leds_off(), charlie_init(), charlie_led_off(), charlie_led_on(), charlie_tick(), led_on(), leds_all_off(), main() (+2 more)

### Community 42 - "Community 42"
Cohesion: 0.29
Nodes (13): EXTI_CallbackIDTypeDef, EXTI_ConfigTypeDef, EXTI_HandleTypeDef, HAL_StatusTypeDef, HAL_EXTI_ClearConfigLine(), HAL_EXTI_ClearPending(), HAL_EXTI_GenerateSWI(), HAL_EXTI_GetConfigLine() (+5 more)

### Community 43 - "Community 43"
Cohesion: 0.35
Nodes (12): book_light_init(), fh8016_color_t, GPIO_TypeDef, delay_us(), fh8016_encode_frame(), fh8016_init(), fh8016_set_raw(), fh8016_set_state() (+4 more)

### Community 44 - "Community 44"
Cohesion: 0.17
Nodes (6): PWR_BIASConfigTypeDef, PWR_StopModeConfigTypeDef, HAL_StatusTypeDef, HAL_PWR_ConfigBIAS(), HAL_PWR_ConfigStopMode(), HAL_PWR_EnterSTOPMode()

### Community 45 - "Community 45"
Cohesion: 0.32
Nodes (11): CRC_HandleTypeDef, HAL_CRC_StateTypeDef, HAL_StatusTypeDef, __weak, HAL_CRC_Accumulate(), HAL_CRC_Calculate(), HAL_CRC_DeInit(), HAL_CRC_GetState() (+3 more)

### Community 46 - "Community 46"
Cohesion: 0.20
Nodes (6): book_light_on_touch_irq(), EXTI0_1_IRQHandler(), EXTI2_3_IRQHandler(), EXTI4_15_IRQHandler(), HAL_GPIO_EXTI_Callback(), HAL_GPIO_EXTI_IRQHandler()

### Community 48 - "Community 48"
Cohesion: 0.39
Nodes (8): ubutton_t, ubutton_click(), ubutton_hold(), ubutton_is_pressed(), ubutton_press(), ubutton_release(), ubutton_release_step(), ubutton_step()

### Community 49 - "Community 49"
Cohesion: 0.39
Nodes (7): charlie_all_leds_off(), charlie_init(), APP_ErrorHandler(), APP_TimConfig(), APP_TimPwmConfig(), main(), SysTick_Handler()

### Community 50 - "Community 50"
Cohesion: 0.46
Nodes (6): charlie_led_off(), charlie_led_on(), digit_battery(), digit_percentage(), digit_show(), digit_teardrop()

### Community 56 - "Community 56"
Cohesion: 0.33
Nodes (4): HAL_StatusTypeDef, HAL_RCCEx_GetPeriphCLKConfig(), HAL_RCCEx_PeriphCLKConfig(), RCC_PeriphCLKInitTypeDef

### Community 57 - "Community 57"
Cohesion: 0.33
Nodes (6): book_light_pwm_tick(), book_light_tick_1ms(), SysTick_Handler(), SysTick_Handler(), SysTick_Handler(), HAL_IncTick()

### Community 61 - "Community 61"
Cohesion: 0.70
Nodes (4): ubutton_t, ubutton_init(), ubutton_reset(), ubutton_tick()

### Community 62 - "Community 62"
Cohesion: 0.40
Nodes (5): __PACKED_STRUCT, T_UINT16_READ(), T_UINT16_WRITE(), T_UINT32_READ(), T_UINT32_WRITE()

### Community 63 - "Community 63"
Cohesion: 0.40
Nodes (5): __PACKED_STRUCT, T_UINT16_READ(), T_UINT16_WRITE(), T_UINT32_READ(), T_UINT32_WRITE()

### Community 64 - "Community 64"
Cohesion: 0.40
Nodes (5): __ROR(), __SXTAB16(), __SXTAB16_RORn(), __SXTB16(), __SXTB16_RORn()

## Knowledge Gaps
- **6 isolated node(s):** `_pins`, `_numPins`, `_rawBits`, `v`, `v` (+1 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 219 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **40 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `HAL_GetTick()` connect `Community 4` to `Community 32`, `Community 5`, `Community 37`, `Community 39`, `Community 41`, `Community 12`, `Community 13`, `Community 19`, `Community 22`, `Community 24`?**
  _High betweenness centrality (0.073) - this node is a cross-community bridge._
- **Why does `HAL_Delay()` connect `Community 41` to `Community 34`, `Community 35`, `Community 4`, `Community 5`, `Community 37`, `Community 49`, `Community 24`, `Community 27`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Why does `main()` connect `Community 49` to `Community 2`, `Community 41`, `Community 50`, `Community 24`, `Community 27`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Are the 93 inferred relationships involving `__DSB()` (e.g. with `SCB_CleanDCache()` and `SCB_CleanDCache_by_Addr()`) actually correct?**
  _`__DSB()` has 93 INFERRED edges - model-reasoned connections that need verification._
- **Are the 70 inferred relationships involving `__ISB()` (e.g. with `SCB_CleanDCache()` and `SCB_CleanDCache_by_Addr()`) actually correct?**
  _`__ISB()` has 70 INFERRED edges - model-reasoned connections that need verification._
- **What connects `_pins`, `_numPins`, `_rawBits` to the rest of the system?**
  _6 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.02984734563681932 - nodes in this community are weakly interconnected._