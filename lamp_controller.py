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

# Hardware Register Addresses for PUYA PY32F002B
TIM1_BASE  = 0x40012C00
TIM1_CR1   = TIM1_BASE + 0x00
TIM1_ARR   = TIM1_BASE + 0x2C
TIM1_CCR1  = TIM1_BASE + 0x34  # Channel 1: PA0 (Indicator LED)
TIM1_CCR3  = TIM1_BASE + 0x3C  # Channel 3: PB2 (All 4 Filaments)

TARGET = 'py32f002bx5'


class SwdWorker(QThread):
    connection_changed = pyqtSignal(bool, str)
    state_updated      = pyqtSignal(int, int) # ccr3 (filaments), ccr1 (indicator)

    def __init__(self):
        super().__init__()
        self.running = True
        self.command_queue = []

    def set_filaments_duty(self, val_1000):
        self.command_queue.append(('CCR3', val_1000))

    def set_indicator_duty(self, val_1000):
        self.command_queue.append(('CCR1', val_1000))

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
                    self.connection_changed.emit(True, "J-Link STLink: Подключено (100% Аппаратный ШИМ 1.0 кГц, 0% CPU)")

                # Execute pending write commands directly to hardware timer registers
                while self.command_queue:
                    reg, val = self.command_queue.pop(0)
                    val = max(0, min(1000, int(val)))
                    if reg == 'CCR3':
                        target.write32(TIM1_CCR3, val)
                    elif reg == 'CCR1':
                        target.write32(TIM1_CCR1, val)

                # Read hardware timer registers
                ccr3 = target.read32(TIM1_CCR3)
                ccr1 = target.read32(TIM1_CCR1)

                self.state_updated.emit(ccr3, ccr1)
                self.msleep(60)

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
        self.setWindowTitle("BookLight — Аппаратный ШИМ TIM1_CH3 (Все 4 филамента)")
        self.setFixedSize(680, 640)

        self.last_ccr3 = 0
        self.last_ccr1 = 500
        self.mem_filaments = 50

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
                padding: 16px;
            }
            QPushButton {
                border-radius: 8px;
                font-weight: bold;
                padding: 10px 14px;
                font-size: 13px;
            }
            QSlider::groove:horizontal {
                height: 10px;
                background: #2D333B;
                border-radius: 5px;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d35400, stop:1 #f39c12);
                border-radius: 5px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 3px solid #e67e22;
                width: 24px;
                margin-top: -7px;
                margin-bottom: -7px;
                border-radius: 12px;
            }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(14)

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

        # ─── Main Card: All 4 Filaments Hardware PWM (TIM1_CH3 on PB2) ───
        fil_card = QFrame()
        fil_card.setProperty("class", "card")
        fil_layout = QVBoxLayout(fil_card)
        fil_layout.setSpacing(14)

        fil_header = QHBoxLayout()
        fil_title = QLabel("🔥 ВСЕ 4 ФИЛАМЕНТА (Аппаратный ШИМ TIM1_CH3 / PB2)")
        fil_title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        fil_title.setStyleSheet("color: #f39c12;")
        self.fil_badge = QLabel("ВЫКЛ (0%)")
        self.fil_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 4px 12px; border-radius: 6px; font-weight: bold;")
        fil_header.addWidget(fil_title)
        fil_header.addStretch()
        fil_header.addWidget(self.fil_badge)
        fil_layout.addLayout(fil_header)

        fil_desc = QLabel("Пятак Coil Pad 2 (Силовой ключ CJ3415 P-FET, до 4.0А). Частота 1.0 кГц, 1000 градаций, 0% CPU.")
        fil_desc.setStyleSheet("color: #8892B0; font-size: 11px;")
        fil_layout.addWidget(fil_desc)

        # Slider Row
        slider_row = QHBoxLayout()
        self.slider_fil = QSlider(Qt.Orientation.Horizontal)
        self.slider_fil.setRange(0, 100)
        self.slider_fil.setValue(0)
        self.slider_fil.valueChanged.connect(self.on_slider_filaments_changed)

        self.lbl_fil_val = QLabel("0%")
        self.lbl_fil_val.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.lbl_fil_val.setFixedWidth(70)
        self.lbl_fil_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_fil_val.setStyleSheet("color: #f39c12;")

        self.btn_fil_toggle = QPushButton("🔄 ВКЛ/ВЫКЛ")
        self.btn_fil_toggle.setStyleSheet("background-color: #d35400; color: white; padding: 10px 16px;")
        self.btn_fil_toggle.clicked.connect(self.toggle_filaments)

        slider_row.addWidget(self.slider_fil, 1)
        slider_row.addWidget(self.lbl_fil_val)
        slider_row.addWidget(self.btn_fil_toggle)
        fil_layout.addLayout(slider_row)

        # Presets Buttons Row
        preset_row = QHBoxLayout()
        preset_row.setSpacing(8)
        for pct in [0, 10, 25, 50, 75, 100]:
            label = "🌑 0% (ВЫКЛ)" if pct == 0 else f"{pct}%"
            if pct == 100: label = "🌟 100% (МАКС)"
            btn = QPushButton(label)
            btn.setStyleSheet("background-color: #242933; color: #E0E0E0; padding: 8px 10px; font-size: 12px;")
            btn.clicked.connect(lambda _, p=pct: self.slider_fil.setValue(p))
            preset_row.addWidget(btn)

        self.btn_breathe = QPushButton("🌊 Дыхание")
        self.btn_breathe.setStyleSheet("background-color: #2980b9; color: white; padding: 8px 12px; font-size: 12px;")
        self.btn_breathe.clicked.connect(self.toggle_breathe)
        preset_row.addWidget(self.btn_breathe)

        fil_layout.addLayout(preset_row)
        root.addWidget(fil_card)

        # ─── Indicator LED Card (PA0 / TIM1_CH1) ───
        ind_card = QFrame()
        ind_card.setProperty("class", "card")
        ind_layout = QVBoxLayout(ind_card)
        ind_layout.setSpacing(10)

        ind_header = QHBoxLayout()
        ind_title = QLabel("💡 Индикаторный LED платы (PA0 / TIM1_CH1 1 кГц)")
        ind_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.ind_badge = QLabel("50%")
        self.ind_badge.setStyleSheet("background-color: #27ae60; color: white; padding: 3px 8px; border-radius: 5px; font-size: 11px;")
        ind_header.addWidget(ind_title)
        ind_header.addStretch()
        ind_header.addWidget(self.ind_badge)
        ind_layout.addLayout(ind_header)

        ind_row = QHBoxLayout()
        self.slider_ind = QSlider(Qt.Orientation.Horizontal)
        self.slider_ind.setStyleSheet("QSlider::sub-page:horizontal { background: #2ecc71; } QSlider::handle:horizontal { border: 2px solid #27ae60; }")
        self.slider_ind.setRange(0, 100)
        self.slider_ind.setValue(50)
        self.slider_ind.valueChanged.connect(self.on_slider_ind_changed)

        self.lbl_ind_val = QLabel("50%")
        self.lbl_ind_val.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.lbl_ind_val.setFixedWidth(45)
        self.lbl_ind_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_ind_val.setStyleSheet("color: #2ecc71;")

        ind_row.addWidget(self.slider_ind, 1)
        ind_row.addWidget(self.lbl_ind_val)
        ind_layout.addLayout(ind_row)
        root.addWidget(ind_card)

        # ─── Telemetry Bar ───
        telem_card = QFrame()
        telem_card.setProperty("class", "card")
        telem_layout = QVBoxLayout(telem_card)
        self.reg_label = QLabel("Аппаратный таймер: TIM1->CCR3 = 0/1000 (Филаменты) | TIM1->CCR1 = 500/1000 (Индикатор) | 1.0 кГц")
        self.reg_label.setFont(QFont("Consolas", 10))
        self.reg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.reg_label.setStyleSheet("color: #8892B0;")
        telem_layout.addWidget(self.reg_label)
        root.addWidget(telem_card)

    def on_connection_changed(self, connected, message):
        if connected:
            self.status_dot.setStyleSheet("color: #2ecc71;")
            self.status_text.setText(message)
        else:
            self.status_dot.setStyleSheet("color: #e74c3c;")
            self.status_text.setText(message)

    def on_slider_filaments_changed(self, value):
        self.lbl_fil_val.setText(f"{value}%")
        ccr3_val = int(value * 10)  # 0..1000
        self.worker.set_filaments_duty(ccr3_val)

    def on_slider_ind_changed(self, value):
        self.lbl_ind_val.setText(f"{value}%")
        ccr1_val = int(value * 10)
        self.worker.set_indicator_duty(ccr1_val)

    def toggle_filaments(self):
        cur = self.slider_fil.value()
        if cur > 0:
            self.mem_filaments = cur
            self.slider_fil.setValue(0)
        else:
            self.slider_fil.setValue(self.mem_filaments if self.mem_filaments > 0 else 50)

    def toggle_breathe(self):
        self.breathe_active = not self.breathe_active
        if self.breathe_active:
            self.btn_breathe.setText("⏸ Стоп")
            self.btn_breathe.setStyleSheet("background-color: #e67e22; color: white; padding: 8px 12px; font-size: 12px;")
            self.breathe_timer.start(25)
        else:
            self.btn_breathe.setText("🌊 Дыхание")
            self.btn_breathe.setStyleSheet("background-color: #2980b9; color: white; padding: 8px 12px; font-size: 12px;")
            self.breathe_timer.stop()

    def on_breathe_tick(self):
        self.breathe_val += self.breathe_dir
        if self.breathe_val >= 100:
            self.breathe_val = 100
            self.breathe_dir = -2
        elif self.breathe_val <= 0:
            self.breathe_val = 0
            self.breathe_dir = 2
        self.slider_fil.setValue(self.breathe_val)

    def on_state_updated(self, ccr3, ccr1):
        self.last_ccr3 = ccr3
        self.last_ccr1 = ccr1

        pct_fil = int(ccr3 / 10)
        pct_ind = int(ccr1 / 10)

        if pct_fil == 0:
            self.fil_badge.setText("ВЫКЛ (0%)")
            self.fil_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 4px 12px; border-radius: 6px; font-weight: bold;")
        else:
            self.fil_badge.setText(f"ШИМ {pct_fil}% (1 кГц)")
            self.fil_badge.setStyleSheet("background-color: #d35400; color: white; padding: 4px 12px; border-radius: 6px; font-weight: bold;")

        self.ind_badge.setText(f"{pct_ind}%")

        self.reg_label.setText(
            f"Аппаратный таймер: TIM1->CCR3 = {ccr3}/1000 ({pct_fil}%) | TIM1->CCR1 = {ccr1}/1000 ({pct_ind}%) | Частота 1.0 кГц | 0% CPU"
        )

    def closeEvent(self, event):
        self.breathe_timer.stop()
        self.worker.stop()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
