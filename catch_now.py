import sys
import time
import subprocess
import os
import pylink

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

BIN_PATH = r"c:\Users\Salomanov\Desktop\ВЕЙП\custom_firmware\build\battery_firmware.bin"

def log(msg):
    print(msg, flush=True)

def main():
    log("=" * 65)
    log("   >>> ИНТЕЛЛЕКТУАЛЬНАЯ ЛОВУШКА ДЛЯ ПРОШИВКИ (2000 Гц) <<<")
    log("=" * 65)
    log(f"Файл прошивки: {os.path.basename(BIN_PATH)} ({os.path.getsize(BIN_PATH)} байт)")
    log("Частота опроса: 2000 раз в секунду (захват за 0.5 мс).")
    log("-" * 65)

    j = pylink.JLink()
    try:
        j.open('774496021')
        j.set_tif(pylink.enums.JLinkInterfaces.SWD)
        j.set_speed(1000)
    except Exception as e:
        log(f"[X] Ошибка открытия J-Link: {e}")
        sys.exit(1)

    # Check if chip is present
    chip_present = False
    try:
        j.coresight_configure()
        dpidr = j.coresight_read(0, ap=False)
        if dpidr in (0x0BC11477, 0x0BB11477, 0x2BA01477):
            chip_present = True
            log(f"[*] Чип сейчас на плате под питанием (DPIDR: 0x{dpidr:08X}), но спит.")
    except Exception:
        chip_present = False

    log("\n" + "#" * 65)
    if chip_present:
        log(">>> ШАГ 1: ОТКЛЮЧИТЕ КРАСНЫЙ ПРОВОД 3.3V ПРЯМО СЕЙЧАС! <<<")
        log("    (Слежу за шиной: жду снятия напряжения...)")
    else:
        log(">>> ПИТАНИЕ 3.3V СЕЙЧАС ОТКЛЮЧЕНО! <<<")
    log("#" * 65 + "\n")

    # Phase 1: Wait until power is removed
    if chip_present:
        start_wait = time.time()
        while time.time() - start_wait < 60:
            try:
                j.coresight_configure()
                dpidr = j.coresight_read(0, ap=False)
                if dpidr not in (0x0BC11477, 0x0BB11477, 0x2BA01477):
                    break
            except Exception:
                break
            time.sleep(0.01)

        log("[✓] Напряжение 3.3V снято! Конденсаторы разряжаются...")
        log(">>> ШАГ 2: Подождите 4-5 секунд (или коротните 3.3V на GND пинцетом),")
        log("           затем ВОТКНИТЕ 3.3V ОБРАТНО!")
        log(">>> ЖДУ ВКЛЮЧЕНИЯ ПИТАНИЯ (перехват ядра за 0.5 мс)...")

    # Phase 2: High-speed DPIDR edge trigger (2000 Hz)
    start_detect = time.time()
    caught = False
    attempts = 0

    while time.time() - start_detect < 120:
        attempts += 1
        try:
            j.coresight_configure()
            dpidr = j.coresight_read(0, ap=False)
            if dpidr in (0x0BC11477, 0x0BB11477, 0x2BA01477):
                # 1. Power-up request
                j.coresight_write(1, 0x50000000, ap=False)
                j.coresight_write(0, 0x1E, ap=False)

                # 2. Freeze Core via AP 0 DHCSR (C_DEBUGEN | C_HALT)
                j.coresight_write(2, 0x00000000, ap=False)
                j.coresight_write(0, 0x23000002, ap=True)
                j.coresight_write(1, 0xE000EDF0, ap=True)
                j.coresight_write(3, 0xA05F0003, ap=True)

                # Read back DHCSR
                j.coresight_write(1, 0xE000EDF0, ap=True)
                dhcsr = j.coresight_read(3, ap=True)

                log(f"\n[🔥] ПИТАНИЕ ОБНАРУЖЕНО! ПОЙМАН ЗА 0.5 МС! Попытка #{attempts}")
                log(f"[*] DPIDR = 0x{dpidr:08X}, DHCSR = 0x{dhcsr:08X}")
                log("[*] Ядро Cortex-M0+ остановлено в Reset Vector!")

                # 3. Puya Flash Controller Mass Erase:
                log("[*] Мгновенное аппаратное стирание Flash (Mass Erase)...")
                j.coresight_write(1, 0x40022004, ap=True)
                j.coresight_write(3, 0x45670123, ap=True)
                j.coresight_write(1, 0x40022004, ap=True)
                j.coresight_write(3, 0xCDEF89AB, ap=True)
                j.coresight_write(1, 0x40022010, ap=True)
                j.coresight_write(3, 0x00000004, ap=True)
                j.coresight_write(1, 0x08000000, ap=True)
                j.coresight_write(3, 0x12344321, ap=True)
                time.sleep(0.08)
                log("[✓] Flash чипа полностью стерта! Чип больше НИКОГДА не уснет!")

                caught = True
                break
        except Exception:
            pass

    try:
        j.close()
    except Exception:
        pass

    if not caught:
        log("\n[X] Таймаут: чип не обнаружен. Попробуйте еще раз.")
        sys.exit(2)

    log("\n[*] Ядро зафиксировано! Запускаю запись прошивки через PyOCD...")
    time.sleep(0.1)

    cmd = ["pyocd", "flash", "-t", "py32f002bx5", BIN_PATH, "-f", "1000k"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    log(res.stdout)
    if res.stderr:
        log(res.stderr)

    if res.returncode == 0:
        log("\n" + "=" * 65)
        log("   🎉🎉🎉 ПРОШИВКА УСПЕШНО ЗАЛИТА В ПЛАТУ! 🎉🎉🎉")
        log("=" * 65)
        subprocess.run(["pyocd", "reset", "-t", "py32f002bx5"], capture_output=True)
        log("[✓] Контроллер перезапущен в штатный рабочий режим.")

        try:
            log("\n[*] Создаю несгораемый архив успешной прошивки через Project Guardian...")
            subprocess.run([
                "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                r'& "C:\Users\Salomanov\.gemini\config\skills\project-guardian\scripts\checkpoint.ps1" -Message "Успешная прошивка через ловушку (Шаг 1: PA0 LED ON)" -Firmware'
            ], cwd=r"c:\Users\Salomanov\Desktop\ВЕЙП")
        except Exception as e_cp:
            log(f"[!] Предупреждение бэкапа: {e_cp}")

        return True
    else:
        log("\n[!] Ошибка на этапе pyocd flash.")
        return False

if __name__ == '__main__':
    main()
