import sys
import time
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QLabel, QPushButton, QFrame, 
    QSlider, QProgressBar, QCheckBox, QComboBox
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

ADDR_DISP_POWER        = ADDR_LAMP_BASE + 0x34  # 1 = ON, 0 = OFF (sleep)
ADDR_DISP_PERCENT      = ADDR_LAMP_BASE + 0x38  # 0..100
ADDR_DISP_BARS         = ADDR_LAMP_BASE + 0x3C  # 0..4
ADDR_DISP_ICONS        = ADDR_LAMP_BASE + 0x40  # 0x02 = lightning
ADDR_DISP_HL_LEFT      = ADDR_LAMP_BASE + 0x44  # color enum 0..7
ADDR_DISP_HL_RIGHT     = ADDR_LAMP_BASE + 0x48  # color enum 0..7
ADDR_DISP_AUTO_SYNC    = ADDR_LAMP_BASE + 0x4C  # 1 = auto, 0 = manual

# Step 6: Battery & Charging Telemetry (Internal VREFINT + C60H PB5)
ADDR_BAT_MILLIVOLTS    = ADDR_LAMP_BASE + 0x50  # mV (e.g. 3300 or 4150)
ADDR_BAT_PERCENT       = ADDR_LAMP_BASE + 0x54  # 0..100%
ADDR_BAT_ADC_RAW       = ADDR_LAMP_BASE + 0x58  # 12-bit ADC raw code
ADDR_CHRG_PIN_RAW      = ADDR_LAMP_BASE + 0x5C  # 0 = LOW (charging), 1 = HIGH (idle)
ADDR_IS_CHARGING       = ADDR_LAMP_BASE + 0x60  # 1 = charging, 0 = battery

TARGET = 'py32f002bx5'

COLOR_NAMES = ["Выкл", "Красный", "Зелёный", "Синий", "Циан", "Маджента", "Жёлтый", "Белый"]


