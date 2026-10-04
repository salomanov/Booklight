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
    def beep(freq=1500, dur=250):
        winsound.Beep(freq, dur)
except Exception:
    def beep(freq=1500, dur=250):
        print('\a', end='', flush=True)

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
BIN_PATH = os.path.join(ROOT_DIR, "custom_firmware", "build", "scanner.bin")
for arg in sys.argv[1:]:
    if arg.endswith(".bin") and os.path.exists(arg):
        BIN_PATH = os.path.abspath(arg)
        break

def main():
    print("=" * 65)
    print(" >>> АППАРАТНАЯ ПРОШИВКА PUYA PY32 (С ПОСТОЯННОЙ ОТЛАДКОЙ) <<<")
    print("=" * 65)

    if not os.path.exists(BIN_PATH):
        print(f"[X] Файл не найден: {BIN_PATH}")
        input("Нажмите Enter...")
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
        if j.num_connected_emulators() > 0:
            try:
                j.open('774496021')
            except Exception:
                j.open()
        else:
            j.open()
        j.set_tif(pylink.enums.JLinkInterfaces.SWD)
        j.set_speed(500) # Safe 500 kHz for clone jumper wires
    except Exception as e:
        print(f"[X] Ошибка открытия J-Link: {e}")
        input("Нажмите Enter...")
        return False

    print(f"[*] J-Link подключен (SN: {j.serial_number})")

    if "--check" in sys.argv:
        print("[✓] ПРОВЕРКА ЗАПУСКА: Все модули, прошивка и программатор J-Link готовы к работе!")
        j.close()
        return True

    print("\n" + "=" * 65)
    print(" >>> ОЖИДАЮ ЧИП (КАСАНИЕ NRST К GND ИЛИ 3.3V) <<<")
    print(" Коснитесь пина 'R' (NRST) на землю 'G' (GND) ОДИН РАЗ И ОТПУСТИТЕ!")
    print("=" * 65 + "\n")

    start_time = time.time()
    attempts = 0
    caught = False
    last_status = time.time()

    # PHASE 1: Capture chip and Halt Core
    while time.time() - start_time < 120:
        attempts += 1
        now = time.time()
        if now - last_status >= 3.0:
            last_status = now
            print(f"[*] Ожидаю захвата чипа... (попыток: {attempts})")
        try:
            j.coresight_configure()
            dpidr = j.coresight_read(0, ap=False)
            if dpidr in (0x0BC11477, 0x0BB11477, 0x2BA01477):
                # 1. DP Power-up
                j.coresight_write(1, 0x50000000, ap=False)
                j.coresight_write(0, 0x1E, ap=False)

                # 2. Halt Core in Reset Vector
                j.coresight_write(2, 0x00000000, ap=False)
                j.coresight_write(0, 0x23000002, ap=True) # CSW
                j.coresight_write(1, 0xE000EDF0, ap=True) # DHCSR
                j.coresight_write(3, 0xA05F0003, ap=True) # HALT | DEBUGEN

                caught = True
                beep(1800, 200)
                print(f"\n[🔥] ЧИП ЗАХВАЧЕН! DPIDR = 0x{dpidr:08X} (попытка #{attempts})")
                print(">>> ВНИМАНИЕ: ОТПУСТИТЕ ПРОВОД/ПИНЦЕТ! НЕ ТРОГАЙТЕ ПЛАТУ! <<<")
                break
        except Exception:
            pass
        time.sleep(0.005)

    if not caught:
        print("\n[X] Время ожидания истекло. Чип не ответил.")
        j.close()
        return False

    time.sleep(0.1)

    # PHASE 2: Flash Erase & Programming (Isolated outside capture loop)
    try:
        # Give user time to release wire/tweezer and settle bus
        time.sleep(0.4)

        # Clear aborts
        j.coresight_write(0, 0x1E, ap=False)
        j.coresight_write(2, 0x00000000, ap=False) # AP 0 Bank 0
        j.coresight_write(0, 0x23000002, ap=True)  # CSW 32-bit non-increment

        # 3. Enable FLASH & SRAM clock in RCC->AHBENR (0x40021014)
        j.coresight_write(1, 0x40021014, ap=True)
        j.coresight_write(3, 0x00000104, ap=True)

        # 4. KEYR unlock
        j.coresight_write(1, 0x40022008, ap=True)
        j.coresight_write(3, 0x45670123, ap=True)
        j.coresight_write(1, 0x40022008, ap=True)
        j.coresight_write(3, 0xCDEF89AB, ap=True)

        # 5. Mass Erase
        print("[*] Выполняю Mass Erase Flash памяти...")
        j.coresight_write(1, 0x40022014, ap=True) # FLASH->CR
        j.coresight_write(3, 0x00000004, ap=True) # MER bit
        j.coresight_write(1, 0x08000000, ap=True)
        j.coresight_write(3, 0x12344321, ap=True) # Dummy write to start erase

        # Wait for Mass Erase completion via BSY flag in FLASH->SR (0x40022010)
        time.sleep(0.05)
        for _ in range(100):
            j.coresight_write(1, 0x40022010, ap=True)
            sr = j.coresight_read(3, ap=True)
            if not (sr & 0x00010000): # BSY == 0
                break
            time.sleep(0.005)

        # Clear MER bit in FLASH->CR
        j.coresight_write(1, 0x40022014, ap=True)
        j.coresight_write(3, 0x00000000, ap=True)
        j.coresight_write(0, 0x1E, ap=False) # Clear any aborts

        print(f"[*] Программирую {num_pages} страниц ({total_bytes} байт)...")

        # Unlock KEYR again for programming
        j.coresight_write(1, 0x40022008, ap=True)
        j.coresight_write(3, 0x45670123, ap=True)
        j.coresight_write(1, 0x40022008, ap=True)
        j.coresight_write(3, 0xCDEF89AB, ap=True)

        flash_addr = 0x08000000

        for page_idx in range(num_pages):
            page_bytes = padded_data[page_idx * page_size : (page_idx + 1) * page_size]
            words = struct.unpack('<32I', page_bytes)
            cur_addr = flash_addr + page_idx * page_size

            # Set PG bit with non-increment CSW
            j.coresight_write(0, 0x23000002, ap=True)
            j.coresight_write(1, 0x40022014, ap=True)
            j.coresight_write(3, 0x00000001, ap=True)

            # Auto-increment CSW for words 0..30
            j.coresight_write(0, 0x23000012, ap=True)
            j.coresight_write(1, cur_addr, ap=True)
            for i in range(31):
                j.coresight_write(3, words[i], ap=True)

            # Non-increment CSW for PGSTRT | PG (0x00080001)
            j.coresight_write(0, 0x23000002, ap=True)
            j.coresight_write(1, 0x40022014, ap=True)
            j.coresight_write(3, 0x00080001, ap=True)

            # Write word 31
            j.coresight_write(1, cur_addr + 31 * 4, ap=True)
            j.coresight_write(3, words[31], ap=True)

            # Wait for BSY to clear
            time.sleep(0.003)
            for _ in range(50):
                j.coresight_write(1, 0x40022010, ap=True)
                sr = j.coresight_read(3, ap=True)
                if not (sr & 0x00010000):
                    break
                time.sleep(0.001)

            # Clear PG bit
            j.coresight_write(1, 0x40022014, ap=True)
            j.coresight_write(3, 0x00000000, ap=True)

            percent = int((page_idx + 1) * 100 / num_pages)
            sys.stdout.write(f"\rЗапись: [{('=' * (percent // 4)).ljust(25)}] {percent}% (стр. {page_idx+1}/{num_pages})")
            sys.stdout.flush()

        print("\n[✓] Запись завершена! Выполняю 100% верификацию...")

        # Per-page auto-increment verification (safe against 1KB boundary wrap-around)
        j.coresight_write(0, 0x23000012, ap=True) # Auto-increment CSW

        verified = True
        for p in range(num_pages):
            cur_addr = flash_addr + p * page_size
            j.coresight_write(1, cur_addr, ap=True)
            exp_words = struct.unpack('<32I', padded_data[p * page_size : (p + 1) * page_size])
            for i in range(32):
                read_w = j.coresight_read(3, ap=True)
                if read_w != exp_words[i]:
                    addr = cur_addr + i * 4
                    print(f"\n[X] Ошибка верификации по адресу 0x{addr:08X}: записано 0x{exp_words[i]:08X}, прочитано 0x{read_w:08X}")
                    verified = False
                    break
            if not verified:
                break

        # Restore non-increment CSW
        j.coresight_write(0, 0x23000002, ap=True)

        if not verified:
            print("[X] Ошибка верификации памяти!")
            j.close()
            return False

        print(f"[✓] ВЕРИФИКАЦИЯ 100% УСПЕШНА! Все {total_bytes} байт проверены!")
        beep(2000, 300)

        # Reset core to run firmware with permanent debug enabled
        print("[*] Перезапускаю процессор в рабочий режим с ПОСТОЯННОЙ ОТЛАДКОЙ...")
        j.coresight_write(0, 0x23000002, ap=True)
        j.coresight_write(1, 0xE000EDF0, ap=True)
        j.coresight_write(3, 0xA05F0001, ap=True) # C_DEBUGEN only (run core)
        j.coresight_write(1, 0xE000ED0C, ap=True)
        j.coresight_write(3, 0x05FA0004, ap=True) # AIRCR SYSRESETREQ
        time.sleep(0.3)

        # Check SRAM for SCAN magic
        try:
            j.coresight_write(1, 0x20000004, ap=True)
            magic = j.coresight_read(3, ap=True)
            print(f"[*] Проверка ОЗУ сканера (0x20000004): 0x{magic:08X}")
            if magic == 0x5343414E:
                print("\n" + "=" * 65)
                print("  🎉🎉🎉 ПРОШИВКА УСПЕШНО ЗАПУЩЕНА И РАБОТАЕТ! 🎉🎉🎉")
                print("  Отладка активна 24/7. Стирать чип больше НИКОГДА не нужно!")
                print("=" * 65)
        except Exception:
            print("[*] Контроллер перезапущен в рабочий режим.")

        j.close()
        return True

    except Exception as e_flash:
        print(f"\n[X] Ошибка во время прошивки: {e_flash}")
        try:
            j.close()
        except Exception:
            pass
        return False

if __name__ == '__main__':
    ok = main()
    sys.exit(0 if ok else 1)
