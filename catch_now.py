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
    log("   >>> ЛОВУШКА ДЛЯ ПРОШИВКИ ПРИ ПЕРЕПОДКЛЮЧЕНИИ ПИТАНИЯ <<<")
    log("=" * 65)
    log(f"Файл прошивки: {os.path.basename(BIN_PATH)} ({os.path.getsize(BIN_PATH)} байт)")
    log("Частота сканирования: 200 раз в секунду.")
    log("-" * 65)
    log("ИНСТРУКЦИЯ: Прямо сейчас отключите и снова подключите провод 3.3V")
    log("(или переткните программатор в USB).")
    log("-" * 65)
    log("Слушаю шину SWD (таймаут 90 сек)...")

    j = pylink.JLink()
    try:
        j.open('774496021')
        j.set_tif(pylink.enums.JLinkInterfaces.SWD)
        j.set_speed(1000)
    except Exception as e:
        log(f"[X] Ошибка открытия J-Link: {e}")
        sys.exit(1)

    start_time = time.time()
    timeout = 600
    last_tick = start_time
    caught = False
    attempts = 0

    while time.time() - start_time < timeout:
        attempts += 1
        try:
            j.coresight_configure()
            dpidr = j.coresight_read(0, ap=False)
            if dpidr in (0x0BC11477, 0x0BB11477, 0x2BA01477):
                # Request debug & system power-up
                j.coresight_write(1, 0x50000000, ap=False)
                j.coresight_write(0, 0x1E, ap=False) # Clear abort
                
                ctrl = j.coresight_read(1, ap=False)
                cdbgpwrupack = (ctrl >> 29) & 1
                
                if cdbgpwrupack:
                    # Debug power is UP! Core is awake or waking up!
                    # AP 0 Bank 0
                    j.coresight_write(2, 0x00000000, ap=False)
                    # CSW: 32-bit transfer
                    j.coresight_write(0, 0x23000002, ap=True)
                    # TAR: DHCSR (0xE000EDF0)
                    j.coresight_write(1, 0xE000EDF0, ap=True)
                    # DRW: C_DEBUGEN | C_HALT (0xA05F0003)
                    j.coresight_write(3, 0xA05F0003, ap=True)
                    
                    # Read back DHCSR
                    j.coresight_write(1, 0xE000EDF0, ap=True)
                    dhcsr = j.coresight_read(3, ap=True)
                    
                    if dhcsr & 0x00030000: # S_HALT bit is set!
                        log(f"\n[{time.strftime('%H:%M:%S')}] ⚡ ЕСТЬ ЗАХВАТ ЯДРА! DPIDR = 0x{dpidr:08X}, DHCSR = 0x{dhcsr:08X} (попытка #{attempts})")
                        caught = True
                        break
        except Exception:
            pass

        time.sleep(0.005)
        now = time.time()
        if now - last_tick >= 3.0:
            last_tick = now
            left = int(timeout - (now - start_time))
            log(f"[...] Слушаю шину SWD ({attempts} опросов)... осталось {left} сек")

    try:
        j.close()
    except Exception:
        pass

    if not caught:
        log("\n[X] Таймаут 90 сек: отклик сброса не обнаружен.")
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
        # Reset MCU into run mode
        subprocess.run(["pyocd", "reset", "-t", "py32f002bx5"], capture_output=True)
        log("[✓] Контроллер перезапущен в штатный рабочий режим.")
        return True
    else:
        log("\n[!] Ошибка на этапе pyocd flash.")
        return False

if __name__ == '__main__':
    main()
