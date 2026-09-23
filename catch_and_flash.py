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

def main():
    bin_file = sys.argv[1] if len(sys.argv) > 1 else r"c:\Users\Salomanov\Desktop\ВЕЙП\custom_firmware\build\battery_firmware.bin"
    if not os.path.exists(bin_file):
        log(f"[X] Файл прошивки не найден: {bin_file}")
        sys.exit(1)

    log("=" * 60)
    log("      АВТОМАТИЧЕСКАЯ ЛОВУШКА И ПРОШИВКА PUYA PY32")
    log("=" * 60)

    probes = ConnectHelper.get_all_connected_probes(blocking=False)
    if not probes:
        log("[!] Ошибка: Программатор не обнаружен в USB!")
        sys.exit(1)

    probe = probes[0]
    log(f"Программатор: {probe.description} (SN: {probe.unique_id})")

    options = {
        'target_override': 'py32f002bx5',
        'frequency': 1000000,
        'connect_mode': 'halt',
        'resume_on_disconnect': False
    }

    session = Session(probe, options=options, init_board=False)
    session.open(init_board=False)

    log("\n>>> [ ЛОВУШКА АКТИВИРОВАНА ] <<<")
    log("Частота опроса шины: ~70 раз в секунду.")
    log("------------------------------------------------------------")
    log("ДЕЙСТВИЕ: Прямо сейчас отключите и снова подключите провод 3.3V")
    log("(или переткните программатор в USB).")
    log("------------------------------------------------------------")
    log("Ожидаю включения микроконтроллера (таймаут 10 минут / 600 сек)...")

    start_time = time.time()
    timeout = 600
    attempts = 0
    last_heartbeat = start_time
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
                elapsed = time.time() - start_time
                log(f"\n[🔥] ЕСТЬ КОНТАКТ! ЧИП ПОЙМАН на {elapsed:.2f} сек (попытка #{attempts})!")
                log("[!] Ядро Cortex-M0+ успешно переведено в HALT!")

                try:
                    cpuid = session.target.read32(0xE000ED00)
                    log(f"[*] CPUID: 0x{cpuid:08X}")
                except Exception:
                    pass

                log("\n[*] Прошиваем battery_firmware.bin...")
                programmer = FileProgrammer(session)
                programmer.program(bin_file)
                log("\n============================================================")
                log("   🎉 ПРОШИВКА УСПЕШНО ЗАВЕРШЕНА!")
                log(f"   Файл: {os.path.basename(bin_file)} ({os.path.getsize(bin_file)} байт)")
                log("   Дисплей FH8016 (PA1), сенсор M+ (PB4), зарядка C60H (PB5)")
                log("============================================================")

                try:
                    session.target.reset()
                    log("[✓] Контроллер перезапущен в рабочий режим.")
                except Exception:
                    pass

                break

            except Exception:
                time.sleep(0.005)

            now = time.time()
            if now - last_heartbeat >= 2.0:
                last_heartbeat = now
                left = int(timeout - (now - start_time))
                rate = int(attempts / (now - start_time)) if (now - start_time) > 0 else 0
                log(f"[...] Слушаю шину SWD ({rate} попыток/сек)... осталось {left} сек")

    except KeyboardInterrupt:
        log("\nЛовушка остановлена пользователем.")
    finally:
        session.close()

    if not caught:
        log("\n[X] Время ожидания истекло. Чип не ответил.")
        sys.exit(2)

if __name__ == '__main__':
    main()
