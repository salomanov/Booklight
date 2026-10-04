# -*- coding: utf-8 -*-
"""
DM02i Display Pinout Mapper (Ручная прозвонка мультиметром 1-6)
Позволяет быстро внести номера контактов (1..6) для всех элементов экрана.
"""
import sys
import os
import json
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QFrame, QScrollArea, QMessageBox, QGroupBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor

MAP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dm02i_multimeter_map.json")

# Полный перечень всех элементов экрана DM02i V03
ALL_ELEMENTS = [
    # --- НЕ ХВАТАЕТ (ПРИОРИТЕТ ДЛЯ ПРОЗВОНКИ) ---
    {"id": "drop",        "name": "💧 Капля жидкости",             "cat": "MISSING", "known_mcu": "Не найдено"},
    {"id": "bar1",        "name": "Полоска жидкости 1 (Нижняя)",    "cat": "MISSING", "known_mcu": "Не найдено"},
    {"id": "percent",     "name": "% (Знак процента)",              "cat": "MISSING", "known_mcu": "Не найдено"},
    {"id": "d1_e",        "name": "Цифра 1 (Десятки) - Сегмент E",   "cat": "MISSING", "known_mcu": "Не найдено"},
    {"id": "d2_b",        "name": "Цифра 2 (Единицы) - Сегмент B",   "cat": "MISSING", "known_mcu": "Не найдено"},
    {"id": "d2_c",        "name": "Цифра 2 (Единицы) - Сегмент C",   "cat": "MISSING", "known_mcu": "Не найдено"},
    {"id": "hundred_top", "name": "Сотня '1' (Верхняя палочка)",    "cat": "MISSING", "known_mcu": "Не найдено"},
    {"id": "boost_o1",    "name": "BOOST - Первая буква O (O₁)",     "cat": "MISSING", "known_mcu": "Не найдено"},
    {"id": "boost_o2",    "name": "BOOST - Вторая буква O (O₂)",    "cat": "MISSING", "known_mcu": "Не найдено"},
    {"id": "boost_s",     "name": "BOOST - Буква S",                "cat": "MISSING", "known_mcu": "Не найдено"},
    {"id": "boost_d1",    "name": "BOOST - Диод 1 (Левый)",         "cat": "MISSING", "known_mcu": "Не найдено"},
    {"id": "boost_d3",    "name": "BOOST - Диод 3",                 "cat": "MISSING", "known_mcu": "Не найдено"},
    {"id": "boost_frame", "name": "Ободок / Рамка BOOST",           "cat": "MISSING", "known_mcu": "Не найдено"},

    # --- УЖЕ НАЙДЕНЫ В ЧИПЕ (19 ШТУК) ---
    {"id": "lightning",   "name": "⚡ Молния (Индикатор заряда)",    "cat": "KNOWN",   "known_mcu": "PB1 (+) -> PB5 (-)"},
    {"id": "bar3",        "name": "Полоска жидкости 3 (Верхняя)",   "cat": "KNOWN",   "known_mcu": "PB2 (+) -> PB5 (-)"},
    {"id": "bar2",        "name": "Полоска жидкости 2 (Средняя)",   "cat": "KNOWN",   "known_mcu": "PB3 (+) -> PB5 (-)"},
    {"id": "hundred_bot", "name": "Сотня '1' (Нижняя палочка)",     "cat": "KNOWN",   "known_mcu": "PB0 (+) -> PB5 (-)"},

    {"id": "d1_a",        "name": "Цифра 1 (Десятки) - Сегмент A",   "cat": "KNOWN",   "known_mcu": "PB1 (+) -> PB0 (-)"},
    {"id": "d1_b",        "name": "Цифра 1 (Десятки) - Сегмент B",   "cat": "KNOWN",   "known_mcu": "PB2 (+) -> PB0 (-)"},
    {"id": "d1_c",        "name": "Цифра 1 (Десятки) - Сегмент C",   "cat": "KNOWN",   "known_mcu": "PB3 (+) -> PB0 (-)"},
    {"id": "d1_d",        "name": "Цифра 1 (Десятки) - Сегмент D",   "cat": "KNOWN",   "known_mcu": "PB5 (+) -> PB0 (-)"},
    {"id": "d1_f",        "name": "Цифра 1 (Десятки) - Сегмент F",   "cat": "KNOWN",   "known_mcu": "PB0 (+) -> PB1 (-)"},
    {"id": "d1_g",        "name": "Цифра 1 (Десятки) - Сегмент G",   "cat": "KNOWN",   "known_mcu": "PB2 (+) -> PB1 (-)"},

    {"id": "d2_a",        "name": "Цифра 2 (Единицы) - Сегмент A",   "cat": "KNOWN",   "known_mcu": "PB3 (+) -> PB1 (-)"},
    {"id": "d2_d",        "name": "Цифра 2 (Единицы) - Сегмент D",   "cat": "KNOWN",   "known_mcu": "PB0 (+) -> PB2 (-)"},
    {"id": "d2_e",        "name": "Цифра 2 (Единицы) - Сегмент E",   "cat": "KNOWN",   "known_mcu": "PB1 (+) -> PB2 (-)"},
    {"id": "d2_f",        "name": "Цифра 2 (Единицы) - Сегмент F",   "cat": "KNOWN",   "known_mcu": "PB3 (+) -> PB2 (-)"},
    {"id": "d2_g",        "name": "Цифра 2 (Единицы) - Сегмент G",   "cat": "KNOWN",   "known_mcu": "PB5 (+) -> PB2 (-)"},

    {"id": "boost_b",     "name": "BOOST - Буква B",                "cat": "KNOWN",   "known_mcu": "PB0 (+) -> PB3 (-)"},
    {"id": "boost_t",     "name": "BOOST - Буква T",                "cat": "KNOWN",   "known_mcu": "PB1 (+) -> PB3 (-)"},
    {"id": "boost_d2",    "name": "BOOST - Диод 2",                 "cat": "KNOWN",   "known_mcu": "PB2 (+) -> PB3 (-)"},
    {"id": "boost_d4",    "name": "BOOST - Диод 4",                 "cat": "KNOWN",   "known_mcu": "PB5 (+) -> PB3 (-)"},
]

