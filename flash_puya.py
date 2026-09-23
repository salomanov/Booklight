import sys
import time
import os

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

from pyocd.core.helpers import ConnectHelper
from pyocd.core.session import Session
from pyocd.flash.eraser import FlashEraser
from pyocd.flash.file_programmer import FileProgrammer

def log(msg):
    print(msg, flush=True)

def main():
    bin_file = r"c:\Users\Salomanov\Desktop\ВЕЙП\custom_firmware\build\battery_firmware.bin"
    if not os.path.exists(bin_file):
        log(f"[X] Ошибка: файл не найден: {bin_file}")
        sys.exit(1)

    log("=" * 60)
    log("      АВТОМАТИЧЕСКАЯ ПРОШИВКА МИКРОКОНТРОЛЛЕРА PY32")
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

    log("\n>>> [ ЛОВУШКА АКТИВИРОВАНА (ТАЙМАУТ 90 СЕКУНД) ] <<<")
    log("------------------------------------------------------------")
    log("ДЕЙСТВИЕ ДЛЯ ПОЛЬЗОВАТЕЛЯ:")
    log("Прямо сейчас ОТКЛЮЧИТЕ красный провод 3.3V на 1 секунду")
    log("и ПОДКЛЮЧИТЕ ЕГО ОБРАТНО!")
    log("(или переподключите программатор в USB)")
    log("------------------------------------------------------------")
    log("Ожидаю момента включения платы...")

    start_time = time.time()
    timeout = 90
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
                log(f"\n[🔥] ЕСТЬ КОНТАКТ! ЧИП ПОЙМАН на {elapsed:.2f} сек!")
                log("[!] Ядро Cortex-M0+ остановлено (HALT)!")

                log("[1/2] Стираем Flash (Mass Erase)...")
                try:
                    eraser = FlashEraser(session, FlashEraser.Mode.CHIP)
                    eraser.erase()
                    log("[✓] Память успешно очищена!")
                except Exception as ee:
                    log(f"[*] Стандартный erase вернул: {ee}, шьем напрямую...")

                log(f"[2/2] Заливаем прошивку {os.path.basename(bin_file)} ({os.path.getsize(bin_file)} байт)...")
                programmer = FileProgrammer(session)
                programmer.program(bin_file)
                log("\n" + "=" * 60)
                log("   🎉🎉🎉 ПОЗДРАВЛЯЮ! ЧИП УСПЕШНО ПРОШИТ! 🎉🎉🎉")
                log("   Прошивка: battery_firmware.bin")
                log("   Дисплей FH8016 (PA1), сенсор M+ (PB4), зарядка C60H (PB5)")
                log("=" * 60)

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
        log("\nЛовушка остановлена.")
    finally:
        session.close()

    if not caught:
        log("\n[X] Время ожидания истекло. Чип не ответил.")
        sys.exit(2)

if __name__ == '__main__':
    main()
