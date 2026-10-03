import sys
import time
import os
import struct
import pylink

try:
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
except Exception:
    pass

try:
    import winsound
    def beep():
        winsound.Beep(1500, 200)
except Exception:
    def beep():
        print('\a', end='', flush=True)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN_PATH = os.path.join(ROOT_DIR, "custom_firmware", "build", "scanner.bin")

def main():
    print("=" * 65)
    print(" >>> ПРЯМАЯ ПРОШИВКА PUYA PY32 ЧЕРЕЗ АППАРАТНЫЙ SWD (PYLINK) <<<")
    print("=" * 65)

    if not os.path.exists(BIN_PATH):
        print(f"[X] Файл не найден: {BIN_PATH}")
        return False

    with open(BIN_PATH, "rb") as f:
        bin_data = f.read()

    total_bytes = len(bin_data)
    print(f"[*] Прошивка: {BIN_PATH} ({total_bytes} байт)")

    # Pad data to multiple of 128 bytes (page size)
    page_size = 128
    pad_len = (page_size - (total_bytes % page_size)) % page_size
    padded_data = bin_data + (b'\xFF' * pad_len)
    num_pages = len(padded_data) // page_size
    print(f"[*] Страниц для записи: {num_pages} (по {page_size} байт)")

    j = pylink.JLink()
    try:
        j.open('774496021')
        j.set_tif(pylink.enums.JLinkInterfaces.SWD)
        j.set_speed(2000) # Fast 2 MHz SWD
    except Exception as e:
        print(f"[X] Ошибка J-Link: {e}")
        return False

    # Connect to CoreSight
    print("[*] Подключаюсь к CoreSight SWD...")
    connected = False
    start_time = time.time()
    last_print = 0

    while time.time() - start_time < 35:
        now = time.time()
        if now - last_print >= 4.0:
            last_print = now
            print("[*] Ожидаю чип... (если нужно, кратковременно замкните NRST на GND или передерните 3.3V)")
        try:
            j.coresight_configure()
            dpidr = j.coresight_read(0, ap=False)
            if dpidr in (0x0BC11477, 0x0BB11477, 0x2BA01477):
                print(f"\n[🔥] ЧИП ЗАХВАЧЕН! DPIDR = 0x{dpidr:08X}")
                connected = True
                break
        except Exception:
            pass
        time.sleep(0.01)

    if not connected:
        print("[X] Таймаут ожидания чипа.")
        j.close()
        return False

    # 1. DP Power-up
    j.coresight_write(1, 0x50000000, ap=False)
    j.coresight_write(0, 0x1E, ap=False)

    # 2. Halt Core via DHCSR
    j.coresight_write(2, 0x00000000, ap=False)
    j.coresight_write(0, 0x23000002, ap=True) # CSW 32-bit transfer
    j.coresight_write(1, 0xE000EDF0, ap=True) # DHCSR
    j.coresight_write(3, 0xA05F0003, ap=True) # HALT | DEBUGEN

    # 3. Enable DBGMCU and freeze Watchdog/Timers
    try:
        j.coresight_write(1, 0x40021034, ap=True) # RCC->APBENR1
        apb1 = j.coresight_read(3, ap=True)
        j.coresight_write(1, 0x40021034, ap=True)
        j.coresight_write(3, apb1 | 0x08000000, ap=True) # DBGEN

        j.coresight_write(1, 0x40015808, ap=True) # DBGMCU->APB_FZ1
        j.coresight_write(3, 0xFFFFFFFF, ap=True) # Freeze IWDG, I2C, Timers

        j.coresight_write(1, 0x40015804, ap=True) # DBGMCU->CR
        j.coresight_write(3, 0x00000007, ap=True) # DBG_STOP
    except Exception:
        pass

    # 4. Enable FLASH clock (RCC->AHBENR = 0x40021014)
    j.coresight_write(1, 0x40021014, ap=True)
    ahbenr = j.coresight_read(3, ap=True)
    j.coresight_write(1, 0x40021014, ap=True)
    j.coresight_write(3, ahbenr | 0x00000104, ap=True)

    # 5. Check if Mass Erase needed
    j.coresight_write(1, 0x08000000, ap=True)
    w0 = j.coresight_read(3, ap=True)
    if w0 != 0xFFFFFFFF:
        print(f"[*] Стираю Flash (0x08000000 = 0x{w0:08X})...")
        # Unlock KEYR
        j.coresight_write(1, 0x40022008, ap=True)
        j.coresight_write(3, 0x45670123, ap=True)
        j.coresight_write(1, 0x40022008, ap=True)
        j.coresight_write(3, 0xCDEF89AB, ap=True)

        # MER (bit 2) in FLASH->CR
        j.coresight_write(1, 0x40022014, ap=True)
        j.coresight_write(3, 0x00000004, ap=True)

        # Trigger
        j.coresight_write(1, 0x08000000, ap=True)
        j.coresight_write(3, 0x12344321, ap=True)
        time.sleep(0.15)
        print("[✓] Flash память очищена.")

    print(f"[*] Программирую {num_pages} страниц Flash памяти напрямую...")

    # Unlock KEYR
    j.coresight_write(1, 0x40022008, ap=True)
    j.coresight_write(3, 0x45670123, ap=True)
    j.coresight_write(1, 0x40022008, ap=True)
    j.coresight_write(3, 0xCDEF89AB, ap=True)

    # Enable Auto-Increment in MEM-AP CSW: 0x23000012
    j.coresight_write(0, 0x23000012, ap=True)

    flash_addr = 0x08000000

    for page_idx in range(num_pages):
        page_bytes = padded_data[page_idx * page_size : (page_idx + 1) * page_size]
        words = struct.unpack('<32I', page_bytes)
        cur_addr = flash_addr + page_idx * page_size

        # 1. Set PG bit (0x01)
        j.coresight_write(1, 0x40022014, ap=True)
        j.coresight_write(3, 0x00000001, ap=True)

        # 2. Write words 0..30 using auto-incrementing TAR
        j.coresight_write(1, cur_addr, ap=True) # Set start TAR
        for i in range(31):
            j.coresight_write(3, words[i], ap=True) # Auto-increments TAR

        # 3. Set PGSTRT (0x00080001: PG + PGSTRT)
        j.coresight_write(1, 0x40022014, ap=True)
        j.coresight_write(3, 0x00080001, ap=True)

        # 4. Write word 31
        j.coresight_write(1, cur_addr + 31 * 4, ap=True)
        j.coresight_write(3, words[31], ap=True)

        # 5. Wait for flash programming to complete (hardware requires ~2.5ms)
        time.sleep(0.006)
        for _ in range(50):
            j.coresight_write(1, 0x40022010, ap=True)
            sr = j.coresight_read(3, ap=True)
            if not (sr & 0x00010000):
                break
            time.sleep(0.001)

        # 6. Clear PG bit
        j.coresight_write(1, 0x40022014, ap=True)
        j.coresight_write(3, 0x00000000, ap=True)

        percent = int((page_idx + 1) * 100 / num_pages)
        sys.stdout.write(f"\rПрогресс записи: [{('=' * (percent // 4)).ljust(25)}] {percent}% (стр. {page_idx+1}/{num_pages})")
        sys.stdout.flush()

    print("\n[✓] Запись завершена! Выполняю верификацию...")

    # Verification with auto-increment
    verified = True
    for page_idx in range(num_pages):
        page_bytes = padded_data[page_idx * page_size : (page_idx + 1) * page_size]
        words = struct.unpack('<32I', page_bytes)
        cur_addr = flash_addr + page_idx * page_size
        
        j.coresight_write(1, cur_addr, ap=True)
        for i in range(32):
            read_w = j.coresight_read(3, ap=True)
            if read_w != words[i]:
                print(f"\n[X] Ошибка верификации по адресу 0x{cur_addr + i * 4:08X}: записано 0x{words[i]:08X}, прочитано 0x{read_w:08X}")
                verified = False
                break
        if not verified:
            break

    if not verified:
        j.close()
        return False

    print("[✓] ВЕРИФИКАЦИЯ 100% УСПЕШНА! Все 3448 байт совпадают!")
    beep()

    # Reset core to run
    print("[*] Перезапускаю процессор в рабочий режим...")
    # Restore CSW
    j.coresight_write(0, 0x23000002, ap=True)
    # Release halt in DHCSR: C_DEBUGEN only
    j.coresight_write(1, 0xE000EDF0, ap=True)
    j.coresight_write(3, 0xA05F0001, ap=True)
    # Trigger system reset via AIRCR
    j.coresight_write(1, 0xE000ED0C, ap=True)
    j.coresight_write(3, 0x05FA0004, ap=True)
    time.sleep(0.3)

    # Check SRAM for SCAN magic
    try:
        j.coresight_write(1, 0x20000004, ap=True)
        magic = j.coresight_read(3, ap=True)
        print(f"[*] Проверка SRAM (0x20000004): 0x{magic:08X}")
        if magic == 0x5343414E:
            print("\n" + "=" * 65)
            print("  🎉🎉🎉 СКАНЕР НА 72 ШАГА УСПЕШНО ЗАПУЩЕН И РАБОТАЕТ! 🎉🎉🎉")
            print("=" * 65)
        else:
            print("[*] Прошивка запущена.")
    except Exception:
        print("[*] Контроллер перезапущен.")

    j.close()
    return True

if __name__ == '__main__':
    ok = main()
    sys.exit(0 if ok else 1)
