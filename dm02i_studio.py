# -*- coding: utf-8 -*-
"""
DM02i Studio - Графическая среда управления и картографирования дисплея платы вейпа DM02i V03
MCU: Puya PY32C642 / PY32F002Bx5 (ARM Cortex-M0+ @ 24MHz)
"""

import sys
import os
import time
import queue
import json

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass
import traceback

def log_exception(exc_type, exc_value, exc_tb):
    err = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    sys.stderr.write(err)
    try:
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "studio_error.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n" + err)
    except Exception:
        pass

sys.excepthook = log_exception

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QGridLayout, QLabel, QPushButton, QFrame, 
    QSlider, QProgressBar, QComboBox, QTableWidget, 
    QTableWidgetItem, QHeaderView, QRadioButton, QButtonGroup,
    QScrollArea, QLineEdit
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor
import pylink

# Shared memory in SRAM
SCANNER_ADDR = 0x2000000C

PIN_NAMES = [
    "PB0 (Контакт 1)",
    "PB1 (Контакт 2)",
    "PB2 (Контакт 3)",
    "PB3 (Контакт 4)",
    "PB5 (Контакт 5)",
    "PC1 (Контакт 6)"
]

def normalize_pin_name(name):
    if not name:
        return PIN_NAMES[0]
    for p in PIN_NAMES:
        # Match 'PB5' with 'PB5 (Пин 9)' or exact
        base_p = p.split()[0]
        if name == base_p or name == p or name in p:
            return p
    return name

MAP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dm02i_screen_map.json")

