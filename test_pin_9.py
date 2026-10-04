# -*- coding: utf-8 -*-
import pylink
import time
import sys
import os

try:
    sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
except Exception:
    pass

try:
    import winsound
    def beep(f=1200, d=150): winsound.Beep(f, d)
except Exception:
    def beep(f=1200, d=150): pass

# All 10 Candidates for Нога 9 (Контакт 6 дисплея) in current scanner firmware:
CANDIDATES = [
    (5,  "PB4", "Порт B, Пин 4 (Нога 10/9 в QFN-16 - самый вероятный кандидат!)"),
    (14, "PB7", "Порт B, Пин 7"),
    (6,  "PA0", "Порт A, Пин 0"),
    (7,  "PA1", "Порт A, Пин 1"),
    (8,  "PA3", "Порт A, Пин 3"),
    (9,  "PA4", "Порт A, Пин 4"),
    (10, "PA5", "Порт A, Пин 5"),
    (11, "PA6", "Порт A, Пин 6"),
    (12, "PA7", "Порт A, Пин 7"),
    (13, "PC1", "Порт C, Пин 1"),
]

def main():
    print("=" * 70)
    print(" >>> ТЕСТ ПОИСКА GPIO ДЛЯ НОГИ 9 (КОНТАКТ 6: КАПЛЯ 💧 И ПОЛОСКА 1) <<<")
    print("=" * 70)

    j = pylink.JLink()
    try:
        j.open('774496021')
    except Exception:
        j.open()
    j.set_tif(pylink.enums.JLinkInterfaces.SWD)
    j.set_speed(1000)
    j.coresight_configure()
    j.coresight_write(0, 0x1E, ap=False)
    j.coresight_write(1, 0x50000000, ap=False)
    j.coresight_write(2, 0x00000000, ap=False)
    j.coresight_write(0, 0x23000002, ap=True)

    base = 0x2000000C

    def wm(a, v):
        j.coresight_write(1, a, ap=True)
        j.coresight_write(3, v, ap=True)

    def set_dc_pair(high, low):
        # Brief switch to mode 3 to guarantee state edge
        wm(base + 0x04, 3)
        time.sleep(0.02)
        wm(base + 0x38, high)
        wm(base + 0x3C, low)
        wm(base + 0x04, 1) # Mode 1: 100% DC bright hold

    def turn_off():
        wm(base + 0x04, 3)

    target_cand = sys.argv[1].upper() if len(sys.argv) > 1 else None

    for idx, name, desc in CANDIDATES:
        if target_cand and name != target_cand and str(idx) != target_cand:
            continue

        print("\n" + "#" * 65)
        print(f"[*] ПРОВЕРКА КАНДИДАТА:  {name}  (Индекс {idx})")
        print(f"    Описание: {desc}")
        print("#" * 65)
        beep(1400, 180)

        # 1. Тест Капли: Контакт 1(+) -> Контакт 6(-)  (PB0 -> Cand)
        print(f"  [1/2] Зажигаем КАПЛЮ 💧: PB0 (+)  --->  {name} (-)...")
        set_dc_pair(0, idx)
        time.sleep(1.8)

        # 2. Тест Полоски 1: Контакт 6(+) -> Контакт 5(-)  (Cand -> PB5)
        print(f"  [2/2] Зажигаем ПОЛОСКУ 1:  {name} (+)  --->  PB5 (-)...")
        set_dc_pair(idx, 4)
        time.sleep(1.8)

        turn_off()

        if target_cand is None:
            ans = input(f"Загорелась ли Капля или Полоска на [{name}]? [д(да)/Enter(след)]: ").strip().lower()
            if ans in ['y', 'yes', 'д', 'да']:
                print(f"\n[!!!] УРА! НОГА 9 ПОДТВЕРЖДЕНА КАК: {name}! [!!!]\n")
                beep(2000, 400)
                break

    turn_off()
    j.close()
    print("\n[+] Тест завершён.")

if __name__ == '__main__':
    main()
