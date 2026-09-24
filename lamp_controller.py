import sys
import time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QLabel, QPushButton, QFrame, QRadioButton, 
    QSlider, QGridLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
from pyocd.core.helpers import ConnectHelper

# Hardware Register Addresses for PUYA PY32F002B
RCC_BASE    = 0x40021000
RCC_IOPENR  = RCC_BASE + 0x34
RCC_APBENR2 = RCC_BASE + 0x3C

GPIOA_BASE  = 0x50000000
GPIOA_MODER = GPIOA_BASE + 0x00
GPIOA_AFR0  = GPIOA_BASE + 0x20
GPIOA_ODR   = GPIOA_BASE + 0x14
GPIOA_BSRR  = GPIOA_BASE + 0x18

GPIOB_BASE  = 0x50000400
GPIOB_MODER = GPIOB_BASE + 0x00
GPIOB_ODR   = GPIOB_BASE + 0x14
GPIOB_BSRR  = GPIOB_BASE + 0x18

# TIM1 (Advanced-control Timer)
TIM1_BASE   = 0x40012C00
TIM1_CR1    = TIM1_BASE + 0x00
TIM1_PSC    = TIM1_BASE + 0x28
TIM1_ARR    = TIM1_BASE + 0x2C
TIM1_CCR1   = TIM1_BASE + 0x34
TIM1_BDTR   = TIM1_BASE + 0x44

TARGET = 'py32f002bx5'


