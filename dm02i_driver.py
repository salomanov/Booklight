# -*- coding: utf-8 -*-
"""
DM02i Python Driver Library
Библиотека прямого управления дисплеем вейпа DM02i V03 по SWD (J-Link / PyLink).
Позволяет из любого Python скрипта управлять дисплеем в реальном времени.

Пример использования:
    from dm02i_driver import DM02i
    display = DM02i()
    display.set_number(100)
    display.set_liquid(3)
    display.set_drop(True)
    display.set_boost('static')
    display.update()
"""

import time
import pylink

SCANNER_ADDR = 0x2000000C

def p_pair(plus_contact, minus_contact):
    """Преобразует контакты 1..6 в 16-битный код для Charlieplexing"""
    return ((plus_contact - 1) << 8) | (minus_contact - 1)

SEGS = {
    # Капля (центр)
    'drop_center': p_pair(1, 6),

    # Обводка (ободок) капли (4 сегмента)
    'drop_top':    p_pair(2, 6),
    'drop_right':  p_pair(5, 6),
    'drop_bot':    p_pair(4, 6),
    'drop_left':   p_pair(3, 6),

    # Полоски жидкости
    'bar1':        p_pair(6, 5), # Нижняя
    'bar2':        p_pair(4, 5), # Средняя
    'bar3':        p_pair(3, 5), # Верхняя

    # Индикаторы
    'lightning':   p_pair(2, 5),
    'percent':     p_pair(6, 3),
    'hundred_top': p_pair(6, 4),
    'hundred_bot': p_pair(1, 5),

    # BOOST
    'boost_tl':    p_pair(1, 4),
    'boost_tr':    p_pair(2, 4),
    'boost_bl':    p_pair(3, 4),
    'boost_br':    p_pair(5, 4),

    # Цифра 1 (Десятки)
    'd1_a': p_pair(2, 1),
    'd1_b': p_pair(3, 1),
    'd1_c': p_pair(4, 1),
    'd1_d': p_pair(5, 1),
    'd1_e': p_pair(6, 1),
    'd1_f': p_pair(1, 2),
    'd1_g': p_pair(3, 2),

    # Цифра 2 (Единицы)
    'd2_a': p_pair(4, 2),
    'd2_b': p_pair(5, 2),
    'd2_c': p_pair(6, 2),
    'd2_d': p_pair(1, 3),
    'd2_e': p_pair(2, 3),
    'd2_f': p_pair(4, 3),
    'd2_g': p_pair(5, 3),
}

FONT_7SEG = {
    0: ['a', 'b', 'c', 'd', 'e', 'f'],
    1: ['b', 'c'],
    2: ['a', 'b', 'g', 'e', 'd'],
    3: ['a', 'b', 'g', 'c', 'd'],
    4: ['f', 'g', 'b', 'c'],
    5: ['a', 'f', 'g', 'c', 'd'],
    6: ['a', 'f', 'e', 'd', 'c', 'g'],
    7: ['a', 'b', 'c'],
    8: ['a', 'b', 'c', 'd', 'e', 'f', 'g'],
    9: ['a', 'b', 'c', 'd', 'f', 'g'],
}

