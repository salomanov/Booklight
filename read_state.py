import pylink
import sys

try:
    jlink = pylink.JLink()
    jlink.open()
    jlink.set_tif(pylink.enums.JLinkInterfaces.SWD)
    jlink.set_speed(1000)
    jlink.coresight_configure()
    jlink.coresight_write(0, 0x23000002, ap=True)

    def read_mem32(addr):
        jlink.coresight_write(1, addr, ap=True)
        jlink.coresight_read(3, ap=True)
        return jlink.coresight_read(3, ap=True)

    pin_sel = read_mem32(0x20000008)
    lamp_on = read_mem32(0x20000004)
    pwm_duty = read_mem32(0x20000000)
    gpioa_odr = read_mem32(0x50000014)
    gpioa_idr = read_mem32(0x50000010)
    
    print("=== СОСТОЯНИЕ МИКРОКОНТРОЛЛЕРА ===")
    print(f"Выбранный пин (pin_select): {pin_sel} (0=PA0, 1=PA1, 2=PA5)")
    print(f"Состояние лампы (lamp_on): {lamp_on}")
    print(f"Скважность (pwm_duty): {pwm_duty}")
    print(f"Регистр вывода (GPIOA_ODR): {hex(gpioa_odr)}")
    print(f" - PA0 (Пин 13): {'HIGH (3.3V)' if (gpioa_odr & (1<<0)) else 'LOW (0V)'}")
    print(f" - PA1 (Пин 14): {'HIGH (3.3V)' if (gpioa_odr & (1<<1)) else 'LOW (0V)'}")
    print(f" - PA5 (Пин 18): {'HIGH (3.3V)' if (gpioa_odr & (1<<5)) else 'LOW (0V)'}")
    
except Exception as e:
    print(f"Ошибка: {e}")
