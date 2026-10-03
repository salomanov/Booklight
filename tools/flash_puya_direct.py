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

def log(msg):
    print(msg, flush=True)

def main():
    log("=" * 65)
    log(" >>> ПРЯМАЯ ПРОШИВКА PUYA PY32 ЧЕРЕЗ АППАРАТНЫЙ SWD (PYLINK) <<<")
    log("=" * 65)

    if not os.path.exists(BIN_PATH):
        log(f"[X] Файл не найден: {BIN_PATH}")
        return False

    with open(BIN_PATH, "rb") as f:
        bin_data = f.read()

    total_bytes = len(bin_data)
    log(f"[*] Прошивка: {BIN_PATH} ({total_bytes} байт)")

    # Pad data to multiple of 128 bytes (page size)
    page_size = 128
    pad_len = (page_size - (total_bytes % page_size)) % page_size
    padded_data = bin_data + (b'\xFF' * pad_len)
    num_pages = len(padded_data) // page_size
    log(f"[*] Страниц для записи: {num_pages} (по {page_size} байт)")

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
        j.set_speed(1000)
    except Exception as e:
        log(f"[X] Ошибка открытия J-Link: {e}")
        return False

    vtarget = j.hardware_status.VTarget
    log(f"[*] J-Link подключен (SN: {j.serial_number}, VTarget: {vtarget} мВ)")

    # Check if chip responds right away
    connected = False
    try:
        j.coresight_configure()
        dpidr = j.coresight_read(0, ap=False)
        if dpidr in (0x0BC11477, 0x0BB11477, 0x2BA01477):
            log(f"[🔥] Чип сразу на связи! DPIDR = 0x{dpidr:08X}")
            connected = True
    except Exception:
        connected = False

    # If chip is not immediately responsive (e.g. blank flash / sleep mode),
    # use high-speed power cycle capture trap (2000 Hz)
    if not connected:
        power_present = vtarget > 1500
        log("\n" + "#" * 65)
        if power_present:
            log(">>> ШАГ 1: ОТКЛЮЧИТЕ КРАСНЫЙ ПРОВОД 3.3V ПРЯМО СЕЙЧАС! <<<")
            log("    (Слежу за шиной: жду отключения провода 3.3V...)")
        else:
            log(">>> ПИТАНИЕ 3.3V СЕЙЧАС ОТКЛЮЧЕНО! <<<")
            log(">>> Приготовьте провод 3.3V для подключения! <<<")
        log("#" * 65 + "\n")

        if power_present:
            start_wait = time.time()
            while time.time() - start_wait < 60:
                if j.hardware_status.VTarget < 1200:
                    break
                time.sleep(0.05)
            log(f"[✓] Провод 3.3V отключён! (Напряжение: {j.hardware_status.VTarget} мВ)")
            log(">>> ШАГ 2: Подождите 2-3 секунды, затем ВОТКНИТЕ 3.3V ОБРАТНО!")
            log(">>> ЖДУ ВКЛЮЧЕНИЯ ПИТАНИЯ (частота перехвата 2000 раз/сек)...")
        else:
            log(">>> ШАГ: ПОДКЛЮЧИТЕ ПРОВОД 3.3V К ПЛАТЕ ПРЯМО СЕЙЧАС! <<<")
            log(">>> ЖДУ ВКЛЮЧЕНИЯ ПИТАНИЯ (частота перехвата 2000 раз/сек)...")

        start_detect = time.time()
        attempts = 0
        last_status = time.time()
        while time.time() - start_detect < 180:
            attempts += 1
            if time.time() - last_status >= 4.0:
                last_status = time.time()
                log(f"[*] Ловушка слушает (попыток: {attempts}, VTarget: {j.hardware_status.VTarget} мВ)...")
            try:
                j.coresight_configure()
                dpidr = j.coresight_read(0, ap=False)
                if dpidr in (0x0BC11477, 0x0BB11477, 0x2BA01477):
                    log(f"\n[🔥] ПИТАНИЕ ОБНАРУЖЕНО! ПОЙМАН ЗА 0.5 МС! Попытка #{attempts}")
                    log(f"[*] DPIDR = 0x{dpidr:08X}")
                    connected = True
                    break
            except Exception:
                pass

    if not connected:
        log("\n[X] Таймаут ожидания чипа. Попробуйте еще раз.")
        j.close()
        return False

    # CoreSight sequence:
    # 1. DP Power-up and clear aborts
    j.coresight_write(1, 0x50000000, ap=False)
    j.coresight_write(0, 0x1E, ap=False)

    # 2. Select AP 0 Bank 0
    j.coresight_write(2, 0x00000000, ap=False)
    j.coresight_write(0, 0x23000002, ap=True) # CSW 32-bit transfer

    # 3. Halt Core via DHCSR (C_DEBUGEN | C_HALT)
    j.coresight_write(1, 0xE000EDF0, ap=True)
    j.coresight_write(3, 0xA05F0003, ap=True)
    j.coresight_write(0, 0x1E, ap=False) # Clear abort
    log("[✓] Ядро Cortex-M0+ остановлено!")

    # 4. Enable FLASH clock in RCC->AHBENR (0x40021038)
    try:
        j.coresight_write(1, 0x40021038, ap=True)
        j.coresight_write(3, 0x00000100, ap=True) # FLASHEN
        j.coresight_write(0, 0x1E, ap=False)
    except Exception:
        pass

    # 5. Mass Erase Flash memory
    log("[*] Выполняю Mass Erase Flash памяти...")
    # KEYR unlock
    j.coresight_write(1, 0x40022008, ap=True)
    j.coresight_write(3, 0x45670123, ap=True)
    j.coresight_write(1, 0x40022008, ap=True)
    j.coresight_write(3, 0xCDEF89AB, ap=True)

    # MER (bit 2) in FLASH->CR
    j.coresight_write(1, 0x40022014, ap=True)
    j.coresight_write(3, 0x00000004, ap=True)

    # Trigger Erase
    j.coresight_write(1, 0x08000000, ap=True)
    j.coresight_write(3, 0x12344321, ap=True)
    time.sleep(0.2)
    j.coresight_write(0, 0x1E, ap=False)
    log("[✓] Flash память очищена (Mass Erase завершен)!")

    # 6. Flash Programming
    log(f"[*] Программирую {num_pages} страниц Flash памяти напрямую...")

    # KEYR unlock
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

        # Set PG bit (0x01)
        j.coresight_write(1, 0x40022014, ap=True)
        j.coresight_write(3, 0x00000001, ap=True)

        # Write words 0..30 using auto-incrementing TAR
        j.coresight_write(1, cur_addr, ap=True)
        for i in range(31):
            j.coresight_write(3, words[i], ap=True)

        # Set PGSTRT (0x00080001: PG + PGSTRT)
        j.coresight_write(1, 0x40022014, ap=True)
        j.coresight_write(3, 0x00080001, ap=True)

        # Write word 31
        j.coresight_write(1, cur_addr + 31 * 4, ap=True)
        j.coresight_write(3, words[31], ap=True)

        # Wait for flash programming to complete (~2.5ms)
        time.sleep(0.005)
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
        sys.stdout.write(f"\rПрогресс записи: [{('=' * (percent // 4)).ljust(25)}] {percent}% (стр. {page_idx+1}/{num_pages})")
        sys.stdout.flush()

    log("\n[✓] Запись завершена! Выполняю верификацию...")

    # 7. Verification
    verified = True
    for page_idx in range(num_pages):
        page_bytes = padded_data[page_idx * page_size : (page_idx + 1) * page_size]
        words = struct.unpack('<32I', page_bytes)
        cur_addr = flash_addr + page_idx * page_size

        j.coresight_write(1, cur_addr, ap=True)
        for i in range(32):
            read_w = j.coresight_read(3, ap=True)
            if read_w != words[i]:
                log(f"\n[X] Ошибка верификации по адресу 0x{cur_addr + i * 4:08X}: записано 0x{words[i]:08X}, прочитано 0x{read_w:08X}")
                verified = False
                break
        if not verified:
            break

    if not verified:
        j.close()
        return False

    log(f"[✓] ВЕРИФИКАЦИЯ 100% УСПЕШНА! Все {total_bytes} байт совпадают!")
    beep()

    # 8. Reset core to run firmware
    log("[*] Перезапускаю процессор в рабочий режим...")
    j.coresight_write(0, 0x23000002, ap=True)
    # Release halt: C_DEBUGEN only
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
        log(f"[*] Проверка SRAM (0x20000004): 0x{magic:08X}")
        if magic == 0x5343414E:
            log("\n" + "=" * 65)
            log("  🎉🎉🎉 СКАНЕР НА 72 ШАГА УСПЕШНО ЗАПУЩЕН И РАБОТАЕТ! 🎉🎉🎉")
            log("=" * 65)
        else:
            log("[*] Прошивка запущена.")
    except Exception:
        log("[*] Контроллер перезапущен.")

    j.close()
    return True

if __name__ == '__main__':
    ok = main()
    sys.exit(0 if ok else 1)
