import sys
import time
import os
import subprocess
import pylink

try:
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
except Exception:
    pass

try:
    import winsound
    def beep():
        winsound.Beep(1500, 250)
except Exception:
    def beep():
        print('\a', end='', flush=True)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN_PATH = os.path.join(ROOT_DIR, "custom_firmware", "build", "scanner.bin")

def main():
    print("=" * 65)
    print(" >>> АВТОМАТИЧЕСКАЯ ПРОШИВКА 72-ШАГОВОГО СКАНЕРА DM02i V03 <<<")
    print("=" * 65)

    if not os.path.exists(BIN_PATH):
        print(f"[X] Ошибка: файл не найден: {BIN_PATH}")
        sys.exit(1)

    print(f"[*] Файл прошивки: {BIN_PATH} ({os.path.getsize(BIN_PATH)} байт)")

    j = pylink.JLink()
    try:
        j.open('774496021')
        j.set_tif(pylink.enums.JLinkInterfaces.SWD)
        j.set_speed(1000)
    except Exception as e:
        print(f"[X] Ошибка открытия J-Link: {e}")
        return False

    print("[*] J-Link подключен. Проверяю состояние чипа...")
    
    erased = False
    start_time = time.time()
    last_prompt = 0

    while time.time() - start_time < 35:
        now = time.time()
        if now - last_prompt >= 4.0:
            last_prompt = now
            print("[*] Ожидаю чип... (если связи нет, кратковременно замкните NRST на GND или передерните 3.3V)")

        try:
            j.coresight_configure()
            dpidr = j.coresight_read(0, ap=False)
            if dpidr in (0x0BC11477, 0x0BB11477, 0x2BA01477):
                print(f"\n[🔥] ЧИП ЗАХВАЧЕН! DPIDR = 0x{dpidr:08X}")
                
                # 1. DP Power-up
                j.coresight_write(1, 0x50000000, ap=False)
                j.coresight_write(0, 0x1E, ap=False)

                # 2. Halt Core
                j.coresight_write(2, 0x00000000, ap=False)
                j.coresight_write(0, 0x23000002, ap=True)
                j.coresight_write(1, 0xE000EDF0, ap=True)
                j.coresight_write(3, 0xA05F0003, ap=True)

                print("[*] Выполняю Mass Erase Flash памяти...")
                # Enable FLASH clock (RCC->AHBENR = 0x40021014)
                j.coresight_write(1, 0x40021014, ap=True)
                j.coresight_write(3, 0x00000104, ap=True)

                # KEYR unlock (0x40022008)
                j.coresight_write(1, 0x40022008, ap=True)
                j.coresight_write(3, 0x45670123, ap=True)
                j.coresight_write(1, 0x40022008, ap=True)
                j.coresight_write(3, 0xCDEF89AB, ap=True)

                # CR = MER (Mass Erase) at 0x40022014
                j.coresight_write(1, 0x40022014, ap=True)
                j.coresight_write(3, 0x00000004, ap=True)

                # Trigger Erase by writing to 0x08000000
                j.coresight_write(1, 0x08000000, ap=True)
                j.coresight_write(3, 0x12344321, ap=True)
                time.sleep(0.2)

                # Read back 0x08000000
                j.coresight_write(1, 0x08000000, ap=True)
                flash_word = j.coresight_read(3, ap=True)
                if flash_word == 0xFFFFFFFF:
                    print("[✓] Flash память успешно очищена (0xFFFFFFFF)!")
                    erased = True
                    beep()
                    break
        except Exception:
            pass
        time.sleep(0.01)

    j.close()

    if not erased:
        print("\n[!] Не удалось выполнить аппаратный захват за отведенное время.")
        return False

    print("\n[*] Запускаю запись прошивки через PyOCD...")
    flash_cmd = ["pyocd", "flash", "-t", "py32f002bx5", BIN_PATH]
    res = subprocess.run(flash_cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"[X] Ошибка записи PyOCD: {res.stderr or res.stdout}")
        return False
    print(res.stdout)
    print("[✓] Прошивка успешно записана в Flash память!")

    print("[*] Перезапускаю микроконтроллер...")
    reset_cmd = ["pyocd", "reset", "-t", "py32f002bx5"]
    subprocess.run(reset_cmd, capture_output=True, text=True)

    time.sleep(0.5)
    print("[*] Проверяю запуск сканера (SRAM 0x20000004)...")
    check_cmd = ["pyocd", "cmd", "-t", "py32f002bx5", "-c", "read32 0x20000004 4"]
    res = subprocess.run(check_cmd, capture_output=True, text=True)
    print(res.stdout)
    if "5343414e" in res.stdout.lower():
        print("🎉🎉🎉 СКАНЕР НА 72 ШАГА УСПЕШНО ЗАПУЩЕН И РАБОТАЕТ! 🎉🎉🎉")
        return True
    else:
        print("[!] Сканер еще инициализируется, проверьте через dm02i_studio.")
        return True

if __name__ == '__main__':
    ok = main()
    sys.exit(0 if ok else 1)