class SwdWorker(QThread):
    connection_changed = pyqtSignal(bool, str)
    state_updated      = pyqtSignal(int, int, int, int, int, int) # ccr1, pb3, pb2, odr_a, odr_b, tim1_cr1

    def __init__(self):
        super().__init__()
        self.running = True
        self.command_queue = []

    def queue_command(self, cmd_type, val):
        self.command_queue.append((cmd_type, val))

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
                    connected = True
                    self.connection_changed.emit(True, "J-Link STLink: Подключено (SWD 24/7 активен)")

                # Execute pending write commands
                while self.command_queue:
                    cmd_type, val = self.command_queue.pop(0)
                    if cmd_type == 'CCR1':
                        target.write32(TIM1_CCR1, val)
                    elif cmd_type == 'B':
                        target.write32(GPIOB_BSRR, val)
                    elif cmd_type == 'A':
                        target.write32(GPIOA_BSRR, val)

                # Read hardware states
                ccr1 = target.read32(TIM1_CCR1)
                cr1  = target.read32(TIM1_CR1)
                odr_a = target.read32(GPIOA_ODR)
                odr_b = target.read32(GPIOB_ODR)

                pb3 = (odr_b >> 3) & 1
                pb2 = (odr_b >> 2) & 1

                self.state_updated.emit(ccr1, pb3, pb2, odr_a, odr_b, cr1)
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
        self.setWindowTitle("BookLight — Пульт управления: Аппаратный ШИМ TIM1 + 3 канала")
        self.setFixedSize(680, 780)

        # Inversion flags: True = LOW opens (P-FET), False = HIGH opens (N-FET)
        self.inv_pb3 = True
        self.inv_pb2 = True

        self.last_ccr1 = 500
        self.last_pb3 = 1
        self.last_pb2 = 1

        # Breathing effect timer
        self.breathe_timer = QTimer(self)
        self.breathe_timer.timeout.connect(self.on_breathe_tick)
        self.breathe_active = False
        self.breathe_val = 50
        self.breathe_dir = 2

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
            QSlider::groove:horizontal {
                height: 8px;
                background: #2D333B;
                border-radius: 4px;
            }
            QSlider::sub-page:horizontal {
                background: #2ecc71;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 2px solid #27ae60;
                width: 22px;
                margin-top: -7px;
                margin-bottom: -7px;
                border-radius: 11px;
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

        # ─── Channel 1: Hardware PWM TIM1_CH1 (PA0) ───
        ch1_card = QFrame()
        ch1_card.setProperty("class", "card")
        ch1_layout = QVBoxLayout(ch1_card)
        ch1_layout.setSpacing(10)

        ch1_header = QHBoxLayout()
        ch1_title = QLabel("💡 Канал 1: Аппаратный ШИМ TIM1_CH1 (PA0 / Пин 13)")
        ch1_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.ch1_badge = QLabel("ШИМ: 50%")
        self.ch1_badge.setStyleSheet("background-color: #27ae60; color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold;")
        ch1_header.addWidget(ch1_title)
        ch1_header.addStretch()
        ch1_header.addWidget(self.ch1_badge)
        ch1_layout.addLayout(ch1_header)

        # Slider and Brightness Readout
        slider_row = QHBoxLayout()
        self.slider_label = QLabel("50%")
        self.slider_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.slider_label.setFixedWidth(55)
        self.slider_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.slider_label.setStyleSheet("color: #2ecc71;")

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(0, 100)
        self.slider.setValue(50)
        self.slider.valueChanged.connect(self.on_slider_changed)

        slider_row.addWidget(self.slider, 1)
        slider_row.addWidget(self.slider_label)
        ch1_layout.addLayout(slider_row)

        # Presets Buttons Row
        preset_row = QHBoxLayout()
        preset_row.setSpacing(8)
        for pct in [0, 10, 25, 50, 75, 100]:
            btn = QPushButton(f"{pct}%" if pct > 0 else "0% (ВЫКЛ)")
            btn.setStyleSheet("background-color: #242933; color: #E0E0E0; padding: 6px 10px; font-size: 11px;")
            btn.clicked.connect(lambda _, p=pct: self.slider.setValue(p))
            preset_row.addWidget(btn)

        self.btn_breathe = QPushButton("🌊 Эффект дыхания")
        self.btn_breathe.setStyleSheet("background-color: #2980b9; color: white; padding: 6px 12px; font-size: 11px;")
        self.btn_breathe.clicked.connect(self.toggle_breathe)
        preset_row.addWidget(self.btn_breathe)

        ch1_layout.addLayout(preset_row)
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
        self.btn_pb3_low.setStyleSheet("background-color: #2c3e50; color: #ecf0f1;")
        self.btn_pb3_low.clicked.connect(lambda: self.set_pb3_direct(0))

        self.btn_pb3_high = QPushButton("3.3V (HIGH)")
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
        self.btn_pb2_low.setStyleSheet("background-color: #2c3e50; color: #ecf0f1;")
        self.btn_pb2_low.clicked.connect(lambda: self.set_pb2_direct(0))

        self.btn_pb2_high = QPushButton("3.3V (HIGH)")
        self.btn_pb2_high.setStyleSheet("background-color: #2c3e50; color: #ecf0f1;")
        self.btn_pb2_high.clicked.connect(lambda: self.set_pb2_direct(1))

        ch3_btns.addWidget(self.btn_pb2_toggle, 3)
        ch3_btns.addWidget(self.btn_pb2_low, 1)
        ch3_btns.addWidget(self.btn_pb2_high, 1)
        ch3_layout.addLayout(ch3_btns)
        root.addWidget(ch3_card)

        # ─── Master Control & Live Hardware Readouts ───
        master_card = QFrame()
        master_card.setProperty("class", "card")
        master_layout = QVBoxLayout(master_card)

        m_btns = QHBoxLayout()
        self.btn_all_on = QPushButton("🌟 Зажечь ВСЕ каналы")
        self.btn_all_on.setStyleSheet("background-color: #27ae60; color: white; padding: 12px;")
        self.btn_all_on.clicked.connect(self.turn_all_on)

        self.btn_all_off = QPushButton("🌑 Погасить ВСЕ каналы")
        self.btn_all_off.setStyleSheet("background-color: #c0392b; color: white; padding: 12px;")
        self.btn_all_off.clicked.connect(self.turn_all_off)

        m_btns.addWidget(self.btn_all_on)
        m_btns.addWidget(self.btn_all_off)
        master_layout.addLayout(m_btns)

        self.reg_label = QLabel("Аппаратный таймер: TIM1_CCR1: 500 / 1000 | Частота: 1.0 кГц | GPIOB_ODR: --")
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

    def on_slider_changed(self, value):
        self.slider_label.setText(f"{value}%")
        ccr1_val = int(value * 10)  # 0..1000
        self.worker.queue_command('CCR1', ccr1_val)

    def toggle_breathe(self):
        self.breathe_active = not self.breathe_active
        if self.breathe_active:
            self.btn_breathe.setText("⏸ Стоп дыхание")
            self.btn_breathe.setStyleSheet("background-color: #e67e22; color: white; padding: 6px 12px; font-size: 11px;")
            self.breathe_timer.start(30)
        else:
            self.btn_breathe.setText("🌊 Эффект дыхания")
            self.btn_breathe.setStyleSheet("background-color: #2980b9; color: white; padding: 6px 12px; font-size: 11px;")
            self.breathe_timer.stop()

    def on_breathe_tick(self):
        self.breathe_val += self.breathe_dir
        if self.breathe_val >= 100:
            self.breathe_val = 100
            self.breathe_dir = -2
        elif self.breathe_val <= 0:
            self.breathe_val = 0
            self.breathe_dir = 2
        self.slider.setValue(self.breathe_val)

    def on_state_updated(self, ccr1, pb3, pb2, odr_a, odr_b, tim1_cr1):
        self.last_ccr1 = ccr1
        self.last_pb3 = pb3
        self.last_pb2 = pb2

        pct = int(ccr1 / 10)
        if pct == 0:
            self.ch1_badge.setText("ВЫКЛ (0%)")
            self.ch1_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 4px 10px; border-radius: 6px; font-weight: bold;")
        else:
            self.ch1_badge.setText(f"ШИМ {pct}% (1 кГц)")
            self.ch1_badge.setStyleSheet("background-color: #27ae60; color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold;")

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
            f"Аппаратный таймер: TIM1_CCR1={ccr1}/1000 ({pct}%) | GPIOB_ODR: 0x{odr_b:04X} (PB3={pb3}, PB2={pb2})"
        )

    # ─── PB3 / Filament 1 Controls ───
    def set_pb3_direct(self, level):
        cmd = (1 << 3) if level else (1 << (3 + 16))
        self.worker.queue_command('B', cmd)

    def toggle_filament1(self):
        is_active = (self.last_pb3 == 0) if self.inv_pb3 else (self.last_pb3 == 1)
        new_level = (1 if is_active else 0) if self.inv_pb3 else (0 if is_active else 1)
        self.set_pb3_direct(new_level)

    # ─── PB2 / Filament 2 Controls ───
    def set_pb2_direct(self, level):
        cmd = (1 << 2) if level else (1 << (2 + 16))
        self.worker.queue_command('B', cmd)

    def toggle_filament2(self):
        is_active = (self.last_pb2 == 0) if self.inv_pb2 else (self.last_pb2 == 1)
        new_level = (1 if is_active else 0) if self.inv_pb2 else (0 if is_active else 1)
        self.set_pb2_direct(new_level)

    # ─── Master All Controls ───
    def turn_all_on(self):
        self.slider.setValue(100)
        self.set_pb3_direct(0 if self.inv_pb3 else 1)
        self.set_pb2_direct(0 if self.inv_pb2 else 1)

    def turn_all_off(self):
        self.slider.setValue(0)
        self.set_pb3_direct(1 if self.inv_pb3 else 0)
        self.set_pb2_direct(1 if self.inv_pb2 else 0)

    def closeEvent(self, event):
        self.breathe_timer.stop()
        self.worker.stop()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