CONTACT_CHOICES = ["--", "Контакт 1", "Контакт 2", "Контакт 3", "Контакт 4", "Контакт 5", "Контакт 6"]

class PinoutMapper(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("DM02i Pinout Mapper - Прозвонка дисплея мультиметром (Контакты 1..6)")
        self.resize(1180, 820)
        self.data_map = {}
        self.load_data()

        self.init_ui()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # 1. Header Banner & Instructions
        header = QFrame()
        header.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1e1b4b, stop:1 #0f172a);
            border: 2px solid #6366f1; border-radius: 10px; padding: 10px;
        """)
        h_layout = QVBoxLayout(header)
        h_title = QLabel("КАРТА ПРОЗВОНКИ ДИСПЛЕЯ МУЛЬТИМЕТРОМ (КОНТАКТЫ 1 .. 6)")
        h_title.setStyleSheet("color: #a5b4fc; font-size: 16px; font-weight: bold;")
        h_layout.addWidget(h_title)

        h_desc = QLabel(
            "<b>Как прозванивать:</b><br>"
            "1. Переключите мультиметр в <b>режим проверки диодов</b> (значок диода <b>->|-</b>).<br>"
            "2. <b>Красный щуп</b> = ПЛЮС (+), <b>Чёрный щуп</b> = МИНУС (-).<br>"
            "3. Касайтесь контактов гребёнки дисплея (1..6). Светодиод на экране загорится прямо под щупами!<br>"
            "4. Выбирайте в выпадающих списках, какой контакт был <b>+</b> и какой <b>-</b>. Сохранение происходит автоматически!"
        )
        h_desc.setStyleSheet("color: #cbd5e1; font-size: 12px; line-height: 1.4;")
        h_layout.addWidget(h_desc)
        layout.addWidget(header)

        # 2. Table of Elements
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Статус", "Элемент экрана", "В чипе (MCU)", "ПЛЮС (+) Красный щуп", "МИНУС (-) Чёрный щуп", "Очистить"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setStyleSheet("""
            QTableWidget {
                background: #090d16;
                color: #f8fafc;
                gridline-color: #1e293b;
                border: 1px solid #334155;
                border-radius: 8px;
                font-size: 13px;
            }
            QHeaderView::section {
                background: #1e293b;
                color: #38bdf8;
                font-weight: bold;
                padding: 6px;
                border: 1px solid #0f172a;
            }
        """)
        layout.addWidget(self.table)

        self.populate_table()

        # 3. Bottom Controls
        bot_bar = QHBoxLayout()
        self.lbl_summary = QLabel("Заполнено: 0 / 32")
        self.lbl_summary.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 14px;")
        bot_bar.addWidget(self.lbl_summary)

        bot_bar.addStretch()

        btn_save = QPushButton("💾 Сохранить и сгенерировать C-драйвер")
        btn_save.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #059669, stop:1 #10b981);
            color: white; font-weight: bold; font-size: 13px; padding: 8px 16px; border-radius: 6px;
        """)
        btn_save.clicked.connect(self.generate_c_driver)
        bot_bar.addWidget(btn_save)

        layout.addLayout(bot_bar)

        self.update_summary()

    def populate_table(self):
        self.table.setRowCount(len(ALL_ELEMENTS))
        self.combos = {}

        for row, el in enumerate(ALL_ELEMENTS):
            el_id = el["id"]
            cat = el["cat"]

            # 0. Status badge
            if cat == "MISSING":
                lbl_st = QLabel(" [🔥 ИЩЕМ] ")
                lbl_st.setStyleSheet("color: #f43f5e; font-weight: bold;")
            else:
                lbl_st = QLabel(" [✓ В ЧИПЕ] ")
                lbl_st.setStyleSheet("color: #10b981; font-weight: bold;")
            lbl_st.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setCellWidget(row, 0, lbl_st)

            # 1. Element Name
            item_name = QTableWidgetItem(el["name"])
            if cat == "MISSING":
                item_name.setForeground(QColor("#fbcfe8"))
                item_name.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            else:
                item_name.setForeground(QColor("#e2e8f0"))
            self.table.setItem(row, 1, item_name)

            # 2. Known MCU pair
            item_mcu = QTableWidgetItem(el["known_mcu"])
            item_mcu.setForeground(QColor("#94a3b8"))
            self.table.setItem(row, 2, item_mcu)

            # 3. PLUS ComboBox
            cb_plus = QComboBox()
            cb_plus.addItems(CONTACT_CHOICES)
            cb_plus.setStyleSheet("background: #1e293b; color: #f43f5e; font-weight: bold; padding: 4px;")
            
            # 4. MINUS ComboBox
            cb_minus = QComboBox()
            cb_minus.addItems(CONTACT_CHOICES)
            cb_minus.setStyleSheet("background: #1e293b; color: #38bdf8; font-weight: bold; padding: 4px;")

            # Load saved values if present
            saved = self.data_map.get(el_id, {})
            p_val = saved.get("plus", "--")
            m_val = saved.get("minus", "--")
            if p_val in CONTACT_CHOICES:
                cb_plus.setCurrentText(p_val)
            if m_val in CONTACT_CHOICES:
                cb_minus.setCurrentText(m_val)

            cb_plus.currentIndexChanged.connect(lambda idx, eid=el_id: self.on_pin_changed(eid))
            cb_minus.currentIndexChanged.connect(lambda idx, eid=el_id: self.on_pin_changed(eid))

            self.combos[el_id] = (cb_plus, cb_minus)
            self.table.setCellWidget(row, 3, cb_plus)
            self.table.setCellWidget(row, 4, cb_minus)

            # 5. Clear Button
            btn_clear = QPushButton("X")
            btn_clear.setFixedSize(26, 26)
            btn_clear.setStyleSheet("background: #475569; color: white; border-radius: 4px;")
            btn_clear.clicked.connect(lambda ch, eid=el_id: self.clear_row(eid))
            self.table.setCellWidget(row, 5, btn_clear)

    def on_pin_changed(self, el_id):
        cb_plus, cb_minus = self.combos[el_id]
        p = cb_plus.currentText()
        m = cb_minus.currentText()

        if p != "--" and m != "--":
            self.data_map[el_id] = {"plus": p, "minus": m}
        elif el_id in self.data_map:
            del self.data_map[el_id]

        self.save_data()
        self.update_summary()

    def clear_row(self, el_id):
        cb_plus, cb_minus = self.combos[el_id]
        cb_plus.setCurrentIndex(0)
        cb_minus.setCurrentIndex(0)
        if el_id in self.data_map:
            del self.data_map[el_id]
        self.save_data()
        self.update_summary()

    def update_summary(self):
        filled = len(self.data_map)
        total = len(ALL_ELEMENTS)
        self.lbl_summary.setText(f"Прозвонено элементов: {filled} / {total}")

    def load_data(self):
        if os.path.exists(MAP_FILE):
            try:
                with open(MAP_FILE, 'r', encoding='utf-8') as f:
                    self.data_map = json.load(f)
            except Exception:
                self.data_map = {}

    def save_data(self):
        try:
            with open(MAP_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.data_map, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print("Ошибка сохранения карты:", e)

    def generate_c_driver(self):
        self.save_data()
        out_h = os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_firmware", "dm02i_hardware_map.h")
        try:
            with open(out_h, "w", encoding="utf-8") as f:
                f.write("// Карта матрицы Charlieplexing DM02i V03 (по прозвонке мультиметром)\n")
                f.write("#ifndef DM02I_HARDWARE_MAP_H\n#define DM02I_HARDWARE_MAP_H\n\n")
                f.write("typedef struct {\n    const char *name;\n    uint8_t plus_pin;\n    uint8_t minus_pin;\n} HardwareMap_t;\n\n")
                f.write("static const HardwareMap_t DM02I_HARDWARE_MAP[] = {\n")
                for el in ALL_ELEMENTS:
                    eid = el["id"]
                    if eid in self.data_map:
                        d = self.data_map[eid]
                        p_num = d["plus"].replace("Контакт ", "")
                        m_num = d["minus"].replace("Контакт ", "")
                        f.write(f'    {{"{el["name"]}", {p_num}, {m_num}}},\n')
                f.write("};\n\n#endif\n")
            QMessageBox.information(self, "Успех", f"Карта сохранена в:\n{MAP_FILE}\n\nСгенерирован C-заголовок:\n{out_h}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить: {e}")

def main():
    app = QApplication(sys.argv)
    win = PinoutMapper()
    win.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
