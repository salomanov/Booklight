import sys
import time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QLabel, QPushButton, QFrame, 
    QSlider, QGridLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
from pyocd.core.helpers import ConnectHelper

# SRAM Shared Control Block (g_lamp at 0x20000000)
LAMP_ADDR_MAGIC    = 0x20000000  # 0x50574D31 ('PWM1')
LAMP_ADDR_DUTY_PA0 = 0x20000004  # 0..100% (Indicator LED)
LAMP_ADDR_DUTY_PB3 = 0x20000008  # 0..100% (Filament 1)
LAMP_ADDR_DUTY_PB2 = 0x2000000C  # 0..100% (Filament 2)
LAMP_ADDR_FLAGS    = 0x20000010

TARGET = 'py32f002bx5'


class SwdWorker(QThread):
    connection_changed = pyqtSignal(bool, str)
    state_updated      = pyqtSignal(int, int, int, int) # duty_pa0, duty_pb3, duty_pb2, magic

    def __init__(self):
        super().__init__()
        self.running = True
        self.command_queue = []

    def set_duty(self, channel, percent):
        """channel: 'PA0', 'PB3', 'PB2'"""
        self.command_queue.append((channel, percent))

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
                    self.connection_changed.emit(True, "J-Link STLink: Подключено (SWD активен, ШИМ работает)")

                # Execute pending write commands
                while self.command_queue:
                    ch, val = self.command_queue.pop(0)
                    val = max(0, min(100, int(val)))
                    if ch == 'PA0':
                        target.write32(LAMP_ADDR_DUTY_PA0, val)
                    elif ch == 'PB3':
                        target.write32(LAMP_ADDR_DUTY_PB3, val)
                    elif ch == 'PB2':
                        target.write32(LAMP_ADDR_DUTY_PB2, val)

                # Read current hardware duty cycles
                magic = target.read32(LAMP_ADDR_MAGIC)
                d_pa0 = target.read32(LAMP_ADDR_DUTY_PA0)
                d_pb3 = target.read32(LAMP_ADDR_DUTY_PB3)
                d_pb2 = target.read32(LAMP_ADDR_DUTY_PB2)

                self.state_updated.emit(d_pa0, d_pb3, d_pb2, magic)
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
        self.setWindowTitle("BookLight — Пульт управления ШИМ всех каналов (PA0, PB3, PB2)")
        self.setFixedSize(700, 840)

        self.last_d_pa0 = 50
        self.last_d_pb3 = 0
        self.last_d_pb2 = 0

        # Memory for toggle return brightness
        self.mem_pb3 = 70
        self.mem_pb2 = 70
        self.mem_pa0 = 50

        # Breathing effect timer
        self.breathe_timer = QTimer(self)
        self.breathe_timer.timeout.connect(self.on_breathe_tick)
        self.breathe_active = False
        self.breathe_val = 0
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
                padding: 8px 12px;
                font-size: 13px;
            }
            QSlider::groove:horizontal {
                height: 8px;
                background: #2D333B;
                border-radius: 4px;
            }
            QSlider::sub-page:horizontal {
                background: #e67e22;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 2px solid #d35400;
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

        # ─── Channel 2: Filament 1 (PB3 / Coil Pad 1) ───
        ch2_card = QFrame()
        ch2_card.setProperty("class", "card")
        ch2_layout = QVBoxLayout(ch2_card)
        ch2_layout.setSpacing(10)

        ch2_header = QHBoxLayout()
        ch2_title = QLabel("🔥 Филамент 1 (PB3 / Пин 9 -> Coil Pad 1)")
        ch2_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.ch2_badge = QLabel("ВЫКЛ (0%)")
        self.ch2_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 4px 10px; border-radius: 6px; font-weight: bold;")
        ch2_header.addWidget(ch2_title)
        ch2_header.addStretch()
        ch2_header.addWidget(self.ch2_badge)
        ch2_layout.addLayout(ch2_header)

        # Slider Row
        s2_row = QHBoxLayout()
        self.lbl_val_pb3 = QLabel("0%")
        self.lbl_val_pb3.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.lbl_val_pb3.setFixedWidth(55)
        self.lbl_val_pb3.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_val_pb3.setStyleSheet("color: #e67e22;")

        self.slider_pb3 = QSlider(Qt.Orientation.Horizontal)
        self.slider_pb3.setRange(0, 100)
        self.slider_pb3.setValue(0)
        self.slider_pb3.valueChanged.connect(lambda v: self.on_slider_filament('PB3', v, self.lbl_val_pb3))

        self.btn_toggle_pb3 = QPushButton("🔄 ВКЛ/ВЫКЛ")
        self.btn_toggle_pb3.setStyleSheet("background-color: #34495e; color: white; padding: 6px 12px;")
        self.btn_toggle_pb3.clicked.connect(self.toggle_pb3)

        s2_row.addWidget(self.slider_pb3, 1)
        s2_row.addWidget(self.lbl_val_pb3)
        s2_row.addWidget(self.btn_toggle_pb3)
        ch2_layout.addLayout(s2_row)

        # Presets Row
        p2_row = QHBoxLayout()
        p2_row.setSpacing(8)
        for pct in [0, 15, 30, 50, 75, 100]:
            btn = QPushButton(f"{pct}%" if pct > 0 else "0% (ВЫКЛ)")
            btn.setStyleSheet("background-color: #242933; color: #E0E0E0; padding: 5px 8px; font-size: 11px;")
            btn.clicked.connect(lambda _, p=pct: self.slider_pb3.setValue(p))
            p2_row.addWidget(btn)
        ch2_layout.addLayout(p2_row)
        root.addWidget(ch2_card)

        # ─── Channel 3: Filament 2 (PB2 / Coil Pad 2) ───
        ch3_card = QFrame()
        ch3_card.setProperty("class", "card")
        ch3_layout = QVBoxLayout(ch3_card)
        ch3_layout.setSpacing(10)

        ch3_header = QHBoxLayout()
        ch3_title = QLabel("🔥 Филамент 2 (PB2 / Пин 10 -> Coil Pad 2)")
        ch3_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.ch3_badge = QLabel("ВЫКЛ (0%)")
        self.ch3_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 4px 10px; border-radius: 6px; font-weight: bold;")
        ch3_header.addWidget(ch3_title)
        ch3_header.addStretch()
        ch3_header.addWidget(self.ch3_badge)
        ch3_layout.addLayout(ch3_header)

        # Slider Row
        s3_row = QHBoxLayout()
        self.lbl_val_pb2 = QLabel("0%")
        self.lbl_val_pb2.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.lbl_val_pb2.setFixedWidth(55)
        self.lbl_val_pb2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_val_pb2.setStyleSheet("color: #e67e22;")

        self.slider_pb2 = QSlider(Qt.Orientation.Horizontal)
        self.slider_pb2.setRange(0, 100)
        self.slider_pb2.setValue(0)
        self.slider_pb2.valueChanged.connect(lambda v: self.on_slider_filament('PB2', v, self.lbl_val_pb2))

        self.btn_toggle_pb2 = QPushButton("🔄 ВКЛ/ВЫКЛ")
        self.btn_toggle_pb2.setStyleSheet("background-color: #34495e; color: white; padding: 6px 12px;")
        self.btn_toggle_pb2.clicked.connect(self.toggle_pb2)

        s3_row.addWidget(self.slider_pb2, 1)
        s3_row.addWidget(self.lbl_val_pb2)
        s3_row.addWidget(self.btn_toggle_pb2)
        ch3_layout.addLayout(s3_row)

        # Presets Row
        p3_row = QHBoxLayout()
        p3_row.setSpacing(8)
        for pct in [0, 15, 30, 50, 75, 100]:
            btn = QPushButton(f"{pct}%" if pct > 0 else "0% (ВЫКЛ)")
            btn.setStyleSheet("background-color: #242933; color: #E0E0E0; padding: 5px 8px; font-size: 11px;")
            btn.clicked.connect(lambda _, p=pct: self.slider_pb2.setValue(p))
            p3_row.addWidget(btn)
        ch3_layout.addLayout(p3_row)
        root.addWidget(ch3_card)

        # ─── Channel 1: On-Board Indicator LED (PA0) ───
        ch1_card = QFrame()
        ch1_card.setProperty("class", "card")
        ch1_layout = QVBoxLayout(ch1_card)
        ch1_layout.setSpacing(8)

        ch1_header = QHBoxLayout()
        ch1_title = QLabel("💡 Индикаторный LED платы (PA0 / TIM1_CH1 1 кГц)")
        ch1_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.ch1_badge = QLabel("50%")
        self.ch1_badge.setStyleSheet("background-color: #27ae60; color: white; padding: 3px 8px; border-radius: 5px; font-size: 11px;")
        ch1_header.addWidget(ch1_title)
        ch1_header.addStretch()
        ch1_header.addWidget(self.ch1_badge)
        ch1_layout.addLayout(ch1_header)

        s1_row = QHBoxLayout()
        self.slider_pa0 = QSlider(Qt.Orientation.Horizontal)
        self.slider_pa0.setStyleSheet("QSlider::sub-page:horizontal { background: #2ecc71; } QSlider::handle:horizontal { border: 2px solid #27ae60; }")
        self.slider_pa0.setRange(0, 100)
        self.slider_pa0.setValue(50)
        self.slider_pa0.valueChanged.connect(self.on_slider_pa0)

        self.btn_toggle_pa0 = QPushButton("ВКЛ/ВЫКЛ")
        self.btn_toggle_pa0.setStyleSheet("background-color: #2c3e50; color: white; padding: 4px 10px; font-size: 11px;")
        self.btn_toggle_pa0.clicked.connect(self.toggle_pa0)

        s1_row.addWidget(self.slider_pa0, 1)
        s1_row.addWidget(self.btn_toggle_pa0)
        ch1_layout.addLayout(s1_row)
        root.addWidget(ch1_card)

        # ─── Master Control (Both Filaments) ───
        master_card = QFrame()
        master_card.setProperty("class", "card")
        master_layout = QVBoxLayout(master_card)
        master_layout.setSpacing(10)

        m_title = QLabel("🌟 Мастер-управление (Оба филамента синхронно)")
        m_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        master_layout.addWidget(m_title)

        # Master Slider
        ms_row = QHBoxLayout()
        ms_lbl = QLabel("Общая яркость:")
        ms_lbl.setStyleSheet("color: #8892B0; font-size: 12px;")
        self.master_slider = QSlider(Qt.Orientation.Horizontal)
        self.master_slider.setRange(0, 100)
        self.master_slider.setValue(0)
        self.master_slider.valueChanged.connect(self.on_master_slider)

        ms_row.addWidget(ms_lbl)
        ms_row.addWidget(self.master_slider, 1)
        master_layout.addLayout(ms_row)

        m_btns = QHBoxLayout()
        self.btn_all_on = QPushButton("🌟 Зажечь ВСЁ (100%)")
        self.btn_all_on.setStyleSheet("background-color: #27ae60; color: white; padding: 10px;")
        self.btn_all_on.clicked.connect(self.turn_all_on)

        self.btn_all_off = QPushButton("🌑 Погасить ВСЁ")
        self.btn_all_off.setStyleSheet("background-color: #c0392b; color: white; padding: 10px;")
        self.btn_all_off.clicked.connect(self.turn_all_off)

        self.btn_breathe = QPushButton("🌊 Эффект дыхания")
        self.btn_breathe.setStyleSheet("background-color: #2980b9; color: white; padding: 10px;")
        self.btn_breathe.clicked.connect(self.toggle_breathe)

        m_btns.addWidget(self.btn_all_on)
        m_btns.addWidget(self.btn_all_off)
        m_btns.addWidget(self.btn_breathe)
        master_layout.addLayout(m_btns)

        self.reg_label = QLabel("ШИМ: Филамент 1: 0% | Филамент 2: 0% | Индикатор: 50% | Частота: 500 Гц")
        self.reg_label.setFont(QFont("Consolas", 10))
        self.reg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.reg_label.setStyleSheet("color: #8892B0; margin-top: 4px;")
        master_layout.addWidget(self.reg_label)

        root.addWidget(master_card)

    def on_connection_changed(self, connected, message):
        if connected:
            self.status_dot.setStyleSheet("color: #2ecc71;")
            self.status_text.setText(message)
        else:
            self.status_dot.setStyleSheet("color: #e74c3c;")
            self.status_text.setText(message)

    def on_slider_filament(self, ch, value, label_widget):
        label_widget.setText(f"{value}%")
        self.worker.set_duty(ch, value)

    def on_slider_pa0(self, value):
        self.worker.set_duty('PA0', value)

    def on_master_slider(self, value):
        self.slider_pb3.setValue(value)
        self.slider_pb2.setValue(value)

    def toggle_pb3(self):
        cur = self.slider_pb3.value()
        if cur > 0:
            self.mem_pb3 = cur
            self.slider_pb3.setValue(0)
        else:
            self.slider_pb3.setValue(self.mem_pb3 if self.mem_pb3 > 0 else 70)

    def toggle_pb2(self):
        cur = self.slider_pb2.value()
        if cur > 0:
            self.mem_pb2 = cur
            self.slider_pb2.setValue(0)
        else:
            self.slider_pb2.setValue(self.mem_pb2 if self.mem_pb2 > 0 else 70)

    def toggle_pa0(self):
        cur = self.slider_pa0.value()
        if cur > 0:
            self.mem_pa0 = cur
            self.slider_pa0.setValue(0)
        else:
            self.slider_pa0.setValue(self.mem_pa0 if self.mem_pa0 > 0 else 50)

    def toggle_breathe(self):
        self.breathe_active = not self.breathe_active
        if self.breathe_active:
            self.btn_breathe.setText("⏸ Стоп дыхание")
            self.btn_breathe.setStyleSheet("background-color: #e67e22; color: white; padding: 10px;")
            self.breathe_timer.start(30)
        else:
            self.btn_breathe.setText("🌊 Эффект дыхания")
            self.btn_breathe.setStyleSheet("background-color: #2980b9; color: white; padding: 10px;")
            self.breathe_timer.stop()

    def on_breathe_tick(self):
        self.breathe_val += self.breathe_dir
        if self.breathe_val >= 100:
            self.breathe_val = 100
            self.breathe_dir = -2
        elif self.breathe_val <= 0:
            self.breathe_val = 0
            self.breathe_dir = 2
        self.master_slider.setValue(self.breathe_val)

    def on_state_updated(self, d_pa0, d_pb3, d_pb2, magic):
        self.last_d_pa0 = d_pa0
        self.last_d_pb3 = d_pb3
        self.last_d_pb2 = d_pb2

        # Badge PB3
        if d_pb3 == 0:
            self.ch2_badge.setText("ВЫКЛ (0%)")
            self.ch2_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 4px 10px; border-radius: 6px; font-weight: bold;")
        else:
            self.ch2_badge.setText(f"ШИМ {d_pb3}%")
            self.ch2_badge.setStyleSheet("background-color: #e67e22; color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold;")

        # Badge PB2
        if d_pb2 == 0:
            self.ch3_badge.setText("ВЫКЛ (0%)")
            self.ch3_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 4px 10px; border-radius: 6px; font-weight: bold;")
        else:
            self.ch3_badge.setText(f"ШИМ {d_pb2}%")
            self.ch3_badge.setStyleSheet("background-color: #e67e22; color: white; padding: 4px 10px; border-radius: 6px; font-weight: bold;")

        # Badge PA0
        self.ch1_badge.setText(f"{d_pa0}%")

        self.reg_label.setText(
            f"ШИМ: Филамент 1: {d_pb3}% | Филамент 2: {d_pb2}% | Индикатор: {d_pa0}% | Частота: 500 Гц"
        )

    def turn_all_on(self):
        self.master_slider.setValue(100)
        self.slider_pa0.setValue(100)

    def turn_all_off(self):
        self.master_slider.setValue(0)
        self.slider_pa0.setValue(0)

    def closeEvent(self, event):
        self.breathe_timer.stop()
        self.worker.stop()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