class SwdWorker(QThread):
    connection_changed = pyqtSignal(bool, str)
    telemetry_updated  = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.running = True
        self.command_queue = []

    def set_filaments_pct(self, val_100):
        self.command_queue.append(('FIL_TARGET', max(0, min(100, int(val_100)))))

    def set_leds_pct(self, val_100):
        self.command_queue.append(('LED_TARGET', max(0, min(100, int(val_100)))))

    def set_disp_param(self, field, val):
        self.command_queue.append((field, int(val)))

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
                    self.connection_changed.emit(True, "J-Link STLink: Подключено (TIM1 ШИМ + TIM14 Дисплей + АЦП Батареи)")

                # Execute pending write commands to SRAM
                while self.command_queue:
                    cmd, val = self.command_queue.pop(0)
                    if cmd == 'FIL_TARGET':
                        target.write32(ADDR_FIL_TARGET_PCT, val)
                    elif cmd == 'LED_TARGET':
                        target.write32(ADDR_LED_TARGET_PCT, val)
                    elif cmd == 'DISP_POWER':
                        target.write32(ADDR_DISP_POWER, val)
                    elif cmd == 'DISP_PERCENT':
                        target.write32(ADDR_DISP_PERCENT, val)
                    elif cmd == 'DISP_BARS':
                        target.write32(ADDR_DISP_BARS, val)
                    elif cmd == 'DISP_ICONS':
                        target.write32(ADDR_DISP_ICONS, val)
                    elif cmd == 'DISP_COLOR':
                        target.write32(ADDR_DISP_HL_LEFT, val)
                        target.write32(ADDR_DISP_HL_RIGHT, val)
                    elif cmd == 'DISP_AUTO':
                        target.write32(ADDR_DISP_AUTO_SYNC, val)

                # Read telemetry block (25 x 32-bit words = 100 bytes)
                data = target.read_memory_block32(ADDR_LAMP_BASE, 25)
                if data[0] == 0x50574D31:
                    telem = {
                        'fil_target': data[1],
                        'fil_curr':   data[2],
                        'fil_pwm':    data[3],
                        'fil_state':  data[4],
                        'fil_saved':  data[5],
                        'led_target': data[6],
                        'led_curr':   data[7],
                        'led_pwm':    data[8],
                        'led_state':  data[9],
                        'led_saved':  data[10],
                        'touch_raw':  data[11],
                        'fade_ms':    data[12],
                        'disp_power': data[13],
                        'disp_pct':   data[14],
                        'disp_bars':  data[15],
                        'disp_icons': data[16],
                        'disp_hl_l':  data[17],
                        'disp_hl_r':  data[18],
                        'disp_auto':  data[19],
                        'bat_mv':     data[20],
                        'bat_pct':    data[21],
                        'bat_adc':    data[22],
                        'chrg_pin':   data[23],
                        'is_charging':data[24],
                    }
                    self.telemetry_updated.emit(telem)

                self.msleep(40) # ~25 Hz update

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
        self.setWindowTitle("BookLight — Филаменты + Светодиоды + Дисплей FH8016 + АКБ и C60H")
        self.setFixedSize(780, 1020)

        self.fil_dragging = False
        self.led_dragging = False
        self.disp_dragging = False

        self.mem_fil_saved = 50
        self.mem_led_saved = 50
        self.cur_fil_state = 0
        self.cur_led_state = 0

        # Touch sensor diagnostics
        self.touch_press_start = 0.0
        self.last_touch_raw = 0
        self.touch_clicks_count = 0
        self.last_release_time = 0.0
        self.click_train = 0

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
                padding: 14px;
            }
            QPushButton {
                border-radius: 8px;
                font-weight: bold;
                padding: 8px 12px;
                font-size: 12px;
            }
            QSlider::groove:horizontal {
                height: 8px;
                background: #2D333B;
                border-radius: 4px;
            }
            QProgressBar {
                border: 1px solid #2D333B;
                border-radius: 6px;
                background-color: #14171C;
                text-align: center;
                height: 12px;
                font-size: 10px;
                font-weight: bold;
                color: #E0E0E0;
            }
            QComboBox {
                background-color: #242933;
                border: 1px solid #2D333B;
                border-radius: 6px;
                padding: 4px 8px;
                color: #E0E0E0;
            }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 12, 18, 12)
        root.setSpacing(10)

        # ─── 1. Status Bar ───
        status_card = QFrame()
        status_card.setProperty("class", "card")
        status_layout = QHBoxLayout(status_card)
        status_layout.setContentsMargins(10, 6, 10, 6)

        self.status_dot = QLabel("●")
        self.status_dot.setFont(QFont("Segoe UI", 16))
        self.status_dot.setStyleSheet("color: #e74c3c;")

        self.status_text = QLabel("Подключение к микроконтроллеру PY32F002B...")
        self.status_text.setFont(QFont("Segoe UI", 10))

        status_layout.addWidget(self.status_dot)
        status_layout.addWidget(self.status_text, 1)
        root.addWidget(status_card)

        # ─── 2. Touch Sensor Diagnostic Card ───
        touch_card = QFrame()
        touch_card.setProperty("class", "card")
        touch_layout = QVBoxLayout(touch_card)
        touch_layout.setContentsMargins(12, 8, 12, 8)
        touch_layout.setSpacing(6)

        touch_header = QHBoxLayout()
        touch_icon = QLabel("👆")
        touch_icon.setFont(QFont("Segoe UI", 14))

        touch_title_box = QVBoxLayout()
        touch_title = QLabel("ТЕСТ И ДИАГНОСТИКА СЕНСОРА TTP223 (Пин 8 / PB4 / Pad M+)")
        touch_title.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        touch_title.setStyleSheet("color: #a29bfe;")
        self.touch_sub = QLabel("Определяет: Клик (<350мс), Удержание (>400мс), Долгое удержание (>1.2с)")
        self.touch_sub.setStyleSheet("color: #8892B0; font-size: 10px;")
        touch_title_box.addWidget(touch_title)
        touch_title_box.addWidget(self.touch_sub)

        self.touch_badge = QLabel("ОЖИДАНИЕ")
        self.touch_badge.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.touch_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 4px 12px; border-radius: 6px;")

        touch_header.addWidget(touch_icon)
        touch_header.addLayout(touch_title_box, 1)
        touch_header.addWidget(self.touch_badge)
        touch_layout.addLayout(touch_header)

        # Progress bar showing hold duration
        self.prog_touch = QProgressBar()
        self.prog_touch.setStyleSheet("""
            QProgressBar::chunk { 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #00cec9, stop:0.3 #0984e3, stop:0.7 #fdcb6e, stop:1 #e17055); 
                border-radius: 4px; 
            }
        """)
        self.prog_touch.setRange(0, 1500)
        self.prog_touch.setValue(0)
        self.prog_touch.setTextVisible(False)
        self.prog_touch.setFixedHeight(8)
        touch_layout.addWidget(self.prog_touch)

        # Event and Stats row
        touch_stats_row = QHBoxLayout()
        self.lbl_touch_event = QLabel("Событие: Ожидание первого касания")
        self.lbl_touch_event.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        self.lbl_touch_event.setStyleSheet("color: #00cec9;")

        self.lbl_touch_counter = QLabel("Касаний: 0 | Длительность: 0 мс")
        self.lbl_touch_counter.setStyleSheet("color: #8892B0; font-size: 10px;")

        self.btn_reset_counter = QPushButton("Сброс")
        self.btn_reset_counter.setStyleSheet("background-color: #242933; color: #8892B0; padding: 2px 8px; font-size: 10px;")
        self.btn_reset_counter.clicked.connect(self.on_reset_touch_counter)

        touch_stats_row.addWidget(self.lbl_touch_event, 1)
        touch_stats_row.addWidget(self.lbl_touch_counter)
        touch_stats_row.addWidget(self.btn_reset_counter)
        touch_layout.addLayout(touch_stats_row)

        root.addWidget(touch_card)

        # ─── 3. Card: 4 COB Filaments (PB2 / TIM1_CH3) ───
        fil_card = QFrame()
        fil_card.setProperty("class", "card")
        fil_layout = QVBoxLayout(fil_card)
        fil_layout.setSpacing(10)

        fil_header = QHBoxLayout()
        fil_title = QLabel("🔥 ВСЕ 4 COB ФИЛАМЕНТА (ШИМ TIM1_CH3 / PB2, Pad Coil 2)")
        fil_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        fil_title.setStyleSheet("color: #f39c12;")
        self.fil_badge = QLabel("ВЫКЛ (0%)")
        self.fil_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 3px 10px; border-radius: 5px; font-weight: bold;")
        fil_header.addWidget(fil_title)
        fil_header.addStretch()
        fil_header.addWidget(self.fil_badge)
        fil_layout.addLayout(fil_header)

        slider_fil_row = QHBoxLayout()
        self.slider_fil = QSlider(Qt.Orientation.Horizontal)
        self.slider_fil.setStyleSheet("""
            QSlider::sub-page:horizontal { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d35400, stop:1 #f39c12); border-radius: 4px; }
            QSlider::handle:horizontal { background: #ffffff; border: 3px solid #e67e22; width: 22px; margin-top: -7px; margin-bottom: -7px; border-radius: 11px; }
        """)
        self.slider_fil.setRange(0, 100)
        self.slider_fil.setValue(0)
        self.slider_fil.sliderPressed.connect(lambda: setattr(self, 'fil_dragging', True))
        self.slider_fil.sliderReleased.connect(self.on_fil_slider_released)
        self.slider_fil.valueChanged.connect(self.on_fil_slider_changed)

        self.lbl_fil_val = QLabel("0%")
        self.lbl_fil_val.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.lbl_fil_val.setFixedWidth(55)
        self.lbl_fil_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_fil_val.setStyleSheet("color: #f39c12;")

        self.btn_fil_toggle = QPushButton("ВЫКЛ ➔ ВКЛ")
        self.btn_fil_toggle.setStyleSheet("background-color: #d35400; color: white; padding: 8px 14px;")
        self.btn_fil_toggle.clicked.connect(self.on_fil_toggle_clicked)

        slider_fil_row.addWidget(self.slider_fil, 1)
        slider_fil_row.addWidget(self.lbl_fil_val)
        slider_fil_row.addWidget(self.btn_fil_toggle)
        fil_layout.addLayout(slider_fil_row)

        self.prog_fil = QProgressBar()
        self.prog_fil.setStyleSheet("QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #d35400, stop:1 #f39c12); border-radius: 5px; }")
        self.prog_fil.setRange(0, 100)
        self.prog_fil.setValue(0)
        self.prog_fil.setFormat("Текущая яркость: %v%")
        fil_layout.addWidget(self.prog_fil)

        fil_presets_row = QHBoxLayout()
        fil_presets_row.setSpacing(6)
        presets_fil = [(0, "🌑 Выкл"), (10, "10%"), (25, "25%"), (50, "50%"), (75, "75%"), (100, "🌟 100%")]
        for p, label in presets_fil:
            btn = QPushButton(label)
            btn.setStyleSheet("background-color: #242933; color: #E0E0E0; padding: 5px 8px; font-size: 11px;")
            btn.clicked.connect(lambda _, val=p: self.apply_fil_target(val))
            fil_presets_row.addWidget(btn)
        fil_layout.addLayout(fil_presets_row)
        root.addWidget(fil_card)

        # ─── 4. Card: FH8016 1-Wire Display (PA1 / TIM14 Non-Blocking) ───
        disp_card = QFrame()
        disp_card.setProperty("class", "card")
        disp_layout = QVBoxLayout(disp_card)
        disp_layout.setSpacing(10)

        disp_header = QHBoxLayout()
        disp_title = QLabel("📟 ДИСПЛЕЙ FH8016 (1-Wire PA1, Аппаратный TIM14, 0% CPU)")
        disp_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        disp_title.setStyleSheet("color: #3498db;")

        self.disp_badge = QLabel("АКТИВЕН")
        self.disp_badge.setStyleSheet("background-color: #2980b9; color: white; padding: 3px 10px; border-radius: 5px; font-weight: bold;")
        disp_header.addWidget(disp_title)
        disp_header.addStretch()
        disp_header.addWidget(self.disp_badge)
        disp_layout.addLayout(disp_header)

        disp_desc = QLabel("Кадр передается полностью в фоне по прерыванию TIM14 без блокирующих задержек delay_us().")
        disp_desc.setStyleSheet("color: #8892B0; font-size: 10px;")
        disp_layout.addWidget(disp_desc)

        # Mode Selector: Auto-sync vs Manual Test
        mode_row = QHBoxLayout()
        self.chk_auto_sync = QCheckBox("Автоматически синхронизировать с филаментами")
        self.chk_auto_sync.setChecked(True)
        self.chk_auto_sync.toggled.connect(self.on_auto_sync_toggled)
        self.chk_auto_sync.setStyleSheet("font-weight: bold; color: #3498db;")

        self.btn_disp_power = QPushButton("ВКЛ / ВЫКЛ экрана")
        self.btn_disp_power.setStyleSheet("background-color: #242933; color: #E0E0E0; padding: 6px 12px;")
        self.btn_disp_power.clicked.connect(self.on_disp_power_toggle)

        mode_row.addWidget(self.chk_auto_sync, 1)
        mode_row.addWidget(self.btn_disp_power)
        disp_layout.addLayout(mode_row)

        # Manual Test Row (Digits & Bars)
        ctrl_row = QHBoxLayout()
        lbl_pct = QLabel("Число (0..100):")
        self.slider_disp_pct = QSlider(Qt.Orientation.Horizontal)
        self.slider_disp_pct.setStyleSheet("""
            QSlider::sub-page:horizontal { background: #3498db; border-radius: 4px; }
            QSlider::handle:horizontal { background: #ffffff; border: 2px solid #2980b9; width: 18px; margin-top: -5px; margin-bottom: -5px; border-radius: 9px; }
        """)
        self.slider_disp_pct.setRange(0, 100)
        self.slider_disp_pct.setValue(50)
        self.slider_disp_pct.sliderPressed.connect(lambda: setattr(self, 'disp_dragging', True))
        self.slider_disp_pct.sliderReleased.connect(self.on_disp_slider_released)
        self.slider_disp_pct.valueChanged.connect(self.on_disp_slider_changed)

        self.lbl_disp_num = QLabel("50")
        self.lbl_disp_num.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.lbl_disp_num.setFixedWidth(40)
        self.lbl_disp_num.setStyleSheet("color: #3498db;")

        ctrl_row.addWidget(lbl_pct)
        ctrl_row.addWidget(self.slider_disp_pct, 1)
        ctrl_row.addWidget(self.lbl_disp_num)
        disp_layout.addLayout(ctrl_row)

        # Options Row: Bars, Lightning, Color
        opt_row = QHBoxLayout()
        opt_row.setSpacing(10)

        lbl_bars = QLabel("Шкала:")
        self.cmb_bars = QComboBox()
        self.cmb_bars.addItems(["0 делений", "1 деление", "2 деления", "3 деления", "4 деления"])
        self.cmb_bars.setCurrentIndex(2)
        self.cmb_bars.currentIndexChanged.connect(self.on_bars_changed)

        self.chk_lightning = QCheckBox("⚡ Молния")
        self.chk_lightning.toggled.connect(self.on_lightning_toggled)

        lbl_color = QLabel("Цвет фар:")
        self.cmb_color = QComboBox()
        self.cmb_color.addItems(COLOR_NAMES)
        self.cmb_color.setCurrentIndex(2) # Green
        self.cmb_color.currentIndexChanged.connect(self.on_color_changed)

        opt_row.addWidget(lbl_bars)
        opt_row.addWidget(self.cmb_bars)
        opt_row.addWidget(self.chk_lightning)
        opt_row.addWidget(lbl_color)
        opt_row.addWidget(self.cmb_color, 1)
        disp_layout.addLayout(opt_row)

        root.addWidget(disp_card)

        # ─── 5. Card: Test Board LEDs (PA0 / TIM1_CH1) ───
        led_card = QFrame()
        led_card.setProperty("class", "card")
        led_layout = QVBoxLayout(led_card)
        led_layout.setSpacing(8)

        led_header = QHBoxLayout()
        led_title = QLabel("💡 ТЕСТОВЫЕ ДИОДЫ НА ПЛАТЕ (ШИМ TIM1_CH1 / PA0, Pin 13)")
        led_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        led_title.setStyleSheet("color: #2ecc71;")
        self.led_badge = QLabel("ВЫКЛ (0%)")
        self.led_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 3px 10px; border-radius: 5px; font-weight: bold;")
        led_header.addWidget(led_title)
        led_header.addStretch()
        led_header.addWidget(self.led_badge)
        led_layout.addLayout(led_header)

        slider_led_row = QHBoxLayout()
        self.slider_led = QSlider(Qt.Orientation.Horizontal)
        self.slider_led.setStyleSheet("""
            QSlider::sub-page:horizontal { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #27ae60, stop:1 #2ecc71); border-radius: 4px; }
            QSlider::handle:horizontal { background: #ffffff; border: 3px solid #27ae60; width: 22px; margin-top: -7px; margin-bottom: -7px; border-radius: 11px; }
        """)
        self.slider_led.setRange(0, 100)
        self.slider_led.setValue(0)
        self.slider_led.sliderPressed.connect(lambda: setattr(self, 'led_dragging', True))
        self.slider_led.sliderReleased.connect(self.on_led_slider_released)
        self.slider_led.valueChanged.connect(self.on_led_slider_changed)

        self.lbl_led_val = QLabel("0%")
        self.lbl_led_val.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.lbl_led_val.setFixedWidth(55)
        self.lbl_led_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_led_val.setStyleSheet("color: #2ecc71;")

        self.btn_led_toggle = QPushButton("ВЫКЛ ➔ ВКЛ")
        self.btn_led_toggle.setStyleSheet("background-color: #27ae60; color: white; padding: 8px 14px;")
        self.btn_led_toggle.clicked.connect(self.on_led_toggle_clicked)

        slider_led_row.addWidget(self.slider_led, 1)
        slider_led_row.addWidget(self.lbl_led_val)
        slider_led_row.addWidget(self.btn_led_toggle)
        led_layout.addLayout(slider_led_row)

        root.addWidget(led_card)

        # ─── 6. Card: Battery & C60H Charging (Internal ADC VREFINT + PB5) ───
        bat_card = QFrame()
        bat_card.setProperty("class", "card")
        bat_layout = QVBoxLayout(bat_card)
        bat_layout.setSpacing(8)

        bat_header = QHBoxLayout()
        bat_title = QLabel("🔋 АККУМУЛЯТОР И ЗАРЯДКА (АЦП Bandgap 1.20В + C60H на PB5)")
        bat_title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        bat_title.setStyleSheet("color: #00d2d3;")
        self.bat_badge = QLabel("ОЖИДАНИЕ ДАННЫХ")
        self.bat_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 3px 10px; border-radius: 5px; font-weight: bold;")
        bat_header.addWidget(bat_title)
        bat_header.addStretch()
        bat_header.addWidget(self.bat_badge)
        bat_layout.addLayout(bat_header)

        bat_info_row = QHBoxLayout()
        self.lbl_bat_voltage = QLabel("0.00 В")
        self.lbl_bat_voltage.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.lbl_bat_voltage.setStyleSheet("color: #00d2d3;")

        self.lbl_bat_details = QLabel("АЦП raw: 0 | Пин PB5 (C60H CHRG): HIGH")
        self.lbl_bat_details.setFont(QFont("Segoe UI", 10))
        self.lbl_bat_details.setStyleSheet("color: #8892B0;")

        bat_info_row.addWidget(self.lbl_bat_voltage)
        bat_info_row.addSpacing(15)
        bat_info_row.addWidget(self.lbl_bat_details, 1)
        bat_layout.addLayout(bat_info_row)

        self.prog_bat = QProgressBar()
        self.prog_bat.setStyleSheet("""
            QProgressBar::chunk { 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #e74c3c, stop:0.3 #f39c12, stop:0.7 #2ecc71, stop:1 #00d2d3); 
                border-radius: 5px; 
            }
        """)
        self.prog_bat.setRange(0, 100)
        self.prog_bat.setValue(0)
        self.prog_bat.setFormat("Заряд АКБ: %v%")
        bat_layout.addWidget(self.prog_bat)

        bat_note = QLabel("ℹ️ При питании от программатора (3.3V) АЦП показывает ~3.30V. Для проверки реального АКБ и Type-C отключите линию 3.3V.")
        bat_note.setStyleSheet("color: #57606f; font-size: 10px;")
        bat_layout.addWidget(bat_note)

        root.addWidget(bat_card)

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
            self.apply_fil_target(0)
        else:
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
            self.apply_led_target(0)
        else:
            target = self.mem_led_saved if self.mem_led_saved >= 1 else 50
            self.apply_led_target(target)

    # ─── Display Handlers ───
    def on_auto_sync_toggled(self, checked):
        self.worker.set_disp_param('DISP_AUTO', 1 if checked else 0)

    def on_disp_power_toggle(self):
        cur = self.slider_disp_pct.value()
        self.worker.set_disp_param('DISP_AUTO', 0)
        self.chk_auto_sync.setChecked(False)
        self.worker.set_disp_param('DISP_POWER', 1)

    def on_disp_slider_released(self):
        self.disp_dragging = False
        val = self.slider_disp_pct.value()
        self.worker.set_disp_param('DISP_AUTO', 0)
        self.chk_auto_sync.setChecked(False)
        self.worker.set_disp_param('DISP_PERCENT', val)

    def on_disp_slider_changed(self, value):
        self.lbl_disp_num.setText(str(value))
        if self.disp_dragging:
            self.worker.set_disp_param('DISP_AUTO', 0)
            self.chk_auto_sync.setChecked(False)
            self.worker.set_disp_param('DISP_PERCENT', value)

    def on_bars_changed(self, index):
        self.worker.set_disp_param('DISP_AUTO', 0)
        self.chk_auto_sync.setChecked(False)
        self.worker.set_disp_param('DISP_BARS', index)

    def on_lightning_toggled(self, checked):
        self.worker.set_disp_param('DISP_AUTO', 0)
        self.chk_auto_sync.setChecked(False)
        self.worker.set_disp_param('DISP_ICONS', 0x02 if checked else 0)

    def on_color_changed(self, index):
        self.worker.set_disp_param('DISP_AUTO', 0)
        self.chk_auto_sync.setChecked(False)
        self.worker.set_disp_param('DISP_COLOR', index)

    def on_reset_touch_counter(self):
        self.touch_clicks_count = 0
        self.prog_touch.setValue(0)
        self.lbl_touch_counter.setText("Касаний: 0 | Длительность: 0 мс")
        self.lbl_touch_event.setText("Событие: Счётчик сброшен")
        self.lbl_touch_event.setStyleSheet("color: #8892B0; font-weight: bold;")

    # ─── Live Telemetry ───
    def on_telemetry_updated(self, telem):
        self.cur_fil_state = telem['fil_state']
        self.mem_fil_saved = telem['fil_saved']
        self.cur_led_state = telem['led_state']
        self.mem_led_saved = telem['led_saved']

        # ─── Touch Sensor Real-Time Diagnostics ───
        now_sec = time.time()
        raw = telem['touch_raw']

        # 1. Edge: 0 -> 1 (Touch Down)
        if raw and not self.last_touch_raw:
            self.touch_press_start = now_sec
            self.touch_clicks_count += 1
            if (now_sec - self.last_release_time) < 0.38:
                self.click_train += 1
            else:
                self.click_train = 1
            self.lbl_touch_event.setText(f"Событие: 👆 Нажатие #{self.click_train}...")
            self.lbl_touch_event.setStyleSheet("color: #00cec9; font-weight: bold;")

        # 2. Level: 1 (Holding / Pressed)
        if raw:
            press_duration_ms = int((now_sec - self.touch_press_start) * 1000)
            self.prog_touch.setValue(min(1500, press_duration_ms))
            self.lbl_touch_counter.setText(f"Касаний: {self.touch_clicks_count} | Длительность: {press_duration_ms} мс")
            self.touch_badge.setText(f"👆 ЗАЖАТО ({press_duration_ms} мс)")
            if press_duration_ms >= 1200:
                self.touch_badge.setStyleSheet("background-color: #d63031; color: #ffffff; padding: 4px 12px; border-radius: 6px; font-weight: bold;")
                self.lbl_touch_event.setText(f"Событие: 🔒 ДОЛГОЕ УДЕРЖАНИЕ ({press_duration_ms} мс)")
                self.lbl_touch_event.setStyleSheet("color: #e17055; font-weight: bold;")
            elif press_duration_ms >= 350:
                self.touch_badge.setStyleSheet("background-color: #e67e22; color: #ffffff; padding: 4px 12px; border-radius: 6px; font-weight: bold;")
                self.lbl_touch_event.setText(f"Событие: 🔆 ДИММИРОВАНИЕ ({press_duration_ms} мс)")
                self.lbl_touch_event.setStyleSheet("color: #fdcb6e; font-weight: bold;")
            else:
                self.touch_badge.setStyleSheet("background-color: #27ae60; color: #ffffff; padding: 4px 12px; border-radius: 6px; font-weight: bold;")

        # 3. Edge: 1 -> 0 (Release / Touch Up)
        elif not raw and self.last_touch_raw:
            release_duration_ms = int((now_sec - self.touch_press_start) * 1000)
            self.last_release_time = now_sec
            self.prog_touch.setValue(0)
            self.lbl_touch_counter.setText(f"Касаний: {self.touch_clicks_count} | Длительность: {release_duration_ms} мс")
            self.touch_badge.setText("ОЖИДАНИЕ")
            self.touch_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 4px 12px; border-radius: 6px;")

            if release_duration_ms < 350:
                if self.click_train == 1:
                    self.lbl_touch_event.setText(f"Событие: 🎯 ОДИНОЧНЫЙ КЛИК ({release_duration_ms} мс)")
                    self.lbl_touch_event.setStyleSheet("color: #2ecc71; font-weight: bold;")
                elif self.click_train == 2:
                    self.lbl_touch_event.setText(f"Событие: ⚡ ДВОЙНОЙ КЛИК! ({release_duration_ms} мс)")
                    self.lbl_touch_event.setStyleSheet("color: #fdcb6e; font-weight: bold;")
                elif self.click_train == 3:
                    self.lbl_touch_event.setText(f"Событие: 🔥 ТРОЙНОЙ КЛИК! (3 клика)")
                    self.lbl_touch_event.setStyleSheet("color: #e67e22; font-weight: bold;")
                elif self.click_train == 4:
                    self.lbl_touch_event.setText(f"Событие: 💥 ЧЕТВЕРНОЙ КЛИК! (4 клика)")
                    self.lbl_touch_event.setStyleSheet("color: #e74c3c; font-weight: bold;")
                elif self.click_train == 5:
                    self.lbl_touch_event.setText(f"Событие: 🚀 ПЯТИКРАТНЫЙ КЛИК! (5 кликов)")
                    self.lbl_touch_event.setStyleSheet("color: #9b59b6; font-weight: bold;")
                else:
                    self.lbl_touch_event.setText(f"Событие: 🌟 СЕРИЯ КЛИКОВ: {self.click_train} раз!")
                    self.lbl_touch_event.setStyleSheet("color: #1abc9c; font-weight: bold;")
            elif release_duration_ms < 1200:
                self.lbl_touch_event.setText(f"Событие: 🔆 ДИММИРОВАНИЕ ЗАВЕРШЕНО ({release_duration_ms} мс)")
                self.lbl_touch_event.setStyleSheet("color: #f39c12; font-weight: bold;")
            else:
                self.lbl_touch_event.setText(f"Событие: 🔒 ДОЛГИЙ КЛИК ЗАВЕРШЕН ({release_duration_ms} мс)")
                self.lbl_touch_event.setStyleSheet("color: #e74c3c; font-weight: bold;")

        self.last_touch_raw = raw

        # Update Filaments UI
        if not self.fil_dragging:
            if abs(self.slider_fil.value() - telem['fil_target']) > 1:
                self.slider_fil.setValue(telem['fil_target'])

        self.prog_fil.setValue(telem['fil_curr'])

        if telem['fil_state'] == 0 and telem['fil_curr'] == 0:
            self.fil_badge.setText("ВЫКЛ (0%)")
            self.fil_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 3px 10px; border-radius: 5px; font-weight: bold;")
            self.btn_fil_toggle.setText(f"ВКЛ ({telem['fil_saved']}%)")
            self.btn_fil_toggle.setStyleSheet("background-color: #27ae60; color: white; padding: 8px 14px;")
        else:
            self.fil_badge.setText(f"СВЕТИТ {telem['fil_curr']}%")
            self.fil_badge.setStyleSheet("background-color: #d35400; color: white; padding: 3px 10px; border-radius: 5px; font-weight: bold;")
            self.btn_fil_toggle.setText("ВЫКЛ (0%)")
            self.btn_fil_toggle.setStyleSheet("background-color: #c0392b; color: white; padding: 8px 14px;")

        # Update Display UI
        if telem['disp_power']:
            self.disp_badge.setText(f"СВЕТИТ: {telem['disp_pct']}% (Шкала {telem['disp_bars']}/4)")
            self.disp_badge.setStyleSheet("background-color: #27ae60; color: white; padding: 3px 10px; border-radius: 5px; font-weight: bold;")
        else:
            self.disp_badge.setText("СОН (ВЫКЛ)")
            self.disp_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 3px 10px; border-radius: 5px; font-weight: bold;")

        if not self.disp_dragging and telem['disp_auto']:
            self.slider_disp_pct.setValue(telem['disp_pct'])
            self.cmb_bars.setCurrentIndex(min(4, telem['disp_bars']))

        # Update Board LEDs UI
        if not self.led_dragging:
            if abs(self.slider_led.value() - telem['led_target']) > 1:
                self.slider_led.setValue(telem['led_target'])

        if telem['led_state'] == 0 and telem['led_curr'] == 0:
            self.led_badge.setText("ВЫКЛ (0% - Полный ноль)")
            self.led_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 3px 10px; border-radius: 5px; font-weight: bold;")
            self.btn_led_toggle.setText(f"ВКЛ ({telem['led_saved']}%)")
            self.btn_led_toggle.setStyleSheet("background-color: #27ae60; color: white; padding: 8px 14px;")
        else:
            self.led_badge.setText(f"СВЕТИТ {telem['led_curr']}%")
            self.led_badge.setStyleSheet("background-color: #27ae60; color: white; padding: 3px 10px; border-radius: 5px; font-weight: bold;")
            self.btn_led_toggle.setText("ВЫКЛ (0%)")
            self.btn_led_toggle.setStyleSheet("background-color: #c0392b; color: white; padding: 8px 14px;")

        # Update Battery & Charge UI
        bat_mv = telem.get('bat_mv', 0)
        bat_pct = telem.get('bat_pct', 0)
        bat_adc = telem.get('bat_adc', 0)
        chrg_pin = telem.get('chrg_pin', 1)
        is_charging = telem.get('is_charging', 0)

        v_float = bat_mv / 1000.0
        self.lbl_bat_voltage.setText(f"{v_float:.2f} В ({bat_mv} мВ)")
        self.prog_bat.setValue(min(100, max(0, bat_pct)))
        self.prog_bat.setFormat(f"Заряд: {bat_pct}% ({v_float:.2f} В)")

        pin_str = "0V (LOW / ЗАРЯДКА)" if chrg_pin == 0 else "3.3V (HIGH / РАЗРЯД)"
        self.lbl_bat_details.setText(f"АЦП raw: {bat_adc} | Пин PB5 (C60H CHRG): {pin_str}")

        if is_charging or chrg_pin == 0:
            self.bat_badge.setText("⚡ ИДЕТ ЗАРЯДКА Type-C")
            self.bat_badge.setStyleSheet("background-color: #0984e3; color: white; padding: 3px 10px; border-radius: 5px; font-weight: bold;")
        else:
            if bat_pct > 20:
                self.bat_badge.setText(f"🔋 РАБОТА ОТ АКБ ({bat_pct}%)")
                self.bat_badge.setStyleSheet("background-color: #27ae60; color: white; padding: 3px 10px; border-radius: 5px; font-weight: bold;")
            elif bat_pct > 0:
                self.bat_badge.setText(f"⚠️ АКБ РАЗРЯЖЕН ({bat_pct}%)")
                self.bat_badge.setStyleSheet("background-color: #d63031; color: white; padding: 3px 10px; border-radius: 5px; font-weight: bold;")
            else:
                self.bat_badge.setText("ОЖИДАНИЕ ДАННЫХ")
                self.bat_badge.setStyleSheet("background-color: #242933; color: #8892B0; padding: 3px 10px; border-radius: 5px; font-weight: bold;")

    def closeEvent(self, event):
        self.worker.stop()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