class DM02i:
    def __init__(self, serial_number='774496021', speed_khz=1000):
        self.j = pylink.JLink()
        try:
            self.j.open(serial_number)
        except Exception:
            self.j.open()

        self.j.set_tif(pylink.enums.JLinkInterfaces.SWD)
        self.j.set_speed(speed_khz)
        self.j.coresight_configure()
        self.j.coresight_write(0, 0x1E, ap=False)
        self.j.coresight_write(1, 0x50000000, ap=False)
        self.j.coresight_write(2, 0x00000000, ap=False)
        self.j.coresight_write(0, 0x23000002, ap=True)

        # Детект базового адреса
        self.base = SCANNER_ADDR
        for cand in [0x2000000C, 0x20000000, 0x20000004, 0x20000008]:
            self.j.coresight_write(1, cand, ap=True)
            self.j.coresight_read(3, ap=True)
            if self.j.coresight_read(3, ap=True) == 0x5343414E:
                self.base = cand
                break

        # Внутреннее состояние дисплея
        self.number = -1
        self.show_percent = False
        self.liquid_level = 0
        self.drop_on = False
        self.rim_mode = 'off' # 'off', 'static', 'spin'
        self.rim_frame = 0
        self.lightning_on = False
        self.boost_mode = 'off' # 'off', 'static', 'spin'
        self.boost_frame = 0

    def set_number(self, val):
        """Установка числа 0..100. Если None или < 0 - цифры гаснут"""
        self.number = val
        return self

    def set_percent(self, enable=True):
        """Включение знака %"""
        self.show_percent = enable
        return self

    def set_liquid(self, level):
        """Деления жидкости (0..3)"""
        self.liquid_level = max(0, min(3, level))
        return self

    def set_drop(self, on=True):
        """Центральная капля 💧"""
        self.drop_on = on
        return self

    def set_rim(self, mode='static'):
        """Обводка капли: 'off', 'static', 'spin'"""
        self.rim_mode = mode
        return self

    def set_lightning(self, on=True):
        """Молния ⚡"""
        self.lightning_on = on
        return self

    def set_boost(self, mode='static'):
        """Индикатор BOOST 🚀: 'off', 'static', 'spin'"""
        self.boost_mode = mode
        return self

    def all_on(self):
        """Зажечь все 30 сегментов"""
        self.set_number(100)
        self.set_percent(True)
        self.set_liquid(3)
        self.set_drop(True)
        self.set_rim('static')
        self.set_lightning(True)
        self.set_boost('static')
        return self.update()

    def all_off(self):
        """Погасить экран полностью в 0"""
        self.number = -1
        self.show_percent = False
        self.liquid_level = 0
        self.drop_on = False
        self.rim_mode = 'off'
        self.lightning_on = False
        self.boost_mode = 'off'
        return self.update()

    def update(self):
        """Передача текущей конфигурации сегментов на микроконтроллер"""
        pairs = []

        # 1. Число и %
        if self.number is not None and self.number >= 0:
            if self.show_percent:
                pairs.append(SEGS['percent'])

            val = self.number
            if val >= 100:
                pairs.append(SEGS['hundred_top'])
                pairs.append(SEGS['hundred_bot'])
                d1_segs = FONT_7SEG[0]
                d2_segs = FONT_7SEG[0]
            else:
                d1 = val // 10
                d2 = val % 10
                d1_segs = FONT_7SEG[d1] if val >= 10 else []
                d2_segs = FONT_7SEG[d2]

            for s in d1_segs: pairs.append(SEGS[f'd1_{s}'])
            for s in d2_segs: pairs.append(SEGS[f'd2_{s}'])

        # 2. Полоски жидкости
        if self.liquid_level >= 1: pairs.append(SEGS['bar1'])
        if self.liquid_level >= 2: pairs.append(SEGS['bar2'])
        if self.liquid_level >= 3: pairs.append(SEGS['bar3'])

        # 3. Капля
        if self.drop_on:
            pairs.append(SEGS['drop_center'])

        # 4. Обводка капли
        rim_quads = [SEGS['drop_top'], SEGS['drop_right'], SEGS['drop_bot'], SEGS['drop_left']]
        if self.rim_mode == 'static':
            pairs.extend(rim_quads)
        elif self.rim_mode == 'spin':
            pairs.append(rim_quads[self.rim_frame % 4])
            self.rim_frame = (self.rim_frame + 1) % 4

        # 5. Молния
        if self.lightning_on:
            pairs.append(SEGS['lightning'])

        # 6. BOOST
        boost_quads = [SEGS['boost_tl'], SEGS['boost_tr'], SEGS['boost_br'], SEGS['boost_bl']]
        if self.boost_mode == 'static':
            pairs.extend(boost_quads)
        elif self.boost_mode == 'spin':
            pairs.append(boost_quads[self.boost_frame % 4])
            self.boost_frame = (self.boost_frame + 1) % 4

        # Запись в микроконтроллер
        count = len(pairs)
        if count > 32: count = 32

        self.j.coresight_write(1, self.base + 0x44, ap=True)
        self.j.coresight_write(3, count, ap=True)

        for i in range(count):
            self.j.coresight_write(1, self.base + 0x48 + (i * 4), ap=True)
            self.j.coresight_write(3, pairs[i], ap=True)

        self.j.coresight_write(1, self.base + 0x04, ap=True)
        self.j.coresight_write(3, 4 if count > 0 else 3, ap=True)
        return self

    def get_battery_mv(self):
        """Чтение напряжения батареи/питания в милливольтах из телеметрии чипа"""
        self.j.coresight_write(1, self.base + 0x28, ap=True)
        self.j.coresight_read(3, ap=True)
        return self.j.coresight_read(3, ap=True)

    def close(self):
        self.j.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

if __name__ == '__main__':
    print("Тестирование библиотеки DM02i...")
    with DM02i() as d:
        print("Напряжение АКБ:", d.get_battery_mv(), "мВ")
        print("Включаем 75%, 2 полоски жидкости, каплю и ободок...")
        d.set_number(75).set_percent(True).set_liquid(2).set_drop(True).set_rim('static').set_lightning(True).update()
        time.sleep(2)
        print("Готово!")
