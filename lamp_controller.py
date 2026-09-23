import sys
import time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QLabel, QPushButton, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
from pyocd.core.helpers import ConnectHelper

# Hardware Register Addresses for PUYA PY32F002B
GPIOA_BASE = 0x50000000
GPIOA_ODR  = GPIOA_BASE + 0x14
GPIOA_BSRR = GPIOA_BASE + 0x18

# Bitmasks: PA0 (bit 0) and PA5 (bit 5)
BSRR_SET_BOTH   = (1 << 0) | (1 << 5)              # 0x00000021 -> Turn PA0 & PA5 HIGH
BSRR_RESET_BOTH = (1 << (0 + 16)) | (1 << (5 + 16)) # 0x00210000 -> Turn PA0 & PA5 LOW

TARGET = 'py32f002bx5'

class SwdWorker(QThread):
    connection_changed = pyqtSignal(bool, str)
    state_updated      = pyqtSignal(bool, int)  # is_on, odr_raw_val

    def __init__(self):
        super().__init__()
        self.running = True
        self.command_queue = []

    def queue_command(self, bsrr_val):
        self.command_queue.append(bsrr_val)

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
                    self.connection_changed.emit(True, "J-Link STLink: Подключено (SWD активен 24/7)")

                # Execute pending write commands
                while self.command_queue:
                    cmd = self.command_queue.pop(0)
                    target.write32(GPIOA_BSRR, cmd)

                # Read current hardware GPIO state
                odr = target.read32(GPIOA_ODR)
                pa0 = (odr >> 0) & 1
                pa5 = (odr >> 5) & 1
                is_on = (pa0 != 0 or pa5 != 0)
                self.state_updated.emit(is_on, odr)

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
        self.setWindowTitle("BookLight — Тест подсветки (Шаг 1: ON / OFF)")
        self.setFixedSize(500, 480)

        # Blink test timer
        self.blink_timer = QTimer(self)
        self.blink_timer.timeout.connect(self.on_blink_tick)
        self.blink_state = False

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
                border-radius: 10px;
                font-weight: bold;
                padding: 14px;
                font-size: 15px;
            }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # ─── Status Bar ───
        status_card = QFrame()
        status_card.setProperty("class", "card")
        status_layout = QHBoxLayout(status_card)
        status_layout.setContentsMargins(12, 10, 12, 10)

        self.status_dot = QLabel("●")
        self.status_dot.setFont(QFont("Segoe UI", 16))
        self.status_dot.setStyleSheet("color: #e74c3c;")

        self.status_text = QLabel("Поиск микроконтроллера...")
        self.status_text.setFont(QFont("Segoe UI", 10))

        status_layout.addWidget(self.status_dot)
        status_layout.addWidget(self.status_text, 1)
        root.addWidget(status_card)

        # ─── Main Control Card ───
        ctrl_card = QFrame()
        ctrl_card.setProperty("class", "card")
        ctrl_layout = QVBoxLayout(ctrl_card)
        ctrl_layout.setSpacing(16)

        title = QLabel("Управление подсветкой (PA0 / PA5)")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ctrl_layout.addWidget(title)

        # Visual Lamp State Widget
        self.lamp_indicator = QLabel("ПОДСВЕТКА ВЫКЛЮЧЕНА")
        self.lamp_indicator.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.lamp_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lamp_indicator.setStyleSheet("""
            QLabel {
                background-color: #242933;
                color: #8892B0;
                border-radius: 10px;
                padding: 18px;
                border: 2px solid #3B4252;
            }
        """)
        ctrl_layout.addWidget(self.lamp_indicator)

        # Hardware Pin Readout
        self.pin_info = QLabel("PA0 (FET1): -- | PA5 (FET2): -- | ODR: --")
        self.pin_info.setFont(QFont("Consolas", 10))
        self.pin_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pin_info.setStyleSheet("color: #8892B0;")
        ctrl_layout.addWidget(self.pin_info)

        # Buttons Row: ON and OFF
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)

        self.btn_on = QPushButton("💡 ВКЛЮЧИТЬ")
        self.btn_on.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
            }
            QPushButton:hover {
                background-color: #2ecc71;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
        """)
        self.btn_on.clicked.connect(self.turn_on)
        btn_row.addWidget(self.btn_on)

        self.btn_off = QPushButton("🌑 ВЫКЛЮЧИТЬ")
        self.btn_off.setStyleSheet("""
            QPushButton {
                background-color: #c0392b;
                color: white;
                border: none;
            }
            QPushButton:hover {
                background-color: #e74c3c;
            }
            QPushButton:pressed {
                background-color: #962d22;
            }
        """)
        self.btn_off.clicked.connect(self.turn_off)
        btn_row.addWidget(self.btn_off)

        ctrl_layout.addLayout(btn_row)

        # Toggle Button
        self.btn_toggle = QPushButton("🔄 Переключить (Toggle)")
        self.btn_toggle.setStyleSheet("""
            QPushButton {
                background-color: #34495e;
                color: white;
                border: 1px solid #4a627a;
            }
            QPushButton:hover {
                background-color: #415b76;
            }
            QPushButton:pressed {
                background-color: #2c3e50;
            }
        """)
        self.btn_toggle.clicked.connect(self.toggle)
        ctrl_layout.addWidget(self.btn_toggle)

        # Blink Test Button
        self.btn_blink = QPushButton("⚡ Режим мигания: ВЫКЛ (Тест 1 Гц)")
        self.btn_blink.setStyleSheet("""
            QPushButton {
                background-color: #2c3e50;
                color: #bdc3c7;
                border: 1px dashed #7f8c8d;
            }
            QPushButton:hover {
                background-color: #34495e;
                color: white;
            }
        """)
        self.btn_blink.clicked.connect(self.toggle_blink)
        ctrl_layout.addWidget(self.btn_blink)

        root.addWidget(ctrl_card)
        root.addStretch()

    def turn_on(self):
        if self.blink_timer.isActive():
            self.toggle_blink()
        self.worker.queue_command(BSRR_SET_BOTH)

    def turn_off(self):
        if self.blink_timer.isActive():
            self.toggle_blink()
        self.worker.queue_command(BSRR_RESET_BOTH)

    def toggle(self):
        if self.blink_timer.isActive():
            self.toggle_blink()
        if hasattr(self, 'current_is_on') and self.current_is_on:
            self.worker.queue_command(BSRR_RESET_BOTH)
        else:
            self.worker.queue_command(BSRR_SET_BOTH)

    def toggle_blink(self):
        if self.blink_timer.isActive():
            self.blink_timer.stop()
            self.btn_blink.setText("⚡ Режим мигания: ВЫКЛ (Тест 1 Гц)")
            self.btn_blink.setStyleSheet("""
                QPushButton {
                    background-color: #2c3e50;
                    color: #bdc3c7;
                    border: 1px dashed #7f8c8d;
                }
            """)
        else:
            self.blink_state = False
            self.blink_timer.start(500) # 500 ms per half-period = 1 Hz
            self.btn_blink.setText("⚡ Режим мигания: АКТИВЕН (1 Гц)")
            self.btn_blink.setStyleSheet("""
                QPushButton {
                    background-color: #d35400;
                    color: white;
                    border: 1px solid #e67e22;
                    font-weight: bold;
                }
            """)

    def on_blink_tick(self):
        self.blink_state = not self.blink_state
        if self.blink_state:
            self.worker.queue_command(BSRR_SET_BOTH)
        else:
            self.worker.queue_command(BSRR_RESET_BOTH)

    def on_connection_changed(self, connected, message):
        if connected:
            self.status_dot.setStyleSheet("color: #2ecc71;")
            self.status_text.setText(message)
            self.btn_on.setEnabled(True)
            self.btn_off.setEnabled(True)
            self.btn_toggle.setEnabled(True)
            self.btn_blink.setEnabled(True)
        else:
            self.status_dot.setStyleSheet("color: #e74c3c;")
            self.status_text.setText(message)
            self.btn_on.setEnabled(False)
            self.btn_off.setEnabled(False)
            self.btn_toggle.setEnabled(False)
            self.btn_blink.setEnabled(False)

    def on_state_updated(self, is_on, odr_raw):
        self.current_is_on = is_on
        pa0 = (odr_raw >> 0) & 1
        pa5 = (odr_raw >> 5) & 1

        self.pin_info.setText(
            f"PA0 (Пин 13): {'HIGH (3.3V)' if pa0 else 'LOW (0V)'}  |  "
            f"PA5 (Пин 18): {'HIGH (3.3V)' if pa5 else 'LOW (0V)'}  |  "
            f"ODR: 0x{odr_raw:04X}"
        )

        if is_on:
            self.lamp_indicator.setText("💡 ПОДСВЕТКА ГОРИТ (ON)")
            self.lamp_indicator.setStyleSheet("""
                QLabel {
                    background-color: #2d2410;
                    color: #ffd166;
                    border-radius: 10px;
                    padding: 18px;
                    border: 2px solid #f39c12;
                    font-weight: bold;
                }
            """)
        else:
            self.lamp_indicator.setText("🌑 ПОДСВЕТКА ВЫКЛЮЧЕНА (OFF)")
            self.lamp_indicator.setStyleSheet("""
                QLabel {
                    background-color: #1e222b;
                    color: #6c7a9c;
                    border-radius: 10px;
                    padding: 18px;
                    border: 2px solid #2d333b;
                }
            """)

    def closeEvent(self, event):
        self.blink_timer.stop()
        self.worker.stop()
        event.accept()


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