class SwdWorker(QThread):
    connection_changed = pyqtSignal(bool, str)
    telemetry_updated  = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.running = True
        self.command_queue = queue.Queue()

    def send_cmd(self, cmd_type, value):
        self.command_queue.put((cmd_type, value))

    def stop(self):
        self.running = False
        self.wait(1000)

    def run(self):
        j = None
        base = None
        fail_count = 0

        while self.running:
            if j is None:
                try:
                    j = pylink.JLink()
                    if j.num_connected_emulators() > 0:
                        try:
                            j.open('774496021')
                        except Exception:
                            j.open()
                    else:
                        j.open()
                    j.set_tif(pylink.enums.JLinkInterfaces.SWD)
                    j.set_speed(1000)
                    j.coresight_configure()
                    j.coresight_write(0, 0x1E, ap=False) # Clear aborts
                    j.coresight_write(1, 0x50000000, ap=False) # Power-up DP
                    j.coresight_write(2, 0x00000000, ap=False) # Select AP 0 Bank 0
                    j.coresight_write(0, 0x23000002, ap=True)  # CSW 32-bit transfer
                    
                    # Auto-detect g_scanner base address
                    base = None
                    for cand in [0x2000000C, 0x20000000, 0x20000004, 0x20000008, 0x20000010]:
                        j.coresight_write(1, cand, ap=True)
                        j.coresight_read(3, ap=True) # dummy
                        val = j.coresight_read(3, ap=True)
                        if val == 0x5343414E:
                            base = cand
                            break
                    if base is None:
                        base = 0x2000000C
                    
                    fail_count = 0
                    self.connection_changed.emit(True, f"Подключено: J-Link {j.serial_number} (1000 кГц, ОЗУ: 0x{base:08X})")
                except Exception as e:
                    if j:
                        try:
                            j.close()
                        except Exception:
                            pass
                        j = None
                    self.connection_changed.emit(False, f"Поиск чипа... ({e})")
                    self.msleep(1000)
                    continue

            # Connected - process commands & read telemetry
            try:
                # Process pending commands from GUI
                while not self.command_queue.empty():
                    cmd, val = self.command_queue.get_nowait()
                    try:
                        j.coresight_write(0, 0x1E, ap=False) # Clear abort
                        if cmd == 'PAUSE':
                            j.coresight_write(1, base + 0x1C, ap=True)
                            j.coresight_write(3, int(val), ap=True)
                        elif cmd == 'MODE':
                            j.coresight_write(1, base + 0x04, ap=True)
                            j.coresight_write(3, int(val), ap=True)
                        elif cmd == 'DELAY':
                            j.coresight_write(1, base + 0x18, ap=True)
                            j.coresight_write(3, int(val), ap=True)
                        elif cmd == 'NEXT':
                            j.coresight_write(1, base + 0x30, ap=True)
                            j.coresight_write(3, 1, ap=True)
                        elif cmd == 'PREV':
                            j.coresight_write(1, base + 0x34, ap=True)
                            j.coresight_write(3, 1, ap=True)
                        elif cmd == 'SET_HIGH':
                            j.coresight_write(1, base + 0x38, ap=True)
                            j.coresight_write(3, int(val), ap=True)
                        elif cmd == 'SET_LOW':
                            j.coresight_write(1, base + 0x3C, ap=True)
                            j.coresight_write(3, int(val), ap=True)
                        elif cmd == 'SET_STEP':
                            j.coresight_write(1, base + 0x08, ap=True)
                            j.coresight_write(3, int(val), ap=True)
                            j.coresight_write(1, base + 0x30, ap=True)
                            j.coresight_write(3, 1, ap=True)
                        elif cmd == 'SET_MUX':
                            pairs = val[:32]
                            j.coresight_write(1, base + 0x44, ap=True)
                            j.coresight_write(3, len(pairs), ap=True)
                            for idx, (h, l) in enumerate(pairs):
                                packed = ((h & 0xFF) << 8) | (l & 0xFF)
                                j.coresight_write(1, base + 0x48 + idx * 4, ap=True)
                                j.coresight_write(3, packed, ap=True)
                            # switch to Mode 4 (Multiplex)
                            j.coresight_write(1, base + 0x04, ap=True)
                            j.coresight_write(3, 4, ap=True)
                    except Exception as cmd_err:
                        print(f"[SWD Command Warning] {cmd}: {cmd_err}")

                # Read telemetry words (17 words from base: 0x00 to 0x40)
                j.coresight_write(0, 0x1E, ap=False) # Clear abort
                j.coresight_write(0, 0x23000012, ap=True) # Auto-increment CSW
                j.coresight_write(1, base, ap=True) # TAR = base
                
                words = []
                for _ in range(17):
                    words.append(j.coresight_read(3, ap=True))
                
                # Restore non-increment CSW
                j.coresight_write(0, 0x23000002, ap=True)

                magic = words[0]
                if magic == 0x5343414E: # 'SCAN'
                    mode    = words[1]
                    step    = words[2]
                    total   = words[3]
                    h_idx   = words[4]
                    l_idx   = words[5]
                    delay   = words[6]
                    paused  = words[7]
                    idr_a   = words[8]
                    idr_b   = words[9]
                    vdd_mv  = words[10]
                    raw_adc = words[11]
                    # words[12..15] are commands/manual
                    hb      = words[16]

                    h_name = PIN_NAMES[h_idx] if h_idx < len(PIN_NAMES) else f"P{h_idx}"
                    l_name = PIN_NAMES[l_idx] if l_idx < len(PIN_NAMES) else f"P{l_idx}"

                    self.telemetry_updated.emit({
                        'magic': magic,
                        'mode': mode,
                        'step': step,
                        'total': total,
                        'h_idx': h_idx,
                        'l_idx': l_idx,
                        'h_name': h_name,
                        'l_name': l_name,
                        'delay': delay,
                        'paused': paused,
                        'idr_a': idr_a,
                        'idr_b': idr_b,
                        'vdd_mv': vdd_mv,
                        'raw_adc': raw_adc,
                        'hb': hb
                    })

                fail_count = 0
                self.msleep(60)

            except Exception as e:
                fail_count += 1
                if fail_count >= 4:
                    if j:
                        try:
                            j.close()
                        except Exception:
                            pass
                        j = None
                    self.connection_changed.emit(False, f"Связь прервана: {e}")
                    self.msleep(1000)
                else:
                    self.msleep(80)

        if j:
            try:
                j.close()
            except Exception:
                pass


