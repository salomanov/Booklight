import sys
import time
import os
import pylink

try:
    import winsound
    def beep():
        winsound.Beep(1500, 300)
except Exception:
    def beep():
        print('\a', end='', flush=True)

def main():
    print("=" * 65)
    print("      >>> АППАРАТНЫЙ СТИРАТЕЛЬ ЧИПА PUYA PY32 (2000 Гц) <<<")
    print("=" * 65)
    print("Этот скрипт перехватывает ядро за 0.5 мс и полностью очищает Flash.")
    print("-" * 65)

    j = pylink.JLink()
    try:
        j.open('774496021')
        j.set_tif(pylink.enums.JLinkInterfaces.SWD)
        j.set_speed(1000)
    except Exception as e:
        print(f"[X] Ошибка открытия J-Link: {e}")
        input("Нажмите Enter для выхода...")
        return

    print("[*] J-Link программатор готов к перехвату!")
    print("\n" + "=" * 65)
    print("  >>> ЛОВУШКА УЖЕ АКТИВНА! (2000 проверок в секунду) <<<")
    print("  ПРЯМО СЕЙЧАС:")
    print("  1. Выдерните провод 3.3V (или выдерните USB программатора)")
    print("  2. Через 3 секунды воткните обратно!")
    print("  (Или просто коснитесь пина 'R' (NRST) на землю 'G' пинцетом)")
    print("=" * 65 + "\n")

    start_time = time.time()
    attempts = 0
    erased = False
    last_status = time.time()

    while time.time() - start_time < 90:
        attempts += 1
        now = time.time()
        if now - last_status >= 2.0:
            last_status = now
            print(f"[*] Ловушка слушает... (проверено попыток: {attempts})")
        try:
            j.coresight_configure()
            dpidr = j.coresight_read(0, ap=False)
            if dpidr in (0x0BC11477, 0x0BB11477, 0x2BA01477):
                # 1. DP Power-up
                j.coresight_write(1, 0x50000000, ap=False)
                j.coresight_write(0, 0x1E, ap=False)

                # 2. Halt Core in Reset Vector
                j.coresight_write(2, 0x00000000, ap=False)
                j.coresight_write(0, 0x23000002, ap=True)
                j.coresight_write(1, 0xE000EDF0, ap=True)
                j.coresight_write(3, 0xA05F0003, ap=True)

                print(f"\n[🔥] ЧИП ПОЙМАН! Попытка #{attempts} (DPIDR: 0x{dpidr:08X})")
                print("[*] Ядро остановлено. Выполняю Mass Erase Flash памяти...")

                # 3. Enable FLASH clock (RCC->AHBENR = 0x40021014)
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
                print(f"[*] Чтение 0x08000000: 0x{flash_word:08X}")

                if flash_word == 0xFFFFFFFF:
                    beep()
                    print("\n" + "=" * 65)
                    print("  🎉 ЧИП УСПЕШНО СТЁРТ! FLASH ПАМЯТЬ ЧИСТАЯ (0xFFFFFFFF) 🎉")
                    print("  Заводской спящий режим и весь предыдущий код удалены.")
                    print("  Шина SWD теперь разблокирована и свободна!")
                    print("=" * 65)
                    erased = True
                    break
                else:
                    print("[!] Внимание: Flash не вернула 0xFFFFFFFF, повторяю...")
        except Exception:
            pass

    j.close()

    if not erased:
        print("\n[X] Время ожидания истекло. Чип не обнаружен на шине.")
    
    print("\nНажмите любую клавишу для завершения...")
    try:
        import msvcrt
        msvcrt.getch()
    except Exception:
        pass

if __name__ == '__main__':
    main()
