import sys
import time

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from pyocd.core.helpers import ConnectHelper
from pyocd.core.session import Session

probes = ConnectHelper.get_all_connected_probes(blocking=False)
if not probes:
    print("Ошибка: Программатор не обнаружен в USB!")
    sys.exit(1)

session = Session(probes[0], target_override='py32f002bx5', frequency=1000000, options={'connect_mode': 'halt'})
session.open(init_board=False)

try:
    def halt_core_task():
        target.dp.write_ap(0x00, 0x23000002)
        target.dp.write_ap(0x04, 0xE000EDF0)
        target.dp.write_ap(0x0C, 0xA05F0003)

    target = session.target
    seq = target.create_init_sequence()
    seq.insert_after('dp_init', ('halt_core_task', halt_core_task))
    seq.invoke()
    session.board._inited = True

    # 1. Читаем переменные прошивки из SRAM (ОЗУ)
    b_percent = session.target.read8(0x20000000)
    b_mv = session.target.read16(0x20000002)
    charging = session.target.read8(0x20000030)
    cur_bright = session.target.read8(0x20000055)
    lamp = session.target.read8(0x20000056)

    # 2. Читаем регистры периферии GPIO
    gpiob_idr = session.target.read32(0x50000410)
    gpioa_idr = session.target.read32(0x50000010)
    gpioa_odr = session.target.read32(0x50000014)

    # 3. Регистры ядра процессора
    pc = session.target.read_core_register('pc')
    state = session.target.get_state().name

    print("============================================================")
    print("       РЕАЛЬНАЯ ТЕЛЕМЕТРИЯ КОНТРОЛЛЕРА ПРЯМО СЕЙЧАС (SWD)    ")
    print("============================================================")
    print(f"Статус ядра Cortex-M0+  : {state} (PC = 0x{pc:08X})")
    print(f"Питание чипа (АЦП VCCA) : {b_mv} мВ ({b_mv / 1000.0:.3f} В)")
    print(f"Процент заряда (экран)  : {b_percent} %")
    print(f"Флаг зарядки Type-C     : {'ИДЕТ ЗАРЯДКА' if charging else 'НЕТ ЗАРЯДКИ (БАТАРЕЯ)'}")
    print(f"Состояние лампы         : {'ВКЛЮЧЕНА' if lamp else 'ВЫКЛЮЧЕНА'}")
    print(f"Текущая яркость лампы   : {cur_bright} %")
    print("------------------------------------------------------------")
    print("ФИЗИЧЕСКИЕ ВХОДЫ (GPIO Port B):")
    print(f"  * PB4 (Пин 8 / Пятачок M+ / Кнопка): {'1 (HIGH - нажата)' if (gpiob_idr & (1 << 4)) else '0 (LOW - отпущена)'}")
    print(f"  * PB5 (Пин 7 / Контроллер CHRG)    : {'0 (LOW - ИДЕТ ЗАРЯДКА)' if not (gpiob_idr & (1 << 5)) else '1 (HIGH - покоя/заряжен)'}")
    print(f"  * PB3 (Монитор VBUS)               : {'1 (HIGH)' if (gpiob_idr & (1 << 3)) else '0 (LOW)'}")
    print("------------------------------------------------------------")
    print("ВЫХОДЫ ШИМ ЛАМПЫ (GPIO Port A):")
    print(f"  * PA0 (MOSFET Pin 13)      : {'HIGH' if (gpioa_odr & (1 << 0)) else 'LOW'}")
    print(f"  * PA5 (MOSFET Pin 18)      : {'HIGH' if (gpioa_odr & (1 << 5)) else 'LOW'}")
    print(f"  * PA1 (1-Wire дисплей)     : {'HIGH' if (gpioa_odr & (1 << 1)) else 'LOW'}")
    print("============================================================")

    # Возобновляем работу ядра, если оно было остановлено при чтении
    try:
        session.target.resume()
    except Exception:
        pass

except Exception as e:
    print(f"[X] Ошибка чтения SWD: {e}")
finally:
    session.close()
