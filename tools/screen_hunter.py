import sys
import time
import os
import msvcrt
from pyocd.core.helpers import ConnectHelper
from pyocd.core.session import Session

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

PIN_NAMES = [
    "PA0", # 0
    "PA1", # 1
    "PA3", # 2
    "PA4", # 3
    "PA5", # 4
    "PA6", # 5
    "PA7", # 6
    "PB0", # 7
    "PB1", # 8
    "PB2", # 9
    "PB3", # 10
    "PB4", # 11
    "PB5", # 12
]

SCANNER_ADDR = 0x20000004
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "screen_map.txt")

def main():
    print("=" * 65)
    print("   >>> ИНТЕРАКТИВНЫЙ ПИН-ХАНТЕР ДИСПЛЕЯ DM02i V03 <<<")
    print("=" * 65)

    try:
        session = ConnectHelper.session_with_chosen_probe(
            target_override='py32f002bx5',
            connect_mode='attach',
            options={'auto_unlock': False, 'frequency': 1000000}
        )
        session.open()
        target = session.target
    except Exception as e:
        print(f"[X] Ошибка подключения к плате: {e}")
        sys.exit(1)

    magic = target.read32(SCANNER_ADDR)
    if magic != 0x5343414E:
        print(f"[!] Внимание: Сигнатура 'SCAN' не найдена (прочитано: 0x{magic:08X})")
        print("    Убедитесь, что прошивка scanner.bin запущена.")

    print("[*] Подключение к сканеру успешно!")
    print("\nУПРАВЛЕНИЕ С КЛАВИАТУРЫ:")
    print("  [ПРОБЕЛ]  - Пауза / Возобновить сканирование")
    print("  [N]       - Следующий шаг (Next)")
    print("  [P]       - Предыдущий шаг (Previous)")
    print("  [+] / [-] - Увеличить / уменьшить задержку")
    print("  [S]       - Записать, что зажглось на экране (в screen_map.txt)")
    print("  [1]       - Режим Charlieplexing (пары High/Low)")
    print("  [2]       - Режим Single Pin High (1 пин High, остальные Z)")
    print("  [Q]       - Выход")
    print("-" * 65)

    last_step = -1
    last_print = 0

    try:
        while True:
            # Check keyboard input
            if msvcrt.kbhit():
                ch = msvcrt.getch().decode('utf-8', errors='ignore').lower()
                if ch == ' ':
                    paused = target.read32(SCANNER_ADDR + 0x1C)
                    target.write32(SCANNER_ADDR + 0x1C, 0 if paused else 1)
                    print(f"\n>>> {'[ПАУЗА]' if not paused else '[ВОЗОБНОВЛЕНО]'} <<<")
                elif ch == 'n':
                    target.write32(SCANNER_ADDR + 0x30, 1) # cmd_next
                elif ch == 'p':
                    target.write32(SCANNER_ADDR + 0x34, 1) # cmd_prev
                elif ch == '+':
                    delay = target.read32(SCANNER_ADDR + 0x18)
                    delay = min(5000, delay + 500)
                    target.write32(SCANNER_ADDR + 0x18, delay)
                    print(f"\nЗадержка: {delay} мс")
                elif ch == '-':
                    delay = target.read32(SCANNER_ADDR + 0x18)
                    delay = max(300, delay - 300)
                    target.write32(SCANNER_ADDR + 0x18, delay)
                    print(f"\nЗадержка: {delay} мс")
                elif ch == '1':
                    target.write32(SCANNER_ADDR + 0x04, 0) # Mode 0: Charlie
                    print("\n>>> Режим: Charlieplexing (пары High/Low)")
                elif ch == '2':
                    target.write32(SCANNER_ADDR + 0x04, 2) # Mode 2: Single High
                    print("\n>>> Режим: Single Pin High")
                elif ch == 's':
                    # Pause automatically while noting
                    target.write32(SCANNER_ADDR + 0x1C, 1)
                    h_idx = target.read32(SCANNER_ADDR + 0x10)
                    l_idx = target.read32(SCANNER_ADDR + 0x14)
                    h_name = PIN_NAMES[h_idx] if h_idx < len(PIN_NAMES) else f"P{h_idx}"
                    l_name = PIN_NAMES[l_idx] if l_idx < len(PIN_NAMES) else f"P{l_idx}"
                    cur_s = target.read32(SCANNER_ADDR + 0x08)
                    print(f"\n[ЗАПИСЬ ДЛЯ ШАГА #{cur_s}: HIGH={h_name} (+), LOW={l_name} (-)]")
                    desc = input("Что сейчас светится на экране? > ").strip()
                    if desc:
                        line = f"Шаг {cur_s:3d} | HIGH: {h_name:4s} (+) -> LOW: {l_name:4s} (-) | Сегмент: {desc}\n"
                        with open(LOG_FILE, "a", encoding="utf-8") as f:
                            f.write(line)
                        print(f"[+] Записано в {LOG_FILE}: {line.strip()}")
                    target.write32(SCANNER_ADDR + 0x1C, 0) # Unpause
                elif ch == 'q':
                    break

            # Poll telemetry
            now = time.time()
            if now - last_print >= 0.2:
                last_print = now
                step = target.read32(SCANNER_ADDR + 0x08)
                total = target.read32(SCANNER_ADDR + 0x0C)
                h_idx = target.read32(SCANNER_ADDR + 0x10)
                l_idx = target.read32(SCANNER_ADDR + 0x14)
                delay = target.read32(SCANNER_ADDR + 0x18)
                paused = target.read32(SCANNER_ADDR + 0x1C)
                vdd = target.read32(SCANNER_ADDR + 0x28)
                idr_a = target.read32(SCANNER_ADDR + 0x20)
                idr_b = target.read32(SCANNER_ADDR + 0x24)

                h_name = PIN_NAMES[h_idx] if h_idx < len(PIN_NAMES) else f"P{h_idx}"
                l_name = PIN_NAMES[l_idx] if l_idx < len(PIN_NAMES) else f"P{l_idx}"

                status_str = "PAUSED" if paused else "SCANNING"
                sys.stdout.write(
                    f"\r[{status_str:8s}] Шаг {step:3d}/{total} | "
                    f"HIGH: {h_name:4s} (+3.3V) ---> LOW: {l_name:4s} (GND) | "
                    f"АКБ: {vdd/1000.0:.2f}В | "
                    f"Задержка: {delay}мс  "
                )
                sys.stdout.flush()

            time.sleep(0.05)

    except KeyboardInterrupt:
        pass
    finally:
        session.close()
        print("\n\nСессия завершена.")

if __name__ == '__main__':
    main()
