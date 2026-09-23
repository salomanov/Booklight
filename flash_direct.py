import sys
import os
import time
from pyocd.core.helpers import ConnectHelper
from pyocd.core.session import Session
from pyocd.flash.file_programmer import FileProgrammer

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

bin_file = sys.argv[1] if len(sys.argv) > 1 else r"c:\Users\Salomanov\Desktop\ВЕЙП\custom_firmware\build\battery_firmware.bin"
if not os.path.exists(bin_file):
    print(f"[X] Ошибка: файл прошивки не найден: {bin_file}")
    sys.exit(1)

print("=" * 60)
print("   ПРЯМАЯ ПРОШИВКА БЕЗ ПЕРЕДЁРГИВАНИЯ ПИТАНИЯ (ON-THE-FLY)")
print("=" * 60)

probes = ConnectHelper.get_all_connected_probes(blocking=False)
if not probes:
    print("[!] Ошибка: Программатор не обнаружен в USB!")
    sys.exit(1)

probe = probes[0]
print(f"[*] Программатор: {probe.description} (SN: {probe.unique_id})")

session = Session(
    probe,
    target_override='py32f002bx5',
    frequency=1000000,
    options={
        'connect_mode': 'under-reset',
        'resume_on_disconnect': False
    }
)
session.open(init_board=False)
target = session.target

def halt_core_task():
    print("[*] Аппаратный векторный перехват сброса (Vector Catch Core Reset)...")
    target.dp.write_ap(0x00, 0x23000002) # CSW: 32-bit transfer
    target.dp.write_ap(0x04, 0xE000EDF0) # TAR: DHCSR
    target.dp.write_ap(0x0C, 0xA05F0003) # DRW: C_DEBUGEN | C_HALT
    target.dp.write_ap(0x04, 0xE000EDFC) # TAR: DEMCR
    target.dp.write_ap(0x0C, 0x00000001) # DRW: VC_CORERESET
    target.dp.write_ap(0x04, 0xE000ED0C) # TAR: AIRCR
    target.dp.write_ap(0x0C, 0x05FA0004) # DRW: SYSRESETREQ
    time.sleep(0.05)
    target.dp.write_ap(0x04, 0xE000EDF0) # TAR: DHCSR
    dhcsr = target.dp.read_ap(0x0C)
    print(f"[✓] Ядро чисто остановлено на Reset Vector! DHCSR: {hex(dhcsr)}")

seq = target.create_init_sequence()
seq.insert_after('dp_init', ('halt_core_task', halt_core_task))

print("[*] Инициализация архитектуры CoreSight и шины...")
seq.invoke()
session.board._inited = True
print(f"[✓] Обнаружен чип: {target.part_number} (ядро {target.cores[0].name})")

print(f"\n[*] Заливаем прошивку {os.path.basename(bin_file)} ({os.path.getsize(bin_file)} байт)...")
programmer = FileProgrammer(session)
programmer.program(bin_file)

print("\n" + "=" * 60)
print("   🎉🎉🎉 ПРОШИВКА УСПЕШНО ЗАВЕРШЕНА! 🎉🎉🎉")
print("   Прошивка: battery_firmware.bin")
print("   Конфигурация платы CXV0257-V1.3:")
print("     * Сенсор TTP223 : Пин 8 (PB4 / M+)")
print("     * Зарядка C60H  : Пин 7 (PB5 / CHRG)")
print("     * Экран FH8016  : Пин 14 (PA1 / 1-Wire)")
print("     * Лампа LED PWM : Пин 13 (PA0)")
print("=" * 60)

try:
    target.reset()
    print("[✓] Контроллер успешно перезапущен в рабочий режим!")
except Exception as e:
    print(f"[*] Сброс: {e}")

session.close()
