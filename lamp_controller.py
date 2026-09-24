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

# Shared Memory Addresses for PUYA PY32F002Bx5 (g_lamp in SRAM)
ADDR_LAMP_BASE           = 0x20000000
ADDR_MAGIC               = ADDR_LAMP_BASE + 0x00  # 0x50574D31 ('PWM1')
ADDR_TARGET_BRIGHTNESS   = ADDR_LAMP_BASE + 0x04  # 0..255
ADDR_CURRENT_BRIGHTNESS  = ADDR_LAMP_BASE + 0x08  # 0..255 (live GyverLED fade)
ADDR_PWM_RAW             = ADDR_LAMP_BASE + 0x0C  # 0..1000 (actual TIM1_CCR3)
ADDR_TOUCH_RAW           = ADDR_LAMP_BASE + 0x10  # 1 = touch detected, 0 = idle
ADDR_FADE_TIME           = ADDR_LAMP_BASE + 0x14  # ms (default 350)
ADDR_LAMP_STATE          = ADDR_LAMP_BASE + 0x18  # 0 = OFF, 1 = ON

TARGET = 'py32f002bx5'


class SwdWorker(QThread):
    connection_changed = pyqtSignal(bool, str)
    # target_b, current_b, pwm_raw, touch_raw, fade_ms, state
    telemetry_updated  = pyqtSignal(int, int, int, int, int, int)

    def __init__(self):
        super().__init__()
        self.running = True
        self.command_queue = []

    def set_target_brightness(self, val_255):
        self.command_queue.append(('TARGET_B', max(0, min(255, int(val_255)))))

    def set_fade_time(self, val_ms):
        self.command_queue.append(('FADE_MS', max(10, min(5000, int(val_ms)))))

    def toggle_lamp(self, target_val_255):
        self.command_queue.append(('TARGET_B', max(0, min(255, int(target_val_255)))))

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
                    self.connection_changed.emit(True, "J-Link STLink: Подключено (GyverLED + GyverButton + Gamma 2.2)")

                # Execute pending write commands to SRAM
                while self.command_queue:
                    cmd, val = self.command_queue.pop(0)
                    if cmd == 'TARGET_B':
                        target.write32(ADDR_TARGET_BRIGHTNESS, val)
                    elif cmd == 'FADE_MS':
                        target.write32(ADDR_FADE_TIME, val)

                # Read telemetry block (7 x 32-bit words)
                data = target.read_memory_block32(ADDR_LAMP_BASE, 7)
                magic       = data[0]
                target_b    = data[1]
                current_b   = data[2]
                pwm_raw     = data[3]
                touch_raw   = data[4]
                fade_ms     = data[5]
                lamp_state  = data[6]

                if magic == 0x50574D31:
                    self.telemetry_updated.emit(target_b, current_b, pwm_raw, touch_raw, fade_ms, lamp_state)

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
        self.setWindowTitle("BookLight — GyverLED + GyverButton (Все 4 филамента на TIM1_CH3 PB2)")
        self.setFixedSize(700, 720)

        self.user_dragging = False
        self.saved_brightness = 150
        self.last_state = 0

        # Breathing effect timer
        self.breathe_timer = QTimer(self)
        self.breathe_timer.timeout.connect(self.on_breathe_tick)
        self.breathe_active = False
        self.breathe_val = 0
        self.breathe_dir = 2

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
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d35400, stop:1 #f39c12);
                border-radius: 5px;
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

        # ─── 2. Touch Sensor Banner (TTP223 on PB4 / Pad M+) ───
        touch_card = QFrame()
        touch_card.setProperty("class", "card")
        touch_layout = QHBoxLayout(touch_card)
        touch_layout.setContentsMargins(16, 12, 16, 12)

        touch_icon = QLabel("👆")
        touch_icon.setFont(QFont("Segoe UI", 18))

        touch_title_box = QVBoxLayout()
        touch_title = QLabel("ЕМКОСТНЫЙ СЕНСОР (TTP223 на PB4 / Pad M+)")
        touch_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        touch_sub = QLabel("Короткое касание = Вкл/Выкл с плавным фейдом | Удержание = Плавная регулировка")
        touch_sub.setStyleSheet("color: #8892B0; font-size: 11px;")
        touch_title_box.addWidget(touch_title)
        touch_title_box.addWidget(touch_sub)

        self.touch_badge = QLabel("ОЖИДАНИЕ КАСАНИЯ")
        self.touch_badge.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.touch_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 6px 14px; border-radius: 8px;")

        touch_layout.addWidget(touch_icon)
        touch_layout.addLayout(touch_title_box, 1)
        touch_layout.addWidget(self.touch_badge)
        root.addWidget(touch_card)

        # ─── 3. Main Lamp Control Card ───
        lamp_card = QFrame()
        lamp_card.setProperty("class", "card")
        lamp_layout = QVBoxLayout(lamp_card)
        lamp_layout.setSpacing(14)

        header_row = QHBoxLayout()
        title_lamp = QLabel("💡 4 COB ФИЛАМЕНТА (ШИМ 1.0 кГц + Нелинейная Gamma 2.2)")
        title_lamp.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title_lamp.setStyleSheet("color: #f39c12;")

        self.state_badge = QLabel("ВЫКЛ (0/255)")
        self.state_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 4px 12px; border-radius: 6px; font-weight: bold;")
        header_row.addWidget(title_lamp)
        header_row.addStretch()
        header_row.addWidget(self.state_badge)
        lamp_layout.addLayout(header_row)

        desc_lamp = QLabel("Пятак Coil Pad 2 (Силовой ключ CJ3415 P-FET до 4.0А). Драйвер GyverLED на millis() без блокировок.")
        desc_lamp.setStyleSheet("color: #8892B0; font-size: 11px;")
        lamp_layout.addWidget(desc_lamp)

        # Target Slider Row
        slider_row = QHBoxLayout()
        self.slider_target = QSlider(Qt.Orientation.Horizontal)
        self.slider_target.setRange(0, 255)
        self.slider_target.setValue(0)
        self.slider_target.sliderPressed.connect(self.on_slider_pressed)
        self.slider_target.sliderReleased.connect(self.on_slider_released)
        self.slider_target.valueChanged.connect(self.on_slider_val_changed)

        self.lbl_target_val = QLabel("0")
        self.lbl_target_val.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.lbl_target_val.setFixedWidth(60)
        self.lbl_target_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_target_val.setStyleSheet("color: #f39c12;")

        self.btn_toggle = QPushButton("🔄 ВКЛ/ВЫКЛ")
        self.btn_toggle.setStyleSheet("background-color: #d35400; color: white; padding: 10px 16px;")
        self.btn_toggle.clicked.connect(self.on_toggle_lamp)

        slider_row.addWidget(self.slider_target, 1)
        slider_row.addWidget(self.lbl_target_val)
        slider_row.addWidget(self.btn_toggle)
        lamp_layout.addLayout(slider_row)

        # Real-time GyverLED Interpolation Bar
        bar_layout = QVBoxLayout()
        bar_label = QLabel("Текущая яркость GyverLED (плавный переход в реальном времени):")
        bar_label.setStyleSheet("color: #8892B0; font-size: 11px;")
        self.prog_current = QProgressBar()
        self.prog_current.setRange(0, 255)
        self.prog_current.setValue(0)
        self.prog_current.setFormat("%v / 255")
        bar_layout.addWidget(bar_label)
        bar_layout.addWidget(self.prog_current)
        lamp_layout.addLayout(bar_layout)

        # Presets Buttons Row
        preset_row = QHBoxLayout()
        preset_row.setSpacing(8)
        presets = [
            (0, "🌑 Выкл"),
            (25, "🌙 Ночник (10%)"),
            (75, "📖 Уют (30%)"),
            (150, "📚 Чтение (60%)"),
            (255, "🌟 Макс (100%)")
        ]
        for val, label in presets:
            btn = QPushButton(label)
            btn.setStyleSheet("background-color: #242933; color: #E0E0E0; padding: 8px 10px; font-size: 12px;")
            btn.clicked.connect(lambda _, v=val: self.apply_brightness(v))
            preset_row.addWidget(btn)

        self.btn_breathe = QPushButton("🌊 Дыхание")
        self.btn_breathe.setStyleSheet("background-color: #2980b9; color: white; padding: 8px 12px; font-size: 12px;")
        self.btn_breathe.clicked.connect(self.toggle_breathe)
        preset_row.addWidget(self.btn_breathe)

        lamp_layout.addLayout(preset_row)
        root.addWidget(lamp_card)

        # ─── 4. Fade Time Tuning Card ───
        tuning_card = QFrame()
        tuning_card.setProperty("class", "card")
        tuning_layout = QVBoxLayout(tuning_card)
        tuning_layout.setSpacing(8)

        tuning_header = QHBoxLayout()
        tuning_title = QLabel("⏱️ Скорость плавного затухания / включения (fade_time_ms)")
        tuning_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.lbl_fade_val = QLabel("350 мс")
        self.lbl_fade_val.setStyleSheet("color: #3498db; font-weight: bold;")
        tuning_header.addWidget(tuning_title)
        tuning_header.addStretch()
        tuning_header.addWidget(self.lbl_fade_val)
        tuning_layout.addLayout(tuning_header)

        self.slider_fade = QSlider(Qt.Orientation.Horizontal)
        self.slider_fade.setStyleSheet("QSlider::sub-page:horizontal { background: #3498db; } QSlider::handle:horizontal { border: 2px solid #2980b9; }")
        self.slider_fade.setRange(50, 1500)
        self.slider_fade.setValue(350)
        self.slider_fade.valueChanged.connect(self.on_slider_fade_changed)
        tuning_layout.addWidget(self.slider_fade)
        root.addWidget(tuning_card)

        # ─── 5. Telemetry & Hardware State ───
        telem_card = QFrame()
        telem_card.setProperty("class", "card")
        telem_layout = QVBoxLayout(telem_card)
        telem_layout.setSpacing(4)

        self.lbl_telem1 = QLabel("Аппаратный ШИМ: TIM1->CCR3 = 0/1000 (Gamma 2.2) | 1.0 кГц | Нагрузка ЦПУ: 0%")
        self.lbl_telem1.setFont(QFont("Consolas", 10))
        self.lbl_telem1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_telem1.setStyleSheet("color: #8892B0;")

        self.lbl_telem2 = QLabel("Индикаторный LED (PA0): TIM1_CH1 Standby=5% / Active=50%")
        self.lbl_telem2.setFont(QFont("Consolas", 9))
        self.lbl_telem2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_telem2.setStyleSheet("color: #5C677D;")

        telem_layout.addWidget(self.lbl_telem1)
        telem_layout.addWidget(self.lbl_telem2)
        root.addWidget(telem_card)

    def on_connection_changed(self, connected, message):
        if connected:
            self.status_dot.setStyleSheet("color: #2ecc71;")
            self.status_text.setText(message)
        else:
            self.status_dot.setStyleSheet("color: #e74c3c;")
            self.status_text.setText(message)

    def on_slider_pressed(self):
        self.user_dragging = True

    def on_slider_released(self):
        self.user_dragging = False
        val = self.slider_target.value()
        self.worker.set_target_brightness(val)

    def on_slider_val_changed(self, value):
        self.lbl_target_val.setText(str(value))
        if self.user_dragging:
            self.worker.set_target_brightness(value)

    def apply_brightness(self, value):
        self.slider_target.setValue(value)
        self.worker.set_target_brightness(value)

    def on_slider_fade_changed(self, value):
        self.lbl_fade_val.setText(f"{value} мс")
        self.worker.set_fade_time(value)

    def on_toggle_lamp(self):
        cur = self.slider_target.value()
        if cur > 0:
            self.saved_brightness = cur
            self.apply_brightness(0)
        else:
            self.apply_brightness(self.saved_brightness if self.saved_brightness > 0 else 150)

    def toggle_breathe(self):
        self.breathe_active = not self.breathe_active
        if self.breathe_active:
            self.btn_breathe.setText("⏸ Стоп")
            self.btn_breathe.setStyleSheet("background-color: #e67e22; color: white; padding: 8px 12px; font-size: 12px;")
            self.slider_fade.setValue(80) # Faster transition during breathe
            self.breathe_timer.start(50)
        else:
            self.btn_breathe.setText("🌊 Дыхание")
            self.btn_breathe.setStyleSheet("background-color: #2980b9; color: white; padding: 8px 12px; font-size: 12px;")
            self.slider_fade.setValue(350)
            self.breathe_timer.stop()

    def on_breathe_tick(self):
        self.breathe_val += self.breathe_dir
        if self.breathe_val >= 250:
            self.breathe_val = 250
            self.breathe_dir = -5
        elif self.breathe_val <= 10:
            self.breathe_val = 10
            self.breathe_dir = 5
        self.apply_brightness(self.breathe_val)

    def on_telemetry_updated(self, target_b, current_b, pwm_raw, touch_raw, fade_ms, lamp_state):
        self.last_state = lamp_state

        # Update touch sensor visualizer
        if touch_raw:
            self.touch_badge.setText("👆 ПРИКОСНОВЕНИЕ!")
            self.touch_badge.setStyleSheet("background-color: #27ae60; color: #ffffff; padding: 6px 14px; border-radius: 8px; font-weight: bold;")
        else:
            self.touch_badge.setText("ОЖИДАНИЕ КАСАНИЯ")
            self.touch_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 6px 14px; border-radius: 8px;")

        # Update sliders only if user is not actively dragging
        if not self.user_dragging and not self.breathe_active:
            if abs(self.slider_target.value() - target_b) > 1:
                self.slider_target.setValue(target_b)

        self.prog_current.setValue(current_b)

        pct = int(current_b * 100 / 255)
        if lamp_state == 0 and current_b == 0:
            self.state_badge.setText("ВЫКЛ (0%)")
            self.state_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 4px 12px; border-radius: 6px; font-weight: bold;")
        else:
            self.state_badge.setText(f"СВЕТИТ {pct}% ({current_b}/255)")
            self.state_badge.setStyleSheet("background-color: #d35400; color: white; padding: 4px 12px; border-radius: 6px; font-weight: bold;")

        self.lbl_telem1.setText(
            f"Аппаратный ШИМ: TIM1->CCR3 = {pwm_raw}/1000 (Gamma 2.2) | 1.0 кГц | Яркость: {current_b}/255 | 0% CPU"
        )
        self.lbl_telem2.setText(
            f"Лампа: {'ВКЛ' if lamp_state else 'ВЫКЛ'} | Фейд: {fade_ms} мс | Индикатор PA0: {'50%' if lamp_state else '5%'}"
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
