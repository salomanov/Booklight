# -*- coding: utf-8 -*-
"""
DM02i Smart Display Controller & Learning Lab
Полноценный интерактивный контроллер дисплея вейпа DM02i V03 (2428).
MCU: Puya PY32C642 / PY32F002BW15 (Cortex-M0+ @ 24MHz)
"""

import sys
import os
import time
import queue
import pylink

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QSlider, QRadioButton, 
    QButtonGroup, QFrame, QGroupBox, QSpinBox, QCheckBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor

# Базовый адрес в ОЗУ (автодетект)
SCANNER_ADDR = 0x2000000C

# Контакты 1..6 соответствуют индексам 0..5 в новой прошивке:
# 0: PB0 (Контакт 1 / Нога 14)
# 1: PB1 (Контакт 2 / Нога 13)
# 2: PB2 (Контакт 3 / Нога 12)
# 3: PB3 (Контакт 4 / Нога 11)
# 4: PB5 (Контакт 5 / Нога 10)
# 5: PC1 (Контакт 6 / Нога 9)

def p_pair(plus_contact, minus_contact):
    """Преобразует номера контактов 1..6 в 16-битное число для прошивки: (high << 8) | low"""
    return ((plus_contact - 1) << 8) | (minus_contact - 1)

# Полная база всех пар сегментов:
SEGS = {
    # Капля (5 сегментов, общий катод на Контакте 6)
    'drop_center': p_pair(1, 6),
    'drop_top':    p_pair(2, 6),
    'drop_right':  p_pair(5, 6),
    'drop_bot':    p_pair(4, 6),
    'drop_left':   p_pair(3, 6),

    # Индикаторы
    'bar1':        p_pair(6, 5), # Нижняя полоска
    'bar2':        p_pair(4, 5), # Средняя полоска
    'bar3':        p_pair(3, 5), # Верхняя полоска
    'lightning':   p_pair(2, 5), # Молния
    'percent':     p_pair(6, 3), # Знак процента %
    'hundred_top': p_pair(6, 4), # Верхняя палочка 100
    'hundred_bot': p_pair(1, 5), # Нижняя палочка 100

    # BOOST (4 сегмента)
    'boost_tl':    p_pair(1, 4), # Буква B
    'boost_tr':    p_pair(2, 4), # Буква T
    'boost_bl':    p_pair(3, 4), # Диод 2
    'boost_br':    p_pair(5, 4), # Диод 4

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

class SwdWorker(QThread):
    connection_status = pyqtSignal(bool, str)
    telemetry_signal  = pyqtSignal(int, int) # vdd_mv, heartbeat

    def __init__(self):
        super().__init__()
        self.running = True
        self.cmd_queue = queue.Queue()

    def set_pairs(self, pairs_list):
        while not self.cmd_queue.empty():
            try:
                self.cmd_queue.get_nowait()
            except Exception:
                break
        self.cmd_queue.put(pairs_list)

    def stop(self):
        self.running = False
        self.wait(1000)

    def run(self):
        j = None
        base = SCANNER_ADDR
        fail_count = 0
        last_sent_pairs = None

        while self.running:
            if j is None:
                try:
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

                    for cand in [0x2000000C, 0x20000000, 0x20000004, 0x20000008]:
                        j.coresight_write(1, cand, ap=True)
                        j.coresight_read(3, ap=True)
                        if j.coresight_read(3, ap=True) == 0x5343414E:
                            base = cand
                            break

                    fail_count = 0
                    self.connection_status.emit(True, f"J-Link SN: {j.serial_number} | ОЗУ: 0x{base:08X}")
                except Exception as e:
                    if j:
                        try: j.close()
                        except Exception: pass
                        j = None
                    self.connection_status.emit(False, f"Ожидание J-Link ({e})")
                    self.msleep(1000)
                    continue

            try:
                target_pairs = None
                while not self.cmd_queue.empty():
                    target_pairs = self.cmd_queue.get_nowait()

                if target_pairs is not None and target_pairs != last_sent_pairs:
                    last_sent_pairs = target_pairs
                    count = len(target_pairs)
                    if count > 32: count = 32

                    # Запись пар в ОЗУ
                    j.coresight_write(1, base + 0x44, ap=True)
                    j.coresight_write(3, count, ap=True)

                    for i in range(count):
                        j.coresight_write(1, base + 0x48 + (i * 4), ap=True)
                        j.coresight_write(3, target_pairs[i], ap=True)

                    # Режим 4: Мультиплексинг (или 3 = All Off если count == 0)
                    j.coresight_write(1, base + 0x04, ap=True)
                    j.coresight_write(3, 4 if count > 0 else 3, ap=True)

                # Периодическое чтение телеметрии
                j.coresight_write(1, base + 0x28, ap=True) # vdd_mv
                j.coresight_read(3, ap=True)
                vdd = j.coresight_read(3, ap=True)
                j.coresight_write(1, base + 0x40, ap=True) # heartbeat
                j.coresight_read(3, ap=True)
                hb = j.coresight_read(3, ap=True)
                self.telemetry_signal.emit(vdd, hb)

                self.msleep(50)
                fail_count = 0
            except Exception as e:
                fail_count += 1
                if fail_count > 3:
                    if j:
                        try: j.close()
                        except Exception: pass
                        j = None
                    self.connection_status.emit(False, f"Связь прервана: {e}")
                    self.msleep(1000)
                else:
                    self.msleep(80)

        if j:
            try: j.close()
            except Exception: pass


class DM02iController(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DM02i Display Controller - Обучающая панель экрана вейпа")
        self.resize(1120, 820)

        # Состояния элементов
        self.percent_val = 100
        self.percent_show = True
        self.liquid_bars = 3
        
        # Капля: раздельные независимые элементы (Центр и Обводка)
        self.drop_center_on = True
        self.drop_rim_mode = 1 # 0=выкл, 1=горит статично, 2=вращение
        self.drop_anim_frame = 0

        # Режимы молнии: 0=выкл, 1=вкл, 2=моргание
        self.lightning_mode = 1
        self.lightning_state = True

        # Режимы BOOST: 0=выкл, 1=вкл (все 4), 2=моргание, 3=турбо вращение
        self.boost_mode = 1
        self.boost_anim_frame = 0
        self.boost_blink_state = True

        # Режим автодемо счетчика
        self.demo_counter = False

        self.init_ui()

        # Таймер анимаций (100 мс = 10 кадров/сек)
        self.anim_timer = QTimer(self)
        self.anim_timer.timeout.connect(self.on_anim_tick)
        self.anim_timer.start(100)

        # SWD Worker
        self.worker = SwdWorker()
        self.worker.connection_status.connect(self.on_conn_status)
        self.worker.telemetry_signal.connect(self.on_telemetry)
        self.worker.start()

        # Первичное обновление
        self.update_display()

    def closeEvent(self, event):
        self.worker.stop()
        super().closeEvent(event)

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        # --- ХЕДЕР И СТАТУС ---
        header = QFrame()
        header.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f172a, stop:1 #1e1b4b);
            border: 2px solid #6366f1; border-radius: 12px; padding: 12px;
        """)
        h_box = QHBoxLayout(header)
        h_box.setContentsMargins(10, 5, 10, 5)

        title_box = QVBoxLayout()
        h_title = QLabel("DM02i V03 — УМНЫЙ КОНТРОЛЛЕР ДИСПЛЕЯ")
        h_title.setStyleSheet("color: #a5b4fc; font-size: 18px; font-weight: bold; letter-spacing: 1px;")
        h_sub = QLabel("Раздельное управление каплей, обводкой, индикаторами и ползунком процентов")
        h_sub.setStyleSheet("color: #94a3b8; font-size: 12px;")
        title_box.addWidget(h_title)
        title_box.addWidget(h_sub)
        h_box.addLayout(title_box)

        h_box.addStretch()

        self.lbl_status = QLabel("Подключение к J-Link...")
        self.lbl_status.setStyleSheet("color: #fbbf24; font-size: 13px; font-weight: bold;")
        h_box.addWidget(self.lbl_status)

        layout.addWidget(header)

        # --- СРЕДНЯЯ ЧАСТЬ: ВИРТУАЛЬНЫЙ ЭКРАН И ПАНЕЛИ УПРАВЛЕНИЯ ---
        main_h = QHBoxLayout()
        main_h.setSpacing(16)

        # 1. Левая колонка: Виртуальный дисплей вейпа
        left_box = QVBoxLayout()
        left_box.setSpacing(10)

        lbl_screen_title = QLabel("ВИРТУАЛЬНЫЙ ЭКРАН ВЕЙПА (LIVE PREVIEW)")
        lbl_screen_title.setStyleSheet("color: #cbd5e1; font-weight: bold; font-size: 13px;")
        left_box.addWidget(lbl_screen_title)

        # Рамка экрана
        self.screen_frame = QFrame()
        self.screen_frame.setFixedSize(380, 560)
        self.screen_frame.setStyleSheet("""
            background: #020617;
            border: 4px solid #334155;
            border-radius: 28px;
        """)
        s_layout = QVBoxLayout(self.screen_frame)
        s_layout.setContentsMargins(20, 25, 20, 25)
        s_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Верхний блок: Капля (Центр + Обводка) и Полоски жидкости
        top_screen = QHBoxLayout()
        top_screen.setSpacing(15)

        # Капля (Визуализация)
        drop_v_box = QVBoxLayout()
        drop_v_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_v_drop_rim = QLabel("◯")
        self.lbl_v_drop_rim.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_v_drop_rim.setStyleSheet("font-size: 60px; color: #38bdf8; font-weight: bold;")
        self.lbl_v_drop_info = QLabel("Капля: Центр + Ободок")
        self.lbl_v_drop_info.setStyleSheet("color: #94a3b8; font-size: 11px;")
        drop_v_box.addWidget(self.lbl_v_drop_rim)
        drop_v_box.addWidget(self.lbl_v_drop_info)
        top_screen.addLayout(drop_v_box)

        # Полоски жидкости
        bars_box = QVBoxLayout()
        bars_box.setSpacing(6)
        bars_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_v_bar3 = QLabel("━━━ Полоска 3")
        self.lbl_v_bar2 = QLabel("━━━ Полоска 2")
        self.lbl_v_bar1 = QLabel("━━━ Полоска 1")
        for b in [self.lbl_v_bar3, self.lbl_v_bar2, self.lbl_v_bar1]:
            b.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 14px;")
            bars_box.addWidget(b)
        top_screen.addLayout(bars_box)
        s_layout.addLayout(top_screen)

        s_layout.addSpacing(15)

        # Средний блок: Число процентов и значок %
        num_box = QHBoxLayout()
        num_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_v_hundred = QLabel("1")
        self.lbl_v_hundred.setStyleSheet("color: #f8fafc; font-size: 80px; font-weight: 900; font-family: monospace;")
        self.lbl_v_digits = QLabel("00")
        self.lbl_v_digits.setStyleSheet("color: #f8fafc; font-size: 80px; font-weight: 900; font-family: monospace;")
        self.lbl_v_percent = QLabel("%")
        self.lbl_v_percent.setStyleSheet("color: #f8fafc; font-size: 40px; font-weight: bold; margin-bottom: 20px;")

        num_box.addWidget(self.lbl_v_hundred)
        num_box.addWidget(self.lbl_v_digits)
        num_box.addWidget(self.lbl_v_percent)
        s_layout.addLayout(num_box)

        # Молния
        self.lbl_v_lightning = QLabel("⚡ ЗАРАДКА")
        self.lbl_v_lightning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_v_lightning.setStyleSheet("color: #facc15; font-size: 20px; font-weight: bold;")
        s_layout.addWidget(self.lbl_v_lightning)

        s_layout.addSpacing(15)

        # Нижний блок: BOOST
        self.lbl_v_boost = QLabel("🚀 B O O S T 🚀")
        self.lbl_v_boost.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_v_boost.setStyleSheet("""
            background: #450a0a; color: #ef4444; border: 2px solid #ef4444; 
            border-radius: 8px; font-size: 18px; font-weight: bold; padding: 6px;
        """)
        s_layout.addWidget(self.lbl_v_boost)

        left_box.addWidget(self.screen_frame)
        main_h.addLayout(left_box)

        # 2. Правая колонка: Органы управления
        right_box = QVBoxLayout()
        right_box.setSpacing(12)

        # ГРУППА 1: Проценты (0..100)
        grp_percent = QGroupBox("🔢 Управление процентами и дисплеем (0 .. 100%)")
        grp_percent.setStyleSheet("QGroupBox { font-weight: bold; color: #a5b4fc; border: 1px solid #475569; border-radius: 8px; margin-top: 6px; padding-top: 10px; }")
        p_layout = QVBoxLayout(grp_percent)

        # Чекбокс включения дисплея цифр (чтобы при выключении не оставалось 0%)
        self.chk_percent_show = QCheckBox("Включить отображение цифр и знака %")
        self.chk_percent_show.setChecked(True)
        self.chk_percent_show.setStyleSheet("font-size: 13px; font-weight: bold; color: #cbd5e1;")
        self.chk_percent_show.toggled.connect(self.on_percent_show_toggled)
        p_layout.addWidget(self.chk_percent_show)

        p_row = QHBoxLayout()
        self.slider_pct = QSlider(Qt.Orientation.Horizontal)
        self.slider_pct.setRange(0, 100)
        self.slider_pct.setValue(100)
        self.slider_pct.valueChanged.connect(self.on_slider_pct_changed)
        
        self.spin_pct = QSpinBox()
        self.spin_pct.setRange(0, 100)
        self.spin_pct.setValue(100)
        self.spin_pct.setStyleSheet("font-size: 16px; font-weight: bold; width: 60px;")
        self.spin_pct.valueChanged.connect(self.slider_pct.setValue)
        self.slider_pct.valueChanged.connect(self.spin_pct.setValue)

        p_row.addWidget(self.slider_pct)
        p_row.addWidget(self.spin_pct)
        p_layout.addLayout(p_row)

        btn_p_box = QHBoxLayout()
        for v in [0, 25, 50, 75, 99, 100]:
            btn = QPushButton(f"{v}%")
            btn.setStyleSheet("padding: 4px 8px; font-size: 11px;")
            btn.clicked.connect(lambda _, val=v: self.set_percent_and_enable(val))
            btn_p_box.addWidget(btn)

        self.btn_demo_pct = QPushButton("🔄 Автосчётчик")
        self.btn_demo_pct.setCheckable(True)
        self.btn_demo_pct.clicked.connect(self.toggle_demo_pct)
        btn_p_box.addWidget(self.btn_demo_pct)
        p_layout.addLayout(btn_p_box)

        right_box.addWidget(grp_percent)

        # ГРУППА 2: Деления жидкости и РАЗДЕЛЬНАЯ КАПЛЯ
        grp_liquid = QGroupBox("💧 Жидкость: Полоски (0..3) и Раздельная Капля")
        grp_liquid.setStyleSheet("QGroupBox { font-weight: bold; color: #38bdf8; border: 1px solid #475569; border-radius: 8px; margin-top: 6px; padding-top: 10px; }")
        l_layout = QVBoxLayout(grp_liquid)

        # Полоски
        bar_row = QHBoxLayout()
        bar_row.addWidget(QLabel("Деления жидкости (0..3):"))
        self.slider_bars = QSlider(Qt.Orientation.Horizontal)
        self.slider_bars.setRange(0, 3)
        self.slider_bars.setValue(3)
        self.slider_bars.valueChanged.connect(self.on_slider_bars_changed)
        self.lbl_bars_txt = QLabel("3 полоски")
        self.lbl_bars_txt.setStyleSheet("font-weight: bold; width: 80px;")
        bar_row.addWidget(self.slider_bars)
        bar_row.addWidget(self.lbl_bars_txt)
        l_layout.addLayout(bar_row)

        # РАЗДЕЛЬНОЕ УПРАВЛЕНИЕ КАПЛЕЙ:
        drop_sep_frame = QFrame()
        drop_sep_frame.setStyleSheet("background: #0f172a; border-radius: 6px; padding: 6px;")
        ds_layout = QVBoxLayout(drop_sep_frame)

        # 1. Чекбокс центральной капли
        self.chk_drop_center = QCheckBox("💧 Центральная капля (точечный центр)")
        self.chk_drop_center.setChecked(True)
        self.chk_drop_center.setStyleSheet("font-size: 13px; font-weight: bold; color: #38bdf8;")
        self.chk_drop_center.toggled.connect(self.on_drop_center_toggled)
        ds_layout.addWidget(self.chk_drop_center)

        # 2. Обводка (ободок) капли: переключатель
        rim_row = QHBoxLayout()
        rim_row.addWidget(QLabel("Ободок капли:"))
        self.bg_drop_rim = QButtonGroup(self)
        r_rim_off  = QRadioButton("Выкл")
        r_rim_on   = QRadioButton("Горит статично (все 4)")
        r_rim_spin = QRadioButton("🌀 Бегущий огонёк по кругу")
        
        self.bg_drop_rim.addButton(r_rim_off, 0)
        self.bg_drop_rim.addButton(r_rim_on, 1)
        self.bg_drop_rim.addButton(r_rim_spin, 2)
        r_rim_on.setChecked(True)
        self.bg_drop_rim.idToggled.connect(self.on_drop_rim_mode_changed)

        for r in [r_rim_off, r_rim_on, r_rim_spin]:
            rim_row.addWidget(r)
        ds_layout.addLayout(rim_row)

        l_layout.addWidget(drop_sep_frame)
        right_box.addWidget(grp_liquid)

        # ГРУППА 3: Молния ⚡ и Индикатор BOOST 🚀
        grp_extra = QGroupBox("⚡ Молния (Зарядка) и 🚀 BOOST")
        grp_extra.setStyleSheet("QGroupBox { font-weight: bold; color: #facc15; border: 1px solid #475569; border-radius: 8px; margin-top: 6px; padding-top: 10px; }")
        e_layout = QVBoxLayout(grp_extra)

        # Молния
        ln_row = QHBoxLayout()
        ln_row.addWidget(QLabel("Молния ⚡:"))
        self.bg_ln = QButtonGroup(self)
        r_ln_off   = QRadioButton("Выкл")
        r_ln_on    = QRadioButton("Горит")
        r_ln_blink = QRadioButton("⚡ Моргание (1 Гц)")
        self.bg_ln.addButton(r_ln_off, 0)
        self.bg_ln.addButton(r_ln_on, 1)
        self.bg_ln.addButton(r_ln_blink, 2)
        r_ln_on.setChecked(True)
        self.bg_ln.idToggled.connect(self.on_lightning_mode_changed)

        for r in [r_ln_off, r_ln_on, r_ln_blink]:
            ln_row.addWidget(r)
        e_layout.addLayout(ln_row)

        # BOOST
        b_row = QHBoxLayout()
        b_row.addWidget(QLabel("BOOST 🚀:"))
        self.bg_boost = QButtonGroup(self)
        r_b_off   = QRadioButton("Выкл")
        r_b_on    = QRadioButton("Горит")
        r_b_blink = QRadioButton("Моргание")
        r_b_spin  = QRadioButton("🚀 Турбо-раскрутка")
        self.bg_boost.addButton(r_b_off, 0)
        self.bg_boost.addButton(r_b_on, 1)
        self.bg_boost.addButton(r_b_blink, 2)
        self.bg_boost.addButton(r_b_spin, 3)
        r_b_on.setChecked(True)
        self.bg_boost.idToggled.connect(self.on_boost_mode_changed)

        for r in [r_b_off, r_b_on, r_b_blink, r_b_spin]:
            b_row.addWidget(r)
        e_layout.addLayout(b_row)

        right_box.addWidget(grp_extra)

        # ГРУППА 4: Готовые сценарии вейпа в 1 клик
        grp_scen = QGroupBox("🎬 Готовые сценарии вейпа (В 1 клик)")
        grp_scen.setStyleSheet("QGroupBox { font-weight: bold; color: #10b981; border: 1px solid #475569; border-radius: 8px; margin-top: 6px; padding-top: 10px; }")
        scen_layout = QHBoxLayout(grp_scen)

        btn_puff = QPushButton("💨 Имитация затяжки (Puff)")
        btn_puff.setStyleSheet("background: #0f766e; font-weight: bold; padding: 8px;")
        btn_puff.clicked.connect(self.scen_puff)

        btn_chrg = QPushButton("🔌 Режим зарядки (Charging)")
        btn_chrg.setStyleSheet("background: #b45309; font-weight: bold; padding: 8px;")
        btn_chrg.clicked.connect(self.scen_charging)

        btn_all_on = QPushButton("💡 Зажечь ВСЁ (30 шт)")
        btn_all_on.setStyleSheet("background: #4338ca; font-weight: bold; padding: 8px;")
        btn_all_on.clicked.connect(self.scen_all_on)

        btn_all_off = QPushButton("🌑 Полностью погасить экран (0)")
        btn_all_off.setStyleSheet("background: #334155; font-weight: bold; padding: 8px;")
        btn_all_off.clicked.connect(self.scen_all_off)

        scen_layout.addWidget(btn_puff)
        scen_layout.addWidget(btn_chrg)
        scen_layout.addWidget(btn_all_on)
        scen_layout.addWidget(btn_all_off)

        right_box.addWidget(grp_scen)

        main_h.addLayout(right_box)
        layout.addLayout(main_h)

    # --- СЛОТЫ УПРАВЛЕНИЯ ---
    def on_conn_status(self, connected, msg):
        if connected:
            self.lbl_status.setText(f"[✓] {msg}")
            self.lbl_status.setStyleSheet("color: #10b981; font-size: 13px; font-weight: bold;")
        else:
            self.lbl_status.setText(f"[X] {msg}")
            self.lbl_status.setStyleSheet("color: #ef4444; font-size: 13px; font-weight: bold;")

    def on_telemetry(self, vdd, hb):
        pass

    def on_percent_show_toggled(self, checked):
        self.percent_show = checked
        self.update_display()

    def set_percent_and_enable(self, val):
        self.chk_percent_show.setChecked(True)
        self.slider_pct.setValue(val)

    def on_slider_pct_changed(self, val):
        self.percent_val = val
        self.update_display()

    def toggle_demo_pct(self, checked):
        self.demo_counter = checked
        if checked:
            self.chk_percent_show.setChecked(True)
            self.btn_demo_pct.setStyleSheet("background: #16a34a; font-weight: bold;")
        else:
            self.btn_demo_pct.setStyleSheet("")

    def on_slider_bars_changed(self, val):
        self.liquid_bars = val
        self.lbl_bars_txt.setText(f"{val} полоски" if val > 0 else "0 (Пусто)")
        self.update_display()

    def on_drop_center_toggled(self, checked):
        self.drop_center_on = checked
        self.update_display()

    def on_drop_rim_mode_changed(self, btn_id, checked):
        if checked:
            self.drop_rim_mode = btn_id
            self.update_display()

    def on_lightning_mode_changed(self, btn_id, checked):
        if checked:
            self.lightning_mode = btn_id
            self.update_display()

    def on_boost_mode_changed(self, btn_id, checked):
        if checked:
            self.boost_mode = btn_id
            self.update_display()

    # --- СЦЕНАРИИ ---
    def scen_puff(self):
        """Имитация затяжки: турбо-буст + вращение капли"""
        self.chk_percent_show.setChecked(True)
        self.bg_drop_rim.button(2).setChecked(True) # Вращение ободка
        self.bg_boost.button(3).setChecked(True)    # Турбо раскрутка
        self.bg_ln.button(0).setChecked(True)       # Молния выкл
        self.slider_pct.setValue(max(0, self.percent_val - 1)) # -1% на затяжку

    def scen_charging(self):
        """Режим зарядки: моргание молнии + заполнение батареи"""
        self.chk_percent_show.setChecked(True)
        self.bg_ln.button(2).setChecked(True)       # Моргание молнии
        self.chk_drop_center.setChecked(True)       # Капля горит
        self.bg_drop_rim.button(1).setChecked(True) # Ободок горит
        self.bg_boost.button(0).setChecked(True)    # Буст выкл
        self.slider_pct.setValue(min(100, self.percent_val + 5))

    def scen_all_on(self):
        self.chk_percent_show.setChecked(True)
        self.slider_pct.setValue(100)
        self.slider_bars.setValue(3)
        self.chk_drop_center.setChecked(True)
        self.bg_drop_rim.button(1).setChecked(True)
        self.bg_ln.button(1).setChecked(True)
        self.bg_boost.button(1).setChecked(True)

    def scen_all_off(self):
        """Полное погашение экрана: выключает проценты, жидкость, каплю, молнию и буст"""
        self.chk_percent_show.setChecked(False) # Никаких цифр и никаких 0%
        self.slider_bars.setValue(0)
        self.chk_drop_center.setChecked(False)
        self.bg_drop_rim.button(0).setChecked(True)
        self.bg_ln.button(0).setChecked(True)
        self.bg_boost.button(0).setChecked(True)

    # --- ТАЙМЕР АНИМАЦИИ (10 FPS) ---
    def on_anim_tick(self):
        need_update = False

        # Демо счётчик
        if self.demo_counter and self.percent_show:
            nv = (self.percent_val + 1) % 101
            self.slider_pct.setValue(nv)

        # Анимация вращения ободка капли
        if self.drop_rim_mode == 2:
            self.drop_anim_frame = (self.drop_anim_frame + 1) % 4
            need_update = True

        # Моргание молнии (раз в 500 мс = каждые 5 тиков)
        if self.lightning_mode == 2:
            self.lightning_state = not self.lightning_state if (time.time() % 0.8 < 0.4) else self.lightning_state
            need_update = True

        # BOOST: моргание или турбо вращение
        if self.boost_mode == 2:
            self.boost_blink_state = (time.time() % 0.6 < 0.3)
            need_update = True
        elif self.boost_mode == 3:
            self.boost_anim_frame = (self.boost_anim_frame + 1) % 4
            need_update = True

        if need_update:
            self.update_display()

    # --- РАСЧЁТ ПАР ДЛЯ АППАРАТНОГО ДИСПЛЕЯ ---
    def update_display(self):
        pairs = []

        # 1. Цифры и Проценты (ЕСЛИ ВКЛЮЧЕНЫ)
        if self.percent_show:
            val = self.percent_val
            pairs.append(SEGS['percent'])
            self.lbl_v_percent.setVisible(True)

            if val >= 100:
                pairs.append(SEGS['hundred_top'])
                pairs.append(SEGS['hundred_bot'])
                d1_segs = FONT_7SEG[0]
                d2_segs = FONT_7SEG[0]
                self.lbl_v_hundred.setVisible(True)
                self.lbl_v_digits.setText("00")
            else:
                self.lbl_v_hundred.setVisible(False)
                d1 = val // 10
                d2 = val % 10
                d1_segs = FONT_7SEG[d1] if val >= 10 else []
                d2_segs = FONT_7SEG[d2]
                self.lbl_v_digits.setText(f"{val:02d}" if val >= 10 else f"{val}")

            for s in d1_segs:
                pairs.append(SEGS[f'd1_{s}'])
            for s in d2_segs:
                pairs.append(SEGS[f'd2_{s}'])
        else:
            # Дисплей цифр полностью погашен
            self.lbl_v_hundred.setVisible(False)
            self.lbl_v_digits.setText("")
            self.lbl_v_percent.setVisible(False)

        # 2. Полоски жидкости
        self.lbl_v_bar1.setStyleSheet("color: #38bdf8;" if self.liquid_bars >= 1 else "color: #1e293b;")
        self.lbl_v_bar2.setStyleSheet("color: #38bdf8;" if self.liquid_bars >= 2 else "color: #1e293b;")
        self.lbl_v_bar3.setStyleSheet("color: #38bdf8;" if self.liquid_bars >= 3 else "color: #1e293b;")

        if self.liquid_bars >= 1: pairs.append(SEGS['bar1'])
        if self.liquid_bars >= 2: pairs.append(SEGS['bar2'])
        if self.liquid_bars >= 3: pairs.append(SEGS['bar3'])

        # 3. РАЗДЕЛЬНАЯ КАПЛЯ
        # А. Центральная капля (независимый чекбокс)
        if self.drop_center_on:
            pairs.append(SEGS['drop_center'])

        # Б. Обводка (ободок) капли (независимый радиобаттон)
        rim_quads = [SEGS['drop_top'], SEGS['drop_right'], SEGS['drop_bot'], SEGS['drop_left']]
        if self.drop_rim_mode == 1:
            # Горит вся обводка статично (все 4 сегмента)
            pairs.extend(rim_quads)
        elif self.drop_rim_mode == 2:
            # Бегущий огонёк только по обводке
            pairs.append(rim_quads[self.drop_anim_frame])

        # Визуализация капли в GUI
        if self.drop_center_on and self.drop_rim_mode == 1:
            self.lbl_v_drop_rim.setText("💧")
            self.lbl_v_drop_rim.setStyleSheet("font-size: 60px; color: #38bdf8;")
            self.lbl_v_drop_info.setText("Капля + Полный ободок")
        elif self.drop_center_on and self.drop_rim_mode == 0:
            self.lbl_v_drop_rim.setText("•")
            self.lbl_v_drop_rim.setStyleSheet("font-size: 60px; color: #0284c7;")
            self.lbl_v_drop_info.setText("Только центральная капля")
        elif not self.drop_center_on and self.drop_rim_mode == 1:
            self.lbl_v_drop_rim.setText("◯")
            self.lbl_v_drop_rim.setStyleSheet("font-size: 60px; color: #38bdf8;")
            self.lbl_v_drop_info.setText("Только ободок (без центра)")
        elif self.drop_rim_mode == 2:
            anim_chars = ["▲", "▶", "▼", "◀"]
            self.lbl_v_drop_rim.setText(anim_chars[self.drop_anim_frame])
            self.lbl_v_drop_rim.setStyleSheet("font-size: 60px; color: #38bdf8;")
            self.lbl_v_drop_info.setText(f"Вращение ободка ({'с центром' if self.drop_center_on else 'без центра'})")
        else:
            self.lbl_v_drop_rim.setText("·")
            self.lbl_v_drop_rim.setStyleSheet("font-size: 60px; color: #1e293b;")
            self.lbl_v_drop_info.setText("Капля выключена")

        # 4. Молния
        ln_active = False
        if self.lightning_mode == 1:
            ln_active = True
        elif self.lightning_mode == 2:
            ln_active = (time.time() % 0.8 < 0.4)

        if ln_active:
            pairs.append(SEGS['lightning'])
            self.lbl_v_lightning.setStyleSheet("color: #facc15; font-size: 20px; font-weight: bold;")
        else:
            self.lbl_v_lightning.setStyleSheet("color: #1e293b; font-size: 20px; font-weight: bold;")

        # 5. BOOST
        boost_active = False
        if self.boost_mode == 1:
            pairs.extend([SEGS['boost_tl'], SEGS['boost_tr'], SEGS['boost_bl'], SEGS['boost_br']])
            boost_active = True
        elif self.boost_mode == 2:
            if time.time() % 0.6 < 0.3:
                pairs.extend([SEGS['boost_tl'], SEGS['boost_tr'], SEGS['boost_bl'], SEGS['boost_br']])
                boost_active = True
        elif self.boost_mode == 3:
            boost_quads = [SEGS['boost_tl'], SEGS['boost_tr'], SEGS['boost_br'], SEGS['boost_bl']]
            pairs.append(boost_quads[self.boost_anim_frame])
            boost_active = True

        if boost_active:
            self.lbl_v_boost.setStyleSheet("""
                background: #450a0a; color: #ef4444; border: 2px solid #ef4444; 
                border-radius: 8px; font-size: 18px; font-weight: bold; padding: 6px;
            """)
        else:
            self.lbl_v_boost.setStyleSheet("""
                background: #0f172a; color: #334155; border: 2px solid #1e293b; 
                border-radius: 8px; font-size: 18px; font-weight: bold; padding: 6px;
            """)

        # Отправляем обновленный набор пар на микроконтроллер через SWD
        self.worker.set_pairs(pairs)

def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    controller = DM02iController()
    controller.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