class DM02iStudio(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DM02i Studio - Аппаратный картограф и диспетчер вейпа")
        self.resize(1150, 780)
        self.screen_map = {}
        self.current_h_name = "PA0"
        self.current_l_name = "PA1"
        self.current_step = 0
        self.load_screen_map()

        self.init_ui()

        # Start SWD Worker after UI is ready
        self.worker = SwdWorker()
        self.worker.connection_changed.connect(self.on_connection_changed)
        self.worker.telemetry_updated.connect(self.on_telemetry_updated)
        self.worker.start()

    def closeEvent(self, event):
        self.worker.stop()
        super().closeEvent(event)

    def load_screen_map(self):
        if os.path.exists(MAP_FILE):
            try:
                with open(MAP_FILE, 'r', encoding='utf-8') as f:
                    raw_map = json.load(f)
                    self.screen_map = {}
                    for k, v in raw_map.items():
                        self.screen_map[k] = {
                            'high': normalize_pin_name(v.get('high', '')),
                            'low': normalize_pin_name(v.get('low', '')),
                            'step': v.get('step', 0)
                        }
            except Exception:
                self.screen_map = {}

    def save_screen_map(self):
        try:
            with open(MAP_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.screen_map, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("Ошибка сохранения карты:", e)

    def init_ui(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0b0f17;
            }
            QWidget {
                color: #e2e8f0;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QFrame.card {
                background-color: #131b28;
                border: 1px solid #233148;
                border-radius: 12px;
                padding: 14px;
            }
            QLabel.cardTitle {
                font-size: 15px;
                font-weight: bold;
                color: #38bdf8;
                border-bottom: 1px solid #1e293b;
                padding-bottom: 6px;
                margin-bottom: 8px;
            }
            QPushButton {
                background-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
                color: #f8fafc;
            }
            QPushButton:hover {
                background-color: #2e3d54;
                border-color: #38bdf8;
            }
            QPushButton:pressed {
                background-color: #0284c7;
            }
            QPushButton.primary {
                background-color: #0284c7;
                border: 1px solid #38bdf8;
            }
            QPushButton.primary:hover {
                background-color: #0369a1;
            }
            QPushButton.danger {
                background-color: #be123c;
                border: 1px solid #f43f5e;
            }
            QPushButton.danger:hover {
                background-color: #9f1239;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #1e293b;
                border-radius: 3px;
            }
            QSlider::sub-page:horizontal {
                background: #38bdf8;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #f8fafc;
                width: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QTableWidget {
                background-color: #0f172a;
                border: 1px solid #233148;
                border-radius: 8px;
                gridline-color: #1e293b;
            }
            QHeaderView::section {
                background-color: #1e293b;
                color: #94a3b8;
                padding: 4px;
                border: 1px solid #0f172a;
                font-weight: bold;
            }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(12)

        # 1. Top Status Header
        header = QFrame()
        header.setStyleSheet("background-color: #131b28; border: 1px solid #233148; border-radius: 8px; padding: 6px 12px;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(8, 4, 8, 4)

        self.lbl_status = QLabel("[*] Поиск программатора...")
        self.lbl_status.setStyleSheet("color: #f59e0b; font-weight: bold; font-size: 14px;")

        self.lbl_vtarget = QLabel("АКБ / VDD: -- В")
        self.lbl_vtarget.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 14px;")

        self.lbl_switch = QLabel("ТУМБЛЕР BOOST: --")
        self.lbl_switch.setStyleSheet("color: #a855f7; font-weight: bold; font-size: 14px;")

        self.lbl_mic = QLabel("ДАТЧИК ЗАТЯЖКИ: ПОКОЙ")
        self.lbl_mic.setStyleSheet("color: #10b981; font-weight: bold; font-size: 14px;")

        h_layout.addWidget(self.lbl_status)
        h_layout.addStretch()
        h_layout.addWidget(self.lbl_vtarget)
        h_layout.addSpacing(20)
        h_layout.addWidget(self.lbl_switch)
        h_layout.addSpacing(20)
        h_layout.addWidget(self.lbl_mic)

        main_layout.addWidget(header)

        # 2. Main Content Split: Left (Display & Mapping) | Right (Controls & Logs)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(14)

        # === LEFT COLUMN: Virtual Display & Quick Segment Map ===
        left_col = QVBoxLayout()

        card_display = QFrame()
        card_display.setProperty("class", "card")
        d_layout = QVBoxLayout(card_display)

        t_lbl = QLabel("ВИРТУАЛЬНЫЙ ДИСПЛЕЙ DM02i (НАЖМИ НА ЭЛЕМЕНТ ДЛЯ ПРИВЯЗКИ)")
        t_lbl.setProperty("class", "cardTitle")
        d_layout.addWidget(t_lbl)

        # Black bezel display container
        disp_box = QFrame()
        disp_box.setStyleSheet("""
            background-color: #030712;
            border: 3px solid #334155;
            border-radius: 20px;
            padding: 24px;
        """)
        disp_inner = QHBoxLayout(disp_box)
        disp_inner.setSpacing(20)

        # 1. Left: Liquid Oval with 3 bars + Drop
        liquid_box = QFrame()
        liquid_box.setStyleSheet("border: 2px solid #0284c7; border-radius: 28px; padding: 10px 8px; background: #082f49;")
        l_layout = QVBoxLayout(liquid_box)
        l_layout.setSpacing(6)

        self.btn_bar3 = QPushButton("- 3")
        self.btn_bar2 = QPushButton("- 2")
        self.btn_bar1 = QPushButton("- 1")
        self.btn_drop = QPushButton("КАПЛЯ")
        self.btn_liquid_oval = QPushButton("ОБОДОК")
        for b in [self.btn_bar3, self.btn_bar2, self.btn_bar1, self.btn_drop, self.btn_liquid_oval]:
            b.setStyleSheet("background: #0369a1; color: #38bdf8; font-size: 13px; font-weight: bold; min-height: 24px; border-radius: 6px;")
            b.clicked.connect(lambda ch, btn=b: self.map_element(btn.text()))
            l_layout.addWidget(b)

        disp_inner.addWidget(liquid_box)

        # 2. Middle: Lightning + % + Digits (1 + 88)
        mid_box = QVBoxLayout()
        mid_top = QHBoxLayout()

        self.btn_lightning = QPushButton("МОЛНИЯ")
        self.btn_lightning.setStyleSheet("background: #ca8a04; color: #fef08a; font-weight: bold; font-size: 13px; border-radius: 6px; padding: 6px 12px;")
        self.btn_lightning.clicked.connect(lambda *args: self.map_element("Молния"))

        self.btn_percent = QPushButton("ПРОЦЕНТ %")
        self.btn_percent.setStyleSheet("background: #15803d; color: #86efac; font-weight: bold; font-size: 13px; border-radius: 6px; padding: 6px 12px;")
        self.btn_percent.clicked.connect(lambda *args: self.map_element("Процент %"))

        mid_top.addWidget(self.btn_lightning)
        mid_top.addWidget(self.btn_percent)
        mid_box.addLayout(mid_top)

        # Digits row: Hundreds '1' + Two 7-segment digits (Tens and Units)
        digits_row = QHBoxLayout()
        self.digit_btns = {}

        # Hundreds '1' digit (TWO SEGMENTS: Top and Bottom)
        hundreds_frame = QFrame()
        hundreds_frame.setStyleSheet("background: #111827; border: 1px solid #374151; border-radius: 8px; padding: 4px;")
        h_layout = QVBoxLayout(hundreds_frame)
        h_layout.setSpacing(3)

        self.btn_hundreds_top = QPushButton("1▲")
        self.btn_hundreds_top.setFixedSize(30, 44)
        self.btn_hundreds_top.setStyleSheet("background: #1f2937; color: #eab308; font-weight: bold; font-size: 13px; padding: 0; border-radius: 4px;")
        self.btn_hundreds_top.setToolTip("Верхний сегмент единицы сотен")
        self.btn_hundreds_top.clicked.connect(lambda *args: self.map_element("Сотня 1 (Верх)"))
        h_layout.addWidget(self.btn_hundreds_top)

        self.btn_hundreds_bot = QPushButton("1▼")
        self.btn_hundreds_bot.setFixedSize(30, 44)
        self.btn_hundreds_bot.setStyleSheet("background: #1f2937; color: #eab308; font-weight: bold; font-size: 13px; padding: 0; border-radius: 4px;")
        self.btn_hundreds_bot.setToolTip("Нижний сегмент единицы сотен")
        self.btn_hundreds_bot.clicked.connect(lambda *args: self.map_element("Сотня 1 (Низ)"))
        h_layout.addWidget(self.btn_hundreds_bot)

        self.btn_hundreds_all = QPushButton("1 Вся")
        self.btn_hundreds_all.setFixedSize(30, 24)
        self.btn_hundreds_all.setStyleSheet("background: #374151; color: #facc15; font-size: 9px; padding: 0; border-radius: 3px;")
        self.btn_hundreds_all.clicked.connect(lambda *args: self.map_element("Сотня 1 (Вся)"))
        h_layout.addWidget(self.btn_hundreds_all)

        lbl_h = QLabel("Сотня")
        lbl_h.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_h.setStyleSheet("color: #9ca3af; font-size: 9px;")
        h_layout.addWidget(lbl_h)
        digits_row.addWidget(hundreds_frame)

        digit_labels = {1: "Десятки", 2: "Единицы"}
        for d in [1, 2]:
            d_frame = QFrame()
            d_frame.setStyleSheet("background: #111827; border: 1px solid #374151; border-radius: 8px; padding: 6px;")
            d_grid = QGridLayout(d_frame)
            d_grid.setSpacing(3)

            seg_names = ['A', 'B', 'C', 'D', 'E', 'F', 'G']
            # Standard 7-seg layout
            positions = {
                'A': (0, 1),
                'B': (1, 2),
                'C': (3, 2),
                'D': (4, 1),
                'E': (3, 0),
                'F': (1, 0),
                'G': (2, 1)
            }
            for s in seg_names:
                r, c = positions[s]
                b = QPushButton(s)
                b.setFixedSize(28, 22)
                b.setStyleSheet("background: #1f2937; color: #eab308; font-weight: bold; font-size: 11px; padding: 0;")
                name = f"Цифра {d} Сегм {s}"
                b.clicked.connect(lambda ch, n=name: self.map_element(n))
                d_grid.addWidget(b, r, c)
                self.digit_btns[name] = b

            lbl_d = QLabel(f"Цифра {d} ({digit_labels[d]})")
            lbl_d.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl_d.setStyleSheet("color: #9ca3af; font-size: 10px;")
            d_grid.addWidget(lbl_d, 5, 0, 1, 3)

            digits_row.addWidget(d_frame)

        mid_box.addLayout(digits_row)
        disp_inner.addLayout(mid_box)

        # 3. Right: BOOST panel (Multiple diodes & letters & frame)
        boost_frame = QFrame()
        boost_frame.setStyleSheet("background: #2e1065; border: 2px solid #a855f7; border-radius: 16px; padding: 6px;")
        boost_lay = QVBoxLayout(boost_frame)
        boost_lay.setSpacing(4)

        b_title = QLabel("ПЛАШКА BOOST")
        b_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        b_title.setStyleSheet("color: #f3e8ff; font-weight: bold; font-size: 11px;")
        boost_lay.addWidget(b_title)

        # Letters row: B, O, O, S, T
        b_letters_row = QHBoxLayout()
        b_letters_row.setSpacing(2)
        for letter in ["B", "O₁", "O₂", "S", "T"]:
            b_btn = QPushButton(letter)
            b_btn.setFixedSize(24, 28)
            b_btn.setStyleSheet("background: #581c87; color: #f3e8ff; font-weight: bold; font-size: 11px; padding: 0; border-radius: 3px;")
            b_name = f"BOOST Буква {letter}"
            b_btn.clicked.connect(lambda ch, n=b_name: self.map_element(n))
            b_letters_row.addWidget(b_btn)
        boost_lay.addLayout(b_letters_row)

        # Diodes row: Д1, Д2, Д3, Д4
        diodes_row = QHBoxLayout()
        diodes_row.setSpacing(2)
        for d_num in [1, 2, 3, 4]:
            d_btn = QPushButton(f"Д{d_num}")
            d_btn.setFixedSize(30, 24)
            d_btn.setStyleSheet("background: #6b21a8; color: #e9d5ff; font-size: 11px; padding: 0; border-radius: 3px;")
            d_name = f"BOOST Диод {d_num}"
            d_btn.clicked.connect(lambda ch, n=d_name: self.map_element(n))
            diodes_row.addWidget(d_btn)
        boost_lay.addLayout(diodes_row)

        self.btn_boost_oval = QPushButton("ОБОДОК BOOST")
        self.btn_boost_oval.setStyleSheet("background-color: #4c1d95; color: #d8b4fe; font-size: 11px; font-weight: bold; border: 1px solid #a855f7; border-radius: 4px; min-height: 22px;")
        self.btn_boost_oval.clicked.connect(lambda *args: self.map_element("Ободок BOOST"))
        boost_lay.addWidget(self.btn_boost_oval)

        self.btn_boost_all = QPushButton("ВЕСЬ BOOST")
        self.btn_boost_all.setStyleSheet("background-color: #7e22ce; color: #ffffff; font-size: 11px; font-weight: bold; border: 1px solid #c084fc; border-radius: 4px; min-height: 24px;")
        self.btn_boost_all.clicked.connect(lambda *args: self.map_element("Надпись BOOST"))
        boost_lay.addWidget(self.btn_boost_all)

        disp_inner.addWidget(boost_frame)

        d_layout.addWidget(disp_box)

        # Quick custom element mapping input
        custom_frame = QFrame()
        custom_frame.setStyleSheet("background: #0f172a; border: 1px solid #1e293b; border-radius: 6px; padding: 4px 8px;")
        c_layout = QHBoxLayout(custom_frame)
        c_layout.setContentsMargins(6, 4, 6, 4)
        c_lbl = QLabel("Свой элемент:")
        c_lbl.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: bold;")
        c_layout.addWidget(c_lbl)
        self.txt_custom_name = QLineEdit()
        self.txt_custom_name.setPlaceholderText("Введи название символа, если его нет на кнопках выше...")
        self.txt_custom_name.setStyleSheet("background: #1e293b; border: 1px solid #334155; color: #f8fafc; padding: 5px 8px; border-radius: 4px; font-size: 12px;")
        self.txt_custom_name.returnPressed.connect(self.on_map_custom_element)
        c_layout.addWidget(self.txt_custom_name)
        self.btn_custom_map = QPushButton("+ Привязать символ")
        self.btn_custom_map.setStyleSheet("background: #2563eb; color: #ffffff; font-weight: bold; padding: 5px 14px; border-radius: 4px; font-size: 12px;")
        self.btn_custom_map.clicked.connect(self.on_map_custom_element)
        c_layout.addWidget(self.btn_custom_map)
        d_layout.addWidget(custom_frame)

        # Current pair indicator badge
        self.pair_card = QFrame()
        self.pair_card.setStyleSheet("background: #0f172a; border: 2px solid #0284c7; border-radius: 8px; padding: 10px;")
        p_lay = QVBoxLayout(self.pair_card)
        self.lbl_pair_title = QLabel("АКТИВНЫЙ ШАГ СКАНИРОВАНИЯ:")
        self.lbl_pair_title.setStyleSheet("color: #94a3b8; font-size: 12px; font-weight: bold;")
        self.lbl_pair_value = QLabel("HIGH: PA0 (+3.3V) -> LOW: PA1 (GND)")
        self.lbl_pair_value.setStyleSheet("color: #38bdf8; font-size: 20px; font-weight: bold;")
        p_lay.addWidget(self.lbl_pair_title)
        p_lay.addWidget(self.lbl_pair_value)
        d_layout.addWidget(self.pair_card)

        left_col.addWidget(card_display)
        content_layout.addLayout(left_col, 5)

        # === RIGHT COLUMN: Controls & Found Mapping Table ===
        right_col = QVBoxLayout()

        # Card: Scan Controls
        card_ctrl = QFrame()
        card_ctrl.setProperty("class", "card")
        c_layout = QVBoxLayout(card_ctrl)

        ctrl_title = QLabel("УПРАВЛЕНИЕ СКАНИРОВАНИЕМ")
        ctrl_title.setProperty("class", "cardTitle")
        c_layout.addWidget(ctrl_title)

        # Buttons row: Play/Pause, Next, Prev
        btn_row = QHBoxLayout()
        self.btn_pause = QPushButton("[II] ПАУЗА")
        self.btn_pause.setProperty("class", "primary")
        self.btn_pause.clicked.connect(self.toggle_pause)

        self.btn_prev = QPushButton("< Назад")
        self.btn_prev.clicked.connect(lambda *args: self.worker.send_cmd('PREV', 1))

        self.btn_next = QPushButton("Вперед >")
        self.btn_next.clicked.connect(lambda *args: self.worker.send_cmd('NEXT', 1))

        btn_row.addWidget(self.btn_prev)
        btn_row.addWidget(self.btn_pause)
        btn_row.addWidget(self.btn_next)
        c_layout.addLayout(btn_row)

        # Speed slider
        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel("Скорость:"))
        self.slider_speed = QSlider(Qt.Orientation.Horizontal)
        self.slider_speed.setRange(200, 3000)
        self.slider_speed.setValue(1000)
        self.slider_speed.valueChanged.connect(self.on_speed_changed)
        self.lbl_speed_val = QLabel("1000 мс")
        speed_row.addWidget(self.slider_speed)
        speed_row.addWidget(self.lbl_speed_val)
        c_layout.addLayout(speed_row)

        # Mode selection
        mode_row = QHBoxLayout()
        self.radio_charlie = QRadioButton("Charlieplexing")
        self.radio_single  = QRadioButton("Single Pin High")
        self.radio_off     = QRadioButton("Все Выкл")
        self.radio_charlie.setChecked(True)

        self.radio_charlie.toggled.connect(lambda *args: self.worker.send_cmd('MODE', 0) if self.radio_charlie.isChecked() else None)
        self.radio_single.toggled.connect(lambda *args: self.worker.send_cmd('MODE', 2) if self.radio_single.isChecked() else None)
        self.radio_off.toggled.connect(lambda *args: self.worker.send_cmd('MODE', 3) if self.radio_off.isChecked() else None)

        mode_row.addWidget(self.radio_charlie)
        mode_row.addWidget(self.radio_single)
        mode_row.addWidget(self.radio_off)
        c_layout.addLayout(mode_row)

        # Simultaneous Multiplexing Button
        self.btn_mux = QPushButton("⚡ ОДНОВРЕМЕННО ЗАЖЕЧЬ ВСЕ НАЙДЕННЫЕ ЗНАКИ (МУЛЬТИПЛЕКС)")
        self.btn_mux.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981); color: white; font-weight: bold; font-size: 12px; padding: 8px; border-radius: 6px; margin: 4px 0;")
        self.btn_mux.clicked.connect(self.trigger_multiplex)
        c_layout.addWidget(self.btn_mux)

        # Manual Pin Selectors
        man_row = QHBoxLayout()
        man_row.addWidget(QLabel("HIGH (+):"))
        self.combo_high = QComboBox()
        self.combo_high.addItems(PIN_NAMES)
        self.combo_high.currentIndexChanged.connect(self.on_manual_pins_changed)

        man_row.addWidget(self.combo_high)
        man_row.addWidget(QLabel("LOW (-):"))
        self.combo_low = QComboBox()
        self.combo_low.addItems(PIN_NAMES)
        self.combo_low.setCurrentIndex(1)
        self.combo_low.currentIndexChanged.connect(self.on_manual_pins_changed)
        man_row.addWidget(self.combo_low)

        self.btn_hold_pair = QPushButton("Зафиксировать пару")
        self.btn_hold_pair.clicked.connect(self.hold_manual_pair)
        man_row.addWidget(self.btn_hold_pair)
        c_layout.addLayout(man_row)

        right_col.addWidget(card_ctrl)

        # Card: Mapped Elements Table
        card_table = QFrame()
        card_table.setProperty("class", "card")
        t_layout = QVBoxLayout(card_table)

        tbl_title = QLabel("КАРТА НАЙДЕННЫХ СЕГМЕНТОВ (СОХРАНЯЕТСЯ В JSON)")
        tbl_title.setProperty("class", "cardTitle")
        t_layout.addWidget(tbl_title)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Элемент", "HIGH (+)", "LOW (-)", "Действие"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        t_layout.addWidget(self.table)

        # Action buttons: Export / Clear
        act_row = QHBoxLayout()
        btn_save = QPushButton("Сохранить карту в C-драйвер")
        btn_save.clicked.connect(self.export_c_driver)

        btn_clear = QPushButton("Очистить карту")
        btn_clear.setProperty("class", "danger")
        btn_clear.clicked.connect(self.clear_map)

        act_row.addWidget(btn_save)
        act_row.addWidget(btn_clear)
        t_layout.addLayout(act_row)

        right_col.addWidget(card_table)
        content_layout.addLayout(right_col, 6)

        main_layout.addLayout(content_layout)

        self.refresh_table()

    def toggle_pause(self):
        cur_text = self.btn_pause.text()
        if "ПАУЗА" in cur_text:
            self.worker.send_cmd('PAUSE', 1)
            self.btn_pause.setText("[>] СТАРТ")
            self.btn_pause.setStyleSheet("background-color: #16a34a;")
        else:
            self.worker.send_cmd('PAUSE', 0)
            self.btn_pause.setText("[II] ПАУЗА")
            self.btn_pause.setStyleSheet("background-color: #0284c7;")

    def on_speed_changed(self, val):
        self.lbl_speed_val.setText(f"{val} мс")
        self.worker.send_cmd('DELAY', val)

    def on_manual_pins_changed(self):
        self.hold_manual_pair()

    def hold_manual_pair(self):
        h = self.combo_high.currentIndex()
        l = self.combo_low.currentIndex()
        self.worker.send_cmd('MODE', 1) # Mode 1: Manual Pair
        self.worker.send_cmd('SET_HIGH', h)
        self.worker.send_cmd('SET_LOW', l)
        self.btn_pause.setText("[>] ВОЗОБНОВИТЬ АВТО")

    def trigger_multiplex(self):
        pairs = []
        for name, item in self.screen_map.items():
            h_name = normalize_pin_name(item.get('high', ''))
            l_name = normalize_pin_name(item.get('low', ''))
            if h_name in PIN_NAMES and l_name in PIN_NAMES:
                h_idx = PIN_NAMES.index(h_name)
                l_idx = PIN_NAMES.index(l_name)
                if (h_idx, l_idx) not in pairs:
                    pairs.append((h_idx, l_idx))
        if pairs:
            self.radio_charlie.setChecked(False)
            self.radio_single.setChecked(False)
            self.radio_off.setChecked(False)
            self.btn_pause.setText("[>] ВОЗОБНОВИТЬ АВТО")
            self.worker.send_cmd('SET_MUX', pairs)
            self.lbl_status.setText(f"[⚡] Мультиплекс: одновременно горят {len(pairs)} сегментов!")
            self.lbl_status.setStyleSheet("color: #10b981; font-weight: bold; font-size: 14px;")
        else:
            self.lbl_status.setText("[!] Нет привязанных сегментов для мультиплекса")

    def map_element(self, element_name):
        # Bind current active pair to element
        pair_key = f"{self.current_h_name}->{self.current_l_name}"
        self.screen_map[element_name] = {
            'high': self.current_h_name,
            'low': self.current_l_name,
            'step': self.current_step
        }
        self.save_screen_map()
        self.refresh_table()

    def on_map_custom_element(self):
        name = self.txt_custom_name.text().strip()
        if name:
            self.map_element(name)
            self.txt_custom_name.clear()

    def delete_mapped_element(self, element_name):
        if element_name in self.screen_map:
            del self.screen_map[element_name]
            self.save_screen_map()
            self.refresh_table()

    def clear_map(self):
        self.screen_map.clear()
        self.save_screen_map()
        self.refresh_table()

    def refresh_table(self):
        self.table.setRowCount(len(self.screen_map))
        row = 0
        for name, data in self.screen_map.items():
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(data['high']))
            self.table.setItem(row, 2, QTableWidgetItem(data['low']))
            
            btn_del = QPushButton("X")
            btn_del.setFixedSize(28, 24)
            btn_del.setStyleSheet("background: #be123c; color: white; padding: 0; font-weight: bold;")
            btn_del.clicked.connect(lambda ch, n=name: self.delete_mapped_element(n))
            self.table.setCellWidget(row, 3, btn_del)
            row += 1

    def export_c_driver(self):
        out_c = os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_firmware", "dm02i_display_map.h")
        try:
            with open(out_c, "w", encoding="utf-8") as f:
                f.write("// Автоматически сгенерированная карта сегментов DM02i V03\n")
                f.write("#ifndef DM02I_DISPLAY_MAP_H\n#define DM02I_DISPLAY_MAP_H\n\n")
                f.write("typedef struct {\n    const char *name;\n    uint8_t high_pin;\n    uint8_t low_pin;\n} SegmentMap_t;\n\n")
                f.write("static const SegmentMap_t DM02I_SEGMENTS[] = {\n")
                for name, d in self.screen_map.items():
                    f.write(f'    {{"{name}", {d["high"]}_IDX, {d["low"]}_IDX}},\n')
                f.write("};\n\n#endif\n")
            print(f"Экспорт завершен: {out_c}")
        except Exception as e:
            print("Ошибка экспорта:", e)

    def on_connection_changed(self, connected, text):
        if connected:
            self.lbl_status.setText(f"[*] {text}")
            self.lbl_status.setStyleSheet("color: #10b981; font-weight: bold; font-size: 14px;")
        else:
            self.lbl_status.setText(f"[*] {text}")
            self.lbl_status.setStyleSheet("color: #ef4444; font-weight: bold; font-size: 14px;")

    def on_telemetry_updated(self, d):
        self.current_step = d['step']
        self.current_h_name = d['h_name']
        self.current_l_name = d['l_name']

        # Update Voltage
        vdd = d['vdd_mv'] / 1000.0
        self.lbl_vtarget.setText(f"АКБ / VDD: {vdd:.2f} В ({d['vdd_mv']} мВ)")

        # Update Switch / Inputs from IDR
        idr_a = d['idr_a']
        idr_b = d['idr_b']

        # Display pair banner
        self.lbl_pair_title.setText(f"АКТИВНЫЙ ШАГ #{d['step']}/{d['total']}:")
        self.lbl_pair_value.setText(f"HIGH: {d['h_name']} (+3.3V)  ->  LOW: {d['l_name']} (GND)")

        # Sync button text if paused externally
        if d['paused']:
            self.btn_pause.setText("[>] СТАРТ")
            self.btn_pause.setStyleSheet("background-color: #16a34a;")
        else:
            self.btn_pause.setText("[II] ПАУЗА")
            self.btn_pause.setStyleSheet("background-color: #0284c7;")

def main():
    app = QApplication(sys.argv)
    window = DM02iStudio()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
