import sys
import time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QLabel, QPushButton, QFrame, 
    QSlider, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont
from pyocd.core.helpers import ConnectHelper

# Shared Memory Addresses for PUYA PY32F002Bx5 (g_lamp in SRAM @ 0x20000000)
ADDR_LAMP_BASE         = 0x20000000
ADDR_MAGIC             = ADDR_LAMP_BASE + 0x00  # 0x50574D31 ('PWM1')
ADDR_FIL_TARGET_PCT    = ADDR_LAMP_BASE + 0x04  # 0..100%
ADDR_FIL_CURRENT_PCT   = ADDR_LAMP_BASE + 0x08  # 0..100% (live GyverLED fade)
ADDR_FIL_PWM_RAW       = ADDR_LAMP_BASE + 0x0C  # 0..1000 (actual TIM1_CCR3)
ADDR_FIL_STATE         = ADDR_LAMP_BASE + 0x10  # 0 = OFF, 1 = ON
ADDR_FIL_SAVED_PCT     = ADDR_LAMP_BASE + 0x14  # Last ON value (1..100%)

ADDR_LED_TARGET_PCT    = ADDR_LAMP_BASE + 0x18  # 0..100%
ADDR_LED_CURRENT_PCT   = ADDR_LAMP_BASE + 0x1C  # 0..100% (live GyverLED fade)
ADDR_LED_PWM_RAW       = ADDR_LAMP_BASE + 0x20  # 0..1000 (actual TIM1_CCR1)
ADDR_LED_STATE         = ADDR_LAMP_BASE + 0x24  # 0 = OFF, 1 = ON
ADDR_LED_SAVED_PCT     = ADDR_LAMP_BASE + 0x28  # Last ON value (1..100%)

ADDR_TOUCH_RAW         = ADDR_LAMP_BASE + 0x2C  # 1 = touch detected, 0 = idle
ADDR_FADE_TIME_MS      = ADDR_LAMP_BASE + 0x30  # ms (default 250)

TARGET = 'py32f002bx5'


