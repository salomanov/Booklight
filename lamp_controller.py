import sys
import time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QLabel, QPushButton, QFrame, QRadioButton, QButtonGroup, QGridLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
from pyocd.core.helpers import ConnectHelper

# Hardware Register Addresses for PUYA PY32F002B
RCC_BASE    = 0x40021000
RCC_IOPENR  = RCC_BASE + 0x34

GPIOA_BASE  = 0x50000000
GPIOA_MODER = GPIOA_BASE + 0x00
GPIOA_ODR   = GPIOA_BASE + 0x14
GPIOA_BSRR  = GPIOA_BASE + 0x18

GPIOB_BASE  = 0x50000400
GPIOB_MODER = GPIOB_BASE + 0x00
GPIOB_ODR   = GPIOB_BASE + 0x14
GPIOB_BSRR  = GPIOB_BASE + 0x18

TARGET = 'py32f002bx5'


class SwdWorker(QThread):
    connection_changed = pyqtSignal(bool, str)
    state_updated      = pyqtSignal(int, int, int, int, int)  # pa0, pb3, pb2, odr_a, odr_b

    def __init__(self):
        super().__init__()
        self.running = True
        self.command_queue = []

    def queue_command(self, port, bsrr_val):
        self.command_queue.append((port, bsrr_val))

    def stop(self):
        self.running = False
        self.wait(2000)

    def run(self):
        connected = False
        session = None
        target = None

        while self.running:
            try:
                if session is None:
                    session = ConnectHelper.session_with_chosen_probe(
                        target_override=TARGET,
                        connect_mode='attach',
                        options={'auto_unlock': False, 'frequency': 1000000}
                    )
                    session.open()
                    target = session.target

                    # Ensure Clocks & GPIO modes are configured
                    try:
                        iopenr = target.read32(RCC_IOPENR)
                        target.write32(RCC_IOPENR, iopenr | 0x03) # GPIOAEN | GPIOBEN

                        # PA0 as Output Push-Pull (bits 1:0 = 01)
                        moder_a = target.read32(GPIOA_MODER)
                        target.write32(GPIOA_MODER, (moder_a & ~0x03) | 0x01)

                        # PB2 and PB3 as Output Push-Pull (bits 7:4 = 0101 -> 0x50)
                        moder_b = target.read32(GPIOB_MODER)
                        target.write32(GPIOB_MODER, (moder_b & ~0xF0) | 0x50)
                    except Exception as e:
                        print(f"GPIO config warning: {e}")

                    connected = True
                    self.connection_changed.emit(True, "J-Link STLink: Подключено (SWD 24/7 активен)")

                # Execute pending write commands
                while self.command_queue:
                    port, bsrr_val = self.command_queue.pop(0)
                    if port == 'A':
                        target.write32(GPIOA_BSRR, bsrr_val)
                    elif port == 'B':
                        target.write32(GPIOB_BSRR, bsrr_val)

                # Read current hardware GPIO output states
                odr_a = target.read32(GPIOA_ODR)
                odr_b = target.read32(GPIOB_ODR)

                pa0 = (odr_a >> 0) & 1
                pb3 = (odr_b >> 3) & 1
                pb2 = (odr_b >> 2) & 1

                self.state_updated.emit(pa0, pb3, pb2, odr_a, odr_b)
                self.msleep(80)

            except Exception as e:
                if connected:
                    connected = False
                    self.connection_changed.emit(False, f"Связь прервана: {e}")
                if session:
                    try:
                        session.close()
                    except Exception:
                        pass
                    session = None
                    target = None
                self.msleep(1000)

        if session:
            try:
                session.close()
            except Exception:
                pass


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BookLight — Пульт управления 3 каналами (PA0, PB3, PB2)")
        self.setFixedSize(650, 720)

        # Inversion flags: False = HIGH opens (N-FET), True = LOW opens (P-FET)
        self.inv_pb3 = True  # P-channel MOSFET (0V / LOW turns on)
        self.inv_pb2 = True  # P-channel MOSFET (0V / LOW turns on)

        # Blink timers
        self.blink_timer = QTimer(self)
        self.blink_timer.timeout.connect(self.on_blink_tick)
        self.blink_active_pa0 = False
        self.blink_state = False

        self.last_pa0 = 0
        self.last_pb3 = 1
        self.last_pb2 = 1

        self.worker = SwdWorker()
        self.worker.connection_changed.connect(self.on_connection_changed)
        self.worker.state_updated.connect(self.on_state_updated)
        self.worker.start()

        self.init_ui()

    def init_ui(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #121417;
            }
            QWidget {
                color: #E0E0E0;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QFrame.card {
                background-color: #1C1F26;
                border: 1px solid #2D333B;
                border-radius: 12px;
                padding: 14px;
            }
            QPushButton {
                border-radius: 8px;
                font-weight: bold;
                padding: 10px 14px;
                font-size: 13px;
            }
            QRadioButton {
                font-size: 12px;
                color: #8892B0;
            }
            QRadioButton:checked {
                color: #64B5F6;
                font-weight: bold;
            }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # ─── Status Bar ───
        status_card = QFrame()
        status_card.setProperty("class", "card")
        status_layout = QHBoxLayout(status_card)
        status_layout.setContentsMargins(12, 8, 12, 8)

        self.status_dot = QLabel("●")
        self.status_dot.setFont(QFont("Segoe UI", 16))
        self.status_dot.setStyleSheet("color: #e74c3c;")

        self.status_text = QLabel("Поиск микроконтроллера через SWD...")
        self.status_text.setFont(QFont("Segoe UI", 10))

        status_layout.addWidget(self.status_dot)
        status_layout.addWidget(self.status_text, 1)
        root.addWidget(status_card)

        # ─── Channel 1: On-board Indicator LED (PA0) ───
        ch1_card = QFrame()
        ch1_card.setProperty("class", "card")
        ch1_layout = QVBoxLayout(ch1_card)
        ch1_layout.setSpacing(10)

        ch1_header = QHBoxLayout()
        ch1_title = QLabel("💡 Канал 1: Индикаторный LED платы (PA0 / Пин 13)")
        ch1_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.ch1_badge = QLabel("ВЫКЛ")
        self.ch1_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 4px 10px; border-radius: 6px; font-weight: bold;")
        ch1_header.addWidget(ch1_title)
        ch1_header.addStretch()
        ch1_header.addWidget(self.ch1_badge)
        ch1_layout.addLayout(ch1_header)

        ch1_btns = QHBoxLayout()
        self.btn_pa0_toggle = QPushButton("🔄 Переключить (Toggle)")
        self.btn_pa0_toggle.setStyleSheet("background-color: #2980b9; color: white;")
        self.btn_pa0_toggle.clicked.connect(self.toggle_pa0)

        self.btn_pa0_on = QPushButton("ВКЛ (1)")
        self.btn_pa0_on.setStyleSheet("background-color: #27ae60; color: white;")
        self.btn_pa0_on.clicked.connect(lambda: self.set_pa0(1))

        self.btn_pa0_off = QPushButton("ВЫКЛ (0)")
        self.btn_pa0_off.setStyleSheet("background-color: #c0392b; color: white;")
        self.btn_pa0_off.clicked.connect(lambda: self.set_pa0(0))

        self.btn_pa0_blink = QPushButton("⚡ Мигать")
        self.btn_pa0_blink.setStyleSheet("background-color: #34495e; color: white;")
        self.btn_pa0_blink.clicked.connect(self.toggle_pa0_blink)

        ch1_btns.addWidget(self.btn_pa0_toggle, 2)
        ch1_btns.addWidget(self.btn_pa0_on, 1)
        ch1_btns.addWidget(self.btn_pa0_off, 1)
        ch1_btns.addWidget(self.btn_pa0_blink, 1)
        ch1_layout.addLayout(ch1_btns)
        root.addWidget(ch1_card)

        # ─── Channel 2: Filament 1 (PB3 / Pin 9 -> Coil Pad 1) ───
        ch2_card = QFrame()
        ch2_card.setProperty("class", "card")
        ch2_layout = QVBoxLayout(ch2_card)
        ch2_layout.setSpacing(10)

        ch2_header = QHBoxLayout()
        ch2_title = QLabel("🔥 Канал 2: Филамент 1 (PB3 / Пин 9 -> Coil Pad 1)")
        ch2_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.ch2_badge = QLabel("ВЫКЛ")
        self.ch2_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 4px 10px; border-radius: 6px; font-weight: bold;")
        ch2_header.addWidget(ch2_title)
        ch2_header.addStretch()
        ch2_header.addWidget(self.ch2_badge)
        ch2_layout.addLayout(ch2_header)

        # Polarity selection
        ch2_pol = QHBoxLayout()
        ch2_pol_lbl = QLabel("Логика ключа:")
        ch2_pol_lbl.setStyleSheet("color: #8892B0; font-size: 11px;")
        self.rb_pb3_pfet = QRadioButton("P-FET (LOW/0 = ВКЛ, HIGH/1 = ВЫКЛ)")
        self.rb_pb3_nfet = QRadioButton("Прямая (HIGH/1 = ВКЛ, LOW/0 = ВЫКЛ)")
        self.rb_pb3_pfet.setChecked(True)
        self.rb_pb3_pfet.toggled.connect(lambda c: setattr(self, 'inv_pb3', c))
        ch2_pol.addWidget(ch2_pol_lbl)
        ch2_pol.addWidget(self.rb_pb3_pfet)
        ch2_pol.addWidget(self.rb_pb3_nfet)
        ch2_pol.addStretch()
        ch2_layout.addLayout(ch2_pol)

        ch2_btns = QHBoxLayout()
        self.btn_pb3_toggle = QPushButton("🔥 ВКЛЮЧИТЬ / ВЫКЛЮЧИТЬ ФИЛАМЕНТ 1")
        self.btn_pb3_toggle.setStyleSheet("background-color: #d35400; color: white; font-size: 14px; padding: 12px;")
        self.btn_pb3_toggle.clicked.connect(self.toggle_filament1)

        self.btn_pb3_low = QPushButton("0V (LOW)")
        self.btn_pb3_low.setToolTip("Установить на затворе 0V")
        self.btn_pb3_low.setStyleSheet("background-color: #2c3e50; color: #ecf0f1;")
        self.btn_pb3_low.clicked.connect(lambda: self.set_pb3_direct(0))

        self.btn_pb3_high = QPushButton("3.3V (HIGH)")
        self.btn_pb3_high.setToolTip("Установить на затворе 3.3V")
        self.btn_pb3_high.setStyleSheet("background-color: #2c3e50; color: #ecf0f1;")
        self.btn_pb3_high.clicked.connect(lambda: self.set_pb3_direct(1))

        ch2_btns.addWidget(self.btn_pb3_toggle, 3)
        ch2_btns.addWidget(self.btn_pb3_low, 1)
        ch2_btns.addWidget(self.btn_pb3_high, 1)
        ch2_layout.addLayout(ch2_btns)
        root.addWidget(ch2_card)

        # ─── Channel 3: Filament 2 (PB2 / Pin 10 -> Coil Pad 2) ───
        ch3_card = QFrame()
        ch3_card.setProperty("class", "card")
        ch3_layout = QVBoxLayout(ch3_card)
        ch3_layout.setSpacing(10)

        ch3_header = QHBoxLayout()
        ch3_title = QLabel("🔥 Канал 3: Филамент 2 (PB2 / Пин 10 -> Coil Pad 2)")
        ch3_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.ch3_badge = QLabel("ВЫКЛ")
        self.ch3_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 4px 10px; border-radius: 6px; font-weight: bold;")
        ch3_header.addWidget(ch3_title)
        ch3_header.addStretch()
        ch3_header.addWidget(self.ch3_badge)
        ch3_layout.addLayout(ch3_header)

        # Polarity selection
        ch3_pol = QHBoxLayout()
        ch3_pol_lbl = QLabel("Логика ключа:")
        ch3_pol_lbl.setStyleSheet("color: #8892B0; font-size: 11px;")
        self.rb_pb2_pfet = QRadioButton("P-FET (LOW/0 = ВКЛ, HIGH/1 = ВЫКЛ)")
        self.rb_pb2_nfet = QRadioButton("Прямая (HIGH/1 = ВКЛ, LOW/0 = ВЫКЛ)")
        self.rb_pb2_pfet.setChecked(True)
        self.rb_pb2_pfet.toggled.connect(lambda c: setattr(self, 'inv_pb2', c))
        ch3_pol.addWidget(ch3_pol_lbl)
        ch3_pol.addWidget(self.rb_pb2_pfet)
        ch3_pol.addWidget(self.rb_pb2_nfet)
        ch3_pol.addStretch()
        ch3_layout.addLayout(ch3_pol)

        ch3_btns = QHBoxLayout()
        self.btn_pb2_toggle = QPushButton("🔥 ВКЛЮЧИТЬ / ВЫКЛЮЧИТЬ ФИЛАМЕНТ 2")
        self.btn_pb2_toggle.setStyleSheet("background-color: #d35400; color: white; font-size: 14px; padding: 12px;")
        self.btn_pb2_toggle.clicked.connect(self.toggle_filament2)

        self.btn_pb2_low = QPushButton("0V (LOW)")
        self.btn_pb2_low.setToolTip("Установить на затворе 0V")
        self.btn_pb2_low.setStyleSheet("background-color: #2c3e50; color: #ecf0f1;")
        self.btn_pb2_low.clicked.connect(lambda: self.set_pb2_direct(0))

        self.btn_pb2_high = QPushButton("3.3V (HIGH)")
        self.btn_pb2_high.setToolTip("Установить на затворе 3.3V")
        self.btn_pb2_high.setStyleSheet("background-color: #2c3e50; color: #ecf0f1;")
        self.btn_pb2_high.clicked.connect(lambda: self.set_pb2_direct(1))

        ch3_btns.addWidget(self.btn_pb2_toggle, 3)
        ch3_btns.addWidget(self.btn_pb2_low, 1)
        ch3_btns.addWidget(self.btn_pb2_high, 1)
        ch3_layout.addLayout(ch3_btns)
        root.addWidget(ch3_card)

        # ─── Master Control & Live Registers ───
        master_card = QFrame()
        master_card.setProperty("class", "card")
        master_layout = QVBoxLayout(master_card)

        m_btns = QHBoxLayout()
        self.btn_all_on = QPushButton("🌟 Зажечь ВСЕ 3 канала")
        self.btn_all_on.setStyleSheet("background-color: #27ae60; color: white; padding: 12px;")
        self.btn_all_on.clicked.connect(self.turn_all_on)

        self.btn_all_off = QPushButton("🌑 Погасить ВСЕ каналы")
        self.btn_all_off.setStyleSheet("background-color: #c0392b; color: white; padding: 12px;")
        self.btn_all_off.clicked.connect(self.turn_all_off)

        m_btns.addWidget(self.btn_all_on)
        m_btns.addWidget(self.btn_all_off)
        master_layout.addLayout(m_btns)

        self.reg_label = QLabel("Регистры: GPIOA_ODR: -- | GPIOB_ODR: --")
        self.reg_label.setFont(QFont("Consolas", 10))
        self.reg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.reg_label.setStyleSheet("color: #8892B0; margin-top: 6px;")
        master_layout.addWidget(self.reg_label)

        root.addWidget(master_card)

    def on_connection_changed(self, connected, message):
        if connected:
            self.status_dot.setStyleSheet("color: #2ecc71;")
            self.status_text.setText(message)
        else:
            self.status_dot.setStyleSheet("color: #e74c3c;")
            self.status_text.setText(message)

    def on_state_updated(self, pa0, pb3, pb2, odr_a, odr_b):
        self.last_pa0 = pa0
        self.last_pb3 = pb3
        self.last_pb2 = pb2

        # Channel 1 (PA0, 1 = ON)
        if pa0 == 1:
            self.ch1_badge.setText("СВЕТИТ (HIGH)")
            self.ch1_badge.setStyleSheet("background-color: #27ae60; color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold;")
        else:
            self.ch1_badge.setText("ВЫКЛ (LOW)")
            self.ch1_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 4px 10px; border-radius: 6px; font-weight: bold;")

        # Channel 2 (PB3)
        fil1_active = (pb3 == 0) if self.inv_pb3 else (pb3 == 1)
        pin_level_str = "0V / LOW" if pb3 == 0 else "3.3V / HIGH"
        if fil1_active:
            self.ch2_badge.setText(f"СВЕТИТ ({pin_level_str})")
            self.ch2_badge.setStyleSheet("background-color: #e67e22; color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold;")
        else:
            self.ch2_badge.setText(f"ВЫКЛ ({pin_level_str})")
            self.ch2_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 4px 10px; border-radius: 6px; font-weight: bold;")

        # Channel 3 (PB2)
        fil2_active = (pb2 == 0) if self.inv_pb2 else (pb2 == 1)
        pin2_level_str = "0V / LOW" if pb2 == 0 else "3.3V / HIGH"
        if fil2_active:
            self.ch3_badge.setText(f"СВЕТИТ ({pin2_level_str})")
            self.ch3_badge.setStyleSheet("background-color: #e67e22; color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold;")
        else:
            self.ch3_badge.setText(f"ВЫКЛ ({pin2_level_str})")
            self.ch3_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 4px 10px; border-radius: 6px; font-weight: bold;")

        self.reg_label.setText(
            f"Регистры: GPIOA_ODR: 0x{odr_a:04X} (PA0={pa0}) | GPIOB_ODR: 0x{odr_b:04X} (PB3={pb3}, PB2={pb2})"
        )

    # ─── PA0 Controls ───
    def set_pa0(self, state):
        cmd = (1 << 0) if state else (1 << 16)
        self.worker.queue_command('A', cmd)

    def toggle_pa0(self):
        new_state = 0 if self.last_pa0 == 1 else 1
        self.set_pa0(new_state)

    def toggle_pa0_blink(self):
        self.blink_active_pa0 = not self.blink_active_pa0
        if self.blink_active_pa0:
            self.btn_pa0_blink.setText("⏸ Стоп")
            self.btn_pa0_blink.setStyleSheet("background-color: #e67e22; color: white;")
            self.blink_timer.start(500)
        else:
            self.btn_pa0_blink.setText("⚡ Мигать")
            self.btn_pa0_blink.setStyleSheet("background-color: #34495e; color: white;")
            self.blink_timer.stop()

    def on_blink_tick(self):
        self.blink_state = not self.blink_state
        if self.blink_active_pa0:
            self.set_pa0(1 if self.blink_state else 0)

    # ─── PB3 / Filament 1 Controls ───
    def set_pb3_direct(self, level):
        cmd = (1 << 3) if level else (1 << (3 + 16))
        self.worker.queue_command('B', cmd)

    def toggle_filament1(self):
        is_active = (self.last_pb3 == 0) if self.inv_pb3 else (self.last_pb3 == 1)
        # To turn off: if P-FET set HIGH (1), else set LOW (0)
        # To turn on: if P-FET set LOW (0), else set HIGH (1)
        if is_active:
            new_level = 1 if self.inv_pb3 else 0
        else:
            new_level = 0 if self.inv_pb3 else 1
        self.set_pb3_direct(new_level)

    # ─── PB2 / Filament 2 Controls ───
    def set_pb2_direct(self, level):
        cmd = (1 << 2) if level else (1 << (2 + 16))
        self.worker.queue_command('B', cmd)

    def toggle_filament2(self):
        is_active = (self.last_pb2 == 0) if self.inv_pb2 else (self.last_pb2 == 1)
        if is_active:
            new_level = 1 if self.inv_pb2 else 0
        else:
            new_level = 0 if self.inv_pb2 else 1
        self.set_pb2_direct(new_level)

    # ─── Master All Controls ───
    def turn_all_on(self):
        self.set_pa0(1)
        self.set_pb3_direct(0 if self.inv_pb3 else 1)
        self.set_pb2_direct(0 if self.inv_pb2 else 1)

    def turn_all_off(self):
        self.set_pa0(0)
        self.set_pb3_direct(1 if self.inv_pb3 else 0)
        self.set_pb2_direct(1 if self.inv_pb2 else 0)

    def closeEvent(self, event):
        self.blink_timer.stop()
        self.worker.stop()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
