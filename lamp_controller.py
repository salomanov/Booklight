import sys
import time
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QSlider, 
                             QGroupBox, QCheckBox, QComboBox, QGridLayout)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from pyocd.core.helpers import ConnectHelper

# ─── Адреса RAM из firmware.map ──────────────────────────────────────────────
ADDR_DISP_POWER = 0x20000000
ADDR_DISP_COLOR = 0x20000004
ADDR_DISP_BARS  = 0x20000008
ADDR_DISP_NUM   = 0x2000000c
ADDR_BRIGHTNESS = 0x20000010
ADDR_FLAG       = 0x20000014

ADDR_V_CHARGE   = 0x20000038
ADDR_CURRENT_MV = 0x2000003c
ADDR_V_BATT_MV  = 0x20000040
ADDR_DISP_ICONS = 0x20000044
ADDR_TOUCH      = 0x20000048

TARGET = 'py32f002bx5'

class SwdWorker(QThread):
    connection_changed = pyqtSignal(bool, str)
    state_updated      = pyqtSignal(bool, int, int, int) # flag, br, adc, is_charging

    def __init__(self):
        super().__init__()
        self.running = True
        self.pending = []

    def write(self, addr, val):
        self.pending.append((addr, val))

    def stop(self):
        self.running = False
        self.wait()

    def run(self):
        connected = False
        session   = None
        target    = None

        while self.running:
            try:
                if session is None:
                    session = ConnectHelper.session_with_chosen_probe(
                        target_override=TARGET,
                        connect_mode='attach',
                        options={'auto_unlock': False}
                    )
                    session.open()
                    target = session.target
                    connected = True
                    self.connection_changed.emit(True, "Подключено")

                while self.pending:
                    addr, val = self.pending.pop(0)
                    target.write_memory(addr, val)
                    target.resume()

                try:
                    flag = target.read_memory(ADDR_FLAG)
                    br   = target.read_memory(ADDR_BRIGHTNESS)
                    mv   = target.read_memory(ADDR_CURRENT_MV)
                    chg  = target.read_memory(ADDR_V_CHARGE)
                    self.state_updated.emit(flag != 0, br, mv, chg)
                except Exception:
                    pass

                self.msleep(50)
            except Exception as e:
                if connected:
                    connected = False
                    self.connection_changed.emit(False, "Ошибка: " + str(e))
                if session:
                    try:
                        session.close()
                    except Exception:
                        pass
                    session = None
                    target  = None
                self.msleep(1500)

        if session:
            try:
                session.close()
            except Exception:
                pass

    def stop(self):
        self.running = False
        self.wait(3000)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BookLight — Dashboard v2")
        self.setFixedSize(560, 750)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(10)

        # ─── Статус ───
        status_row = QHBoxLayout()
        self.dot = QLabel("●")
        self.dot.setFont(QFont("Segoe UI", 15))
        self.dot.setStyleSheet("color: #e74c3c;")
        self.status_lbl = QLabel("Поиск программатора...")
        self.status_lbl.setFont(QFont("Segoe UI", 10))
        status_row.addWidget(self.dot)
        status_row.addWidget(self.status_lbl, 1)
        root.addLayout(status_row)

        # ─── Экран (Vape Display) ───
        disp_group = QGroupBox("Эмуляция дисплея (FH8016)")
        disp_group.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        disp_layout = QVBoxLayout(disp_group)

        # Кнопка включения дисплея
        self.chk_disp_power = QCheckBox("ДИСПЛЕЙ ВКЛЮЧЕН")
        self.chk_disp_power.setChecked(True)
        self.chk_disp_power.stateChanged.connect(self.on_power_change)
        disp_layout.addWidget(self.chk_disp_power)

        # Цифры (LCD)
        lcd_row = QHBoxLayout()
        lcd_lbl = QLabel("Значение на экране (0-100):")
        self.num_slider = QSlider(Qt.Orientation.Horizontal)
        self.num_slider.setRange(0, 100)
        self.num_slider.setValue(88)
        self.num_slider.valueChanged.connect(self.on_num_change)
        self.num_val_lbl = QLabel("88")
        self.num_val_lbl.setFixedWidth(30)
        lcd_row.addWidget(lcd_lbl)
        lcd_row.addWidget(self.num_slider)
        lcd_row.addWidget(self.num_val_lbl)
        disp_layout.addLayout(lcd_row)

        # Иконки / Статус
        icons_row = QHBoxLayout()
        self.chk_light = QCheckBox("🔌 Подключить зарядку (USB)")
        self.chk_light.stateChanged.connect(self.on_charge_change)
        icons_row.addWidget(self.chk_light)
        disp_layout.addLayout(icons_row)

        # Деления батареи
        bars_row = QHBoxLayout()
        bars_lbl = QLabel("Деления (0-4):")
        self.bars_slider = QSlider(Qt.Orientation.Horizontal)
        self.bars_slider.setRange(0, 4)
        self.bars_slider.setValue(4)
        self.bars_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.bars_slider.setTickInterval(1)
        self.bars_slider.valueChanged.connect(self.on_bars_change)
        self.bars_val_lbl = QLabel("4")
        self.bars_val_lbl.setFixedWidth(30)
        bars_row.addWidget(bars_lbl)
        bars_row.addWidget(self.bars_slider)
        bars_row.addWidget(self.bars_val_lbl)
        disp_layout.addLayout(bars_row)

        # Цвет фар
        color_row = QHBoxLayout()
        color_lbl = QLabel("Цвет фар:")
        self.color_combo = QComboBox()
        self.color_combo.addItems(["Выкл", "Красный", "Зеленый", "Синий", "Бирюзовый", "Пурпурный", "Желтый", "Белый"])
        self.color_combo.setCurrentIndex(2) # Зеленый
        self.color_combo.currentIndexChanged.connect(self.on_color_change)
        color_row.addWidget(color_lbl)
        color_row.addWidget(self.color_combo, 1)
        disp_layout.addLayout(color_row)

        root.addWidget(disp_group)

        # ─── Физическая лампа ───
        lamp_group = QGroupBox("Лампа и Сенсоры (Обратная связь от MCU)")
        lamp_group.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        lamp_layout = QVBoxLayout(lamp_group)
        self.state_lbl = QLabel("Статус: ОЖИДАНИЕ")
        self.state_lbl.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self.state_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lamp_layout.addWidget(self.state_lbl)
        
        self.adc_lbl = QLabel("АЦП Батареи: -- мВ")
        self.adc_lbl.setFont(QFont("Segoe UI", 10))
        self.adc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lamp_layout.addWidget(self.adc_lbl)
        
        self.chg_lbl = QLabel("Статус зарядки: --")
        self.chg_lbl.setFont(QFont("Segoe UI", 10))
        self.chg_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lamp_layout.addWidget(self.chg_lbl)
        
        root.addWidget(lamp_group)

        # ─── Кнопка ───
        btn_group = QGroupBox("Управление кнопкой")
        btn_group.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        btn_layout = QVBoxLayout(btn_group)
        self.btn = QPushButton("СЕНСОР (TTP223)")
        self.btn.setFixedHeight(80)
        self.btn.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn.setEnabled(False)
        self.btn.pressed.connect(self.on_press)
        self.btn.released.connect(self.on_release)
        btn_layout.addWidget(self.btn)
        root.addWidget(btn_group)

        root.addStretch()
        self._apply_theme()

        self.worker = SwdWorker()
        self.worker.connection_changed.connect(self.on_connection)
        self.worker.state_updated.connect(self.on_state_update)
        self.worker.start()

    # ─── Логика ───
    def on_power_change(self):
        self.worker.write(ADDR_DISP_POWER, 1 if self.chk_disp_power.isChecked() else 0)

    def on_num_change(self, val):
        self.num_val_lbl.setText(str(val))
        self.worker.write(ADDR_DISP_NUM, val)
        self.worker.write(ADDR_BRIGHTNESS, val)

    def on_charge_change(self):
        self.worker.write(ADDR_V_CHARGE, 1 if self.chk_light.isChecked() else 0)

    def on_bars_change(self, val):
        self.bars_val_lbl.setText(str(val))
        # Переводим 0..4 деления в милливольты для обмана прошивки
        mv_map = {4: 4100, 3: 3900, 2: 3700, 1: 3400, 0: 3100}
        self.worker.write(ADDR_V_BATT_MV, mv_map[val])

    def on_color_change(self, index):
        self.worker.write(ADDR_DISP_COLOR, index)

    def on_press(self):
        self.btn.setStyleSheet("QPushButton { background: #f39c12; color: white; border-radius: 10px; }")
        self.worker.write(ADDR_TOUCH, 1)

    def on_release(self):
        self.btn.setStyleSheet("QPushButton { background: #1b1e26; border: 2px solid #f39c12; color: #f39c12; border-radius: 10px; }")
        self.worker.write(ADDR_TOUCH, 0)

    def on_connection(self, connected, msg):
        self.status_lbl.setText(msg)
        if connected:
            self.dot.setStyleSheet("color: #2ecc71;")
            self.btn.setEnabled(True)
            self.on_release()
        else:
            self.dot.setStyleSheet("color: #e74c3c;")
            self.btn.setEnabled(False)

    def on_state_update(self, lamp_on, brightness, adc_mv, is_charging):
        if lamp_on:
            self.state_lbl.setText(f"Лампа: ВКЛ ({brightness}%)")
            self.state_lbl.setStyleSheet("color: #f39c12;")
        else:
            self.state_lbl.setText("Лампа: ВЫКЛ")
            self.state_lbl.setStyleSheet("color: #8c96ab;")
            
        self.adc_lbl.setText(f"АЦП Батареи: {adc_mv} мВ")
        self.chg_lbl.setText(f"Статус зарядки: {'Подключена ⚡' if is_charging else 'Отключена'}")

    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #12141a; color: #e0e4ed; }
            QGroupBox { border: 1px solid #2b303d; border-radius: 8px; margin-top: 10px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #8fa0b0; }
            QSlider::groove:horizontal { background: #2b303d; height: 8px; border-radius: 4px; }
            QSlider::handle:horizontal { background: #f39c12; width: 16px; margin: -4px 0; border-radius: 8px; }
            QCheckBox { spacing: 8px; font-size: 13px; }
            QCheckBox::indicator { width: 18px; height: 18px; border-radius: 4px; border: 1px solid #3a3d4a; }
            QCheckBox::indicator:checked { background: #f39c12; }
            QComboBox { background: #1b1e26; border: 1px solid #3a3d4a; border-radius: 4px; padding: 4px; }
            QPushButton:disabled { background: #2a2d38; border-color: #3a3d4a; color: #555; }
        """)

    def closeEvent(self, event):
        self.worker.stop()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    w = MainWindow()
    w.show()
    sys.exit(app.exec())
