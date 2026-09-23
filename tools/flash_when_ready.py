import sys
import time
import os

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from pyocd.core.helpers import ConnectHelper
from pyocd.core.session import Session
from pyocd.flash.file_programmer import FileProgrammer

def log(msg):
    print(msg, flush=True)

bin_file = r"c:\Users\Salomanov\Desktop\ВЕЙП\custom_firmware\build\battery_firmware.bin"
if not os.path.exists(bin_file):
    log(f"Error: {bin_file} not found")
    sys.exit(1)

log("=" * 60)
log("       ПРОШИВАТЕЛЬ BOOKLIGHT ДЛЯ CXV0257-V1.3")
log("=" * 60)

probes = ConnectHelper.get_all_connected_probes(blocking=False)
if not probes:
    log("[X] Ошибка: Программатор (ST-Link/J-Link) не найден в USB!")
    sys.exit(1)

probe = probes[0]
log(f"Программатор: {probe.description} (SN: {probe.unique_id})")
log(f"Файл прошивки: {os.path.basename(bin_file)} ({os.path.getsize(bin_file)} байт)")
log("-" * 60)
log("Ожидаю подключение платы к программатору...")
log("Подключите к плате:")
log("  1. GND   -> GND (общий минус)")
log("  2. SWCLK -> CK  (PA2)")
log("  3. SWDIO -> DA  (PB6)")
log("  4. 3.3V  -> VCC (если плата не запитана от АКБ)")
log("-" * 60)

options = {
    'target_override': 'py32f002bx5',
    'frequency': 500000,
    'connect_mode': 'halt',
    'resume_on_disconnect': False
}

session = Session(probe, options=options, init_board=False)
session.open(init_board=False)

start_time = time.time()
timeout = 60
attempts = 0
last_tick = start_time
caught = False

try:
    while time.time() - start_time < timeout:
        attempts += 1
        try:
            session.target.aps.clear()
            session.target.cores.clear()
            seq = session.target.create_init_sequence()
            seq.invoke()
            session.board._inited = True
            caught = True
            log(f"\n[🔥] ПЛАТА ОБНАРУЖЕНА НА SWD! (попытка #{attempts})")
            log("[!] Ядро Cortex-M0+ успешно переведено в HALT.")

            log("\n[*] Стирание и запись новой прошивки...")
            programmer = FileProgrammer(session)
            programmer.program(bin_file)

            log("\n" + "=" * 60)
            log("   🎉 ПРОШИВКА УСПЕШНО ЗАЛИТА В ПЛАТУ!")
            log("=" * 60)

            try:
                session.target.reset()
                log("[✓] Контроллер перезапущен в рабочий режим.")
            except Exception:
                pass
            break

        except Exception:
            time.sleep(0.05)
            now = time.time()
            if now - last_tick >= 3.0:
                last_tick = now
                left = int(timeout - (now - start_time))
                log(f"[...] Ожидаю контакт с чипом... осталось {left} сек")

except KeyboardInterrupt:
    log("\nОстановлено пользователем.")
finally:
    session.close()

if not caught:
    log("\n[X] Таймаут: плата не ответила на линии SWD.")
    sys.exit(2)