class SwdWorker(QThread):
    connection_changed = pyqtSignal(bool, str)
    # fil_target, fil_current, fil_pwm, fil_state, fil_saved,
    # led_target, led_current, led_pwm, led_state, led_saved,
    # touch_raw, fade_ms
    telemetry_updated  = pyqtSignal(int, int, int, int, int, int, int, int, int, int, int, int)

    def __init__(self):
        super().__init__()
        self.running = True
        self.command_queue = []

    def set_filaments_pct(self, val_100):
        self.command_queue.append(('FIL_TARGET', max(0, min(100, int(val_100)))))

    def set_leds_pct(self, val_100):
        self.command_queue.append(('LED_TARGET', max(0, min(100, int(val_100)))))

    def set_fade_time(self, val_ms):
        self.command_queue.append(('FADE_MS', max(10, min(5000, int(val_ms)))))

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
                    self.connection_changed.emit(True, "J-Link STLink: Подключено (Раздельное управление Филаментами и Диодами)")

                # Execute pending write commands to SRAM
                while self.command_queue:
                    cmd, val = self.command_queue.pop(0)
                    if cmd == 'FIL_TARGET':
                        target.write32(ADDR_FIL_TARGET_PCT, val)
                    elif cmd == 'LED_TARGET':
                        target.write32(ADDR_LED_TARGET_PCT, val)
                    elif cmd == 'FADE_MS':
                        target.write32(ADDR_FADE_TIME_MS, val)

                # Read telemetry block (13 x 32-bit words)
                data = target.read_memory_block32(ADDR_LAMP_BASE, 13)
                magic       = data[0]
                fil_target  = data[1]
                fil_curr    = data[2]
                fil_pwm     = data[3]
                fil_state   = data[4]
                fil_saved   = data[5]

                led_target  = data[6]
                led_curr    = data[7]
                led_pwm     = data[8]
                led_state   = data[9]
                led_saved   = data[10]

                touch_raw   = data[11]
                fade_ms     = data[12]

                if magic == 0x50574D31:
                    self.telemetry_updated.emit(
                        fil_target, fil_curr, fil_pwm, fil_state, fil_saved,
                        led_target, led_curr, led_pwm, led_state, led_saved,
                        touch_raw, fade_ms
                    )

                self.msleep(40) # ~25 Hz telemetry update

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
        self.setWindowTitle("BookLight — Раздельное управление (4 Филамента PB2 + Тестовые Диоды PA0)")
        self.setFixedSize(760, 800)

        self.fil_dragging = False
        self.led_dragging = False

        self.mem_fil_saved = 50
        self.mem_led_saved = 50
        self.cur_fil_state = 0
        self.cur_led_state = 0

        self.worker = SwdWorker()
        self.worker.connection_changed.connect(self.on_connection_changed)
        self.worker.telemetry_updated.connect(self.on_telemetry_updated)
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
            QProgressBar {
                border: 1px solid #2D333B;
                border-radius: 6px;
                background-color: #14171C;
                text-align: center;
                height: 14px;
                font-size: 11px;
                font-weight: bold;
                color: #E0E0E0;
            }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # ─── 1. Status Bar ───
        status_card = QFrame()
        status_card.setProperty("class", "card")
        status_layout = QHBoxLayout(status_card)
        status_layout.setContentsMargins(12, 8, 12, 8)

        self.status_dot = QLabel("●")
        self.status_dot.setFont(QFont("Segoe UI", 16))
        self.status_dot.setStyleSheet("color: #e74c3c;")

        self.status_text = QLabel("Подключение к микроконтроллеру PY32F002B...")
        self.status_text.setFont(QFont("Segoe UI", 10))

        status_layout.addWidget(self.status_dot)
        status_layout.addWidget(self.status_text, 1)
        root.addWidget(status_card)

        # ─── 2. Touch Sensor Banner ───
        touch_card = QFrame()
        touch_card.setProperty("class", "card")
        touch_layout = QHBoxLayout(touch_card)
        touch_layout.setContentsMargins(14, 10, 14, 10)

        touch_icon = QLabel("👆")
        touch_icon.setFont(QFont("Segoe UI", 18))

        touch_box = QVBoxLayout()
        touch_title = QLabel("ЕМКОСТНЫЙ СЕНСОР (TTP223 на PB4 / Pad M+)")
        touch_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        touch_sub = QLabel("Управляет только филаментами: короткий тап = Вкл/Выкл с памятью | Удержание = диммирование")
        touch_sub.setStyleSheet("color: #8892B0; font-size: 11px;")
        touch_box.addWidget(touch_title)
        touch_box.addWidget(touch_sub)

        self.touch_badge = QLabel("ОЖИДАНИЕ КАСАНИЯ")
        self.touch_badge.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.touch_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 6px 14px; border-radius: 8px;")

        touch_layout.addWidget(touch_icon)
        touch_layout.addLayout(touch_box, 1)
        touch_layout.addWidget(self.touch_badge)
        root.addWidget(touch_card)

        # ─── 3. Card 1: 4 COB Filaments (PB2 / TIM1_CH3) ───
        fil_card = QFrame()
        fil_card.setProperty("class", "card")
        fil_layout = QVBoxLayout(fil_card)
        fil_layout.setSpacing(12)

        fil_header = QHBoxLayout()
        fil_title = QLabel("🔥 ВСЕ 4 COB ФИЛАМЕНТА (ШИМ TIM1_CH3 / PB2, Pad Coil 2)")
        fil_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        fil_title.setStyleSheet("color: #f39c12;")
        self.fil_badge = QLabel("ВЫКЛ (0%)")
        self.fil_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 4px 12px; border-radius: 6px; font-weight: bold;")
        fil_header.addWidget(fil_title)
        fil_header.addStretch()
        fil_header.addWidget(self.fil_badge)
        fil_layout.addLayout(fil_header)

        fil_desc = QLabel("Силовой ключ CJ3415 P-FET (до 4.0А). Регулировка 1..100%, Gamma 2.2, память последнего значения при выключении.")
        fil_desc.setStyleSheet("color: #8892B0; font-size: 11px;")
        fil_layout.addWidget(fil_desc)

        # Slider Row
        slider_fil_row = QHBoxLayout()
        self.slider_fil = QSlider(Qt.Orientation.Horizontal)
        self.slider_fil.setStyleSheet("""
            QSlider::sub-page:horizontal { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d35400, stop:1 #f39c12); border-radius: 5px; }
            QSlider::handle:horizontal { background: #ffffff; border: 3px solid #e67e22; width: 24px; margin-top: -7px; margin-bottom: -7px; border-radius: 12px; }
        """)
        self.slider_fil.setRange(0, 100)
        self.slider_fil.setValue(0)
        self.slider_fil.sliderPressed.connect(lambda: setattr(self, 'fil_dragging', True))
        self.slider_fil.sliderReleased.connect(self.on_fil_slider_released)
        self.slider_fil.valueChanged.connect(self.on_fil_slider_changed)

        self.lbl_fil_val = QLabel("0%")
        self.lbl_fil_val.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.lbl_fil_val.setFixedWidth(65)
        self.lbl_fil_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_fil_val.setStyleSheet("color: #f39c12;")

        self.btn_fil_toggle = QPushButton("ВЫКЛ ➔ ВКЛ")
        self.btn_fil_toggle.setStyleSheet("background-color: #d35400; color: white; padding: 10px 16px;")
        self.btn_fil_toggle.clicked.connect(self.on_fil_toggle_clicked)

        slider_fil_row.addWidget(self.slider_fil, 1)
        slider_fil_row.addWidget(self.lbl_fil_val)
        slider_fil_row.addWidget(self.btn_fil_toggle)
        fil_layout.addLayout(slider_fil_row)

        # Filaments Progress Bar
        self.prog_fil = QProgressBar()
        self.prog_fil.setStyleSheet("QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d35400, stop:1 #f39c12); border-radius: 5px; }")
        self.prog_fil.setRange(0, 100)
        self.prog_fil.setValue(0)
        self.prog_fil.setFormat("Текущая яркость: %v%")
        fil_layout.addWidget(self.prog_fil)

        # Filaments Presets
        fil_presets_row = QHBoxLayout()
        fil_presets_row.setSpacing(6)
        presets_fil = [(0, "🌑 Выкл"), (10, "10%"), (25, "25%"), (50, "50%"), (75, "75%"), (100, "🌟 100%")]
        for p, label in presets_fil:
            btn = QPushButton(label)
            btn.setStyleSheet("background-color: #242933; color: #E0E0E0; padding: 6px 10px; font-size: 11px;")
            btn.clicked.connect(lambda _, val=p: self.apply_fil_target(val))
            fil_presets_row.addWidget(btn)
        fil_layout.addLayout(fil_presets_row)

        self.lbl_fil_raw = QLabel("ШИМ CCR3 = 0/1000 | Память последнего значения: 50%")
        self.lbl_fil_raw.setFont(QFont("Consolas", 10))
        self.lbl_fil_raw.setStyleSheet("color: #8892B0;")
        fil_layout.addWidget(self.lbl_fil_raw)

        root.addWidget(fil_card)

        # ─── 4. Card 2: Test Board LEDs (PA0 / TIM1_CH1) ───
        led_card = QFrame()
        led_card.setProperty("class", "card")
        led_layout = QVBoxLayout(led_card)
        led_layout.setSpacing(12)

        led_header = QHBoxLayout()
        led_title = QLabel("💡 ТЕСТОВЫЕ ДИОДЫ НА ПЛАТЕ (ШИМ TIM1_CH1 / PA0, Pin 13)")
        led_title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        led_title.setStyleSheet("color: #2ecc71;")
        self.led_badge = QLabel("ВЫКЛ (0% - Полный ноль)")
        self.led_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 4px 12px; border-radius: 6px; font-weight: bold;")
        led_header.addWidget(led_title)
        led_header.addStretch()
        led_header.addWidget(self.led_badge)
        led_layout.addLayout(led_header)

        led_desc = QLabel("Полностью отдельный канал. При 0% ШИМ = 0 (диоды полностью гаснут в ноль). Кнопка восстанавливает последнее значение.")
        led_desc.setStyleSheet("color: #8892B0; font-size: 11px;")
        led_layout.addWidget(led_desc)

        # LED Slider Row
        slider_led_row = QHBoxLayout()
        self.slider_led = QSlider(Qt.Orientation.Horizontal)
        self.slider_led.setStyleSheet("""
            QSlider::sub-page:horizontal { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #27ae60, stop:1 #2ecc71); border-radius: 5px; }
            QSlider::handle:horizontal { background: #ffffff; border: 3px solid #27ae60; width: 24px; margin-top: -7px; margin-bottom: -7px; border-radius: 12px; }
        """)
        self.slider_led.setRange(0, 100)
        self.slider_led.setValue(0)
        self.slider_led.sliderPressed.connect(lambda: setattr(self, 'led_dragging', True))
        self.slider_led.sliderReleased.connect(self.on_led_slider_released)
        self.slider_led.valueChanged.connect(self.on_led_slider_changed)

        self.lbl_led_val = QLabel("0%")
        self.lbl_led_val.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.lbl_led_val.setFixedWidth(65)
        self.lbl_led_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_led_val.setStyleSheet("color: #2ecc71;")

        self.btn_led_toggle = QPushButton("ВЫКЛ ➔ ВКЛ")
        self.btn_led_toggle.setStyleSheet("background-color: #27ae60; color: white; padding: 10px 16px;")
        self.btn_led_toggle.clicked.connect(self.on_led_toggle_clicked)

        slider_led_row.addWidget(self.slider_led, 1)
        slider_led_row.addWidget(self.lbl_led_val)
        slider_led_row.addWidget(self.btn_led_toggle)
        led_layout.addLayout(slider_led_row)

        # LED Progress Bar
        self.prog_led = QProgressBar()
        self.prog_led.setStyleSheet("QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #27ae60, stop:1 #2ecc71); border-radius: 5px; }")
        self.prog_led.setRange(0, 100)
        self.prog_led.setValue(0)
        self.prog_led.setFormat("Текущая яркость: %v%")
        led_layout.addWidget(self.prog_led)

        # LED Presets
        led_presets_row = QHBoxLayout()
        led_presets_row.setSpacing(6)
        presets_led = [(0, "🌑 0% (ВЫКЛ В НОЛЬ)"), (10, "10%"), (25, "25%"), (50, "50%"), (75, "75%"), (100, "💡 100%")]
        for p, label in presets_led:
            btn = QPushButton(label)
            btn.setStyleSheet("background-color: #242933; color: #E0E0E0; padding: 6px 10px; font-size: 11px;")
            btn.clicked.connect(lambda _, val=p: self.apply_led_target(val))
            led_presets_row.addWidget(btn)
        led_layout.addLayout(led_presets_row)

        self.lbl_led_raw = QLabel("ШИМ CCR1 = 0/1000 (0V) | Память последнего значения: 50%")
        self.lbl_led_raw.setFont(QFont("Consolas", 10))
        self.lbl_led_raw.setStyleSheet("color: #8892B0;")
        led_layout.addWidget(self.lbl_led_raw)

        root.addWidget(led_card)

    def on_connection_changed(self, connected, message):
        if connected:
            self.status_dot.setStyleSheet("color: #2ecc71;")
            self.status_text.setText(message)
        else:
            self.status_dot.setStyleSheet("color: #e74c3c;")
            self.status_text.setText(message)

    # ─── Filaments Handlers ───
    def on_fil_slider_released(self):
        self.fil_dragging = False
        val = self.slider_fil.value()
        self.worker.set_filaments_pct(val)

    def on_fil_slider_changed(self, value):
        self.lbl_fil_val.setText(f"{value}%")
        if self.fil_dragging:
            self.worker.set_filaments_pct(value)

    def apply_fil_target(self, value):
        self.slider_fil.setValue(value)
        self.worker.set_filaments_pct(value)

    def on_fil_toggle_clicked(self):
        if self.cur_fil_state:
            # Turn OFF
            self.apply_fil_target(0)
        else:
            # Turn ON to last saved
            target = self.mem_fil_saved if self.mem_fil_saved >= 1 else 50
            self.apply_fil_target(target)

    # ─── Board LEDs Handlers ───
    def on_led_slider_released(self):
        self.led_dragging = False
        val = self.slider_led.value()
        self.worker.set_leds_pct(val)

    def on_led_slider_changed(self, value):
        self.lbl_led_val.setText(f"{value}%")
        if self.led_dragging:
            self.worker.set_leds_pct(value)

    def apply_led_target(self, value):
        self.slider_led.setValue(value)
        self.worker.set_leds_pct(value)

    def on_led_toggle_clicked(self):
        if self.cur_led_state:
            # Turn OFF
            self.apply_led_target(0)
        else:
            # Turn ON to last saved
            target = self.mem_led_saved if self.mem_led_saved >= 1 else 50
            self.apply_led_target(target)

    # ─── Live Telemetry ───
    def on_telemetry_updated(
        self, fil_target, fil_curr, fil_pwm, fil_state, fil_saved,
        led_target, led_curr, led_pwm, led_state, led_saved,
        touch_raw, fade_ms
    ):
        self.cur_fil_state = fil_state
        self.mem_fil_saved = fil_saved
        self.cur_led_state = led_state
        self.mem_led_saved = led_saved

        # Touch sensor indicator
        if touch_raw:
            self.touch_badge.setText("👆 ПРИКОСНОВЕНИЕ!")
            self.touch_badge.setStyleSheet("background-color: #27ae60; color: #ffffff; padding: 6px 14px; border-radius: 8px; font-weight: bold;")
        else:
            self.touch_badge.setText("ОЖИДАНИЕ КАСАНИЯ")
            self.touch_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 6px 14px; border-radius: 8px;")

        # Update Filaments UI
        if not self.fil_dragging:
            if abs(self.slider_fil.value() - fil_target) > 1:
                self.slider_fil.setValue(fil_target)

        self.prog_fil.setValue(fil_curr)

        if fil_state == 0 and fil_curr == 0:
            self.fil_badge.setText("ВЫКЛ (0%)")
            self.fil_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 4px 12px; border-radius: 6px; font-weight: bold;")
            self.btn_fil_toggle.setText(f"ВКЛ ({fil_saved}%)")
            self.btn_fil_toggle.setStyleSheet("background-color: #27ae60; color: white; padding: 10px 16px;")
        else:
            self.fil_badge.setText(f"СВЕТИТ {fil_curr}%")
            self.fil_badge.setStyleSheet("background-color: #d35400; color: white; padding: 4px 12px; border-radius: 6px; font-weight: bold;")
            self.btn_fil_toggle.setText("ВЫКЛ (0%)")
            self.btn_fil_toggle.setStyleSheet("background-color: #c0392b; color: white; padding: 10px 16px;")

        self.lbl_fil_raw.setText(f"ШИМ TIM1->CCR3 = {fil_pwm}/1000 (Gamma 2.2) | Последнее значение памяти: {fil_saved}%")

        # Update Board LEDs UI
        if not self.led_dragging:
            if abs(self.slider_led.value() - led_target) > 1:
                self.slider_led.setValue(led_target)

        self.prog_led.setValue(led_curr)

        if led_state == 0 and led_curr == 0:
            self.led_badge.setText("ВЫКЛ (0% - Полный ноль)")
            self.led_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 4px 12px; border-radius: 6px; font-weight: bold;")
            self.btn_led_toggle.setText(f"ВКЛ ({led_saved}%)")
            self.btn_led_toggle.setStyleSheet("background-color: #27ae60; color: white; padding: 10px 16px;")
        else:
            self.led_badge.setText(f"СВЕТИТ {led_curr}%")
            self.led_badge.setStyleSheet("background-color: #27ae60; color: white; padding: 4px 12px; border-radius: 6px; font-weight: bold;")
            self.btn_led_toggle.setText("ВЫКЛ (0%)")
            self.btn_led_toggle.setStyleSheet("background-color: #c0392b; color: white; padding: 10px 16px;")

        self.lbl_led_raw.setText(f"ШИМ TIM1->CCR1 = {led_pwm}/1000 ({'0V, 100% OFF' if led_pwm == 0 else 'Активен'}) | Память: {led_saved}%")

    def closeEvent(self, event):
        self.worker.stop()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
