# -*- coding: utf-8 -*-
"""
BOOKLIGHT STUDIO & HARDWARE CONTROLLER
======================================================
Портативная студия для управления и симуляции лампы для чтения
на базе платы вейпа (Puya PY32 + экран FH8016 + сенсор + филамент).

Возможности:
1. Точная графическая копия экрана FH8016 (цифры, 4 деления, молния, фары RGB).
2. Полный интерактивный выбор любых процентов, цветов диодов, делений и молнии.
3. Симулятор свечения филамента лампы с гамма-коррекцией AlexGyver Gamma 2.2.
4. Виртуальная сенсорная кнопка (клик, удержание, диммирование) + отображение
   состояния реальной физической кнопки с платы (по SWD).
5. Мониторинг и симуляция статуса USB Type-C, напряжения и анимации зарядки АКБ.
6. Прямая связь с микроконтроллером по SWD (когда подключен программатор)
   и 100% автономный режим симулятора (когда программатор отключен).
"""

import sys
import os
import time
import math

# Windows GUI stream fix (for no-console / windowed mode)
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, pyqtSlot, QPointF, QRectF, QSize
)
from PyQt6.QtGui import (
    QPainter, QColor, QFont, QPen, QBrush, QLinearGradient,
    QRadialGradient, QPainterPath, QPolygonF, QIcon, QFontDatabase
)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QSlider, QPushButton, QCheckBox, QComboBox,
    QSpinBox, QTabWidget, QGroupBox, QFrame, QScrollArea, QProgressBar,
    QSplitter, QStatusBar, QMessageBox
)

# ---------------------------------------------------------------------------
# 1. КОНСТАНТЫ И АЛГОРИТМЫ (В ТОЧНОСТИ СООТВЕТСТВУЮТ C-ПРОШИВКЕ)
# ---------------------------------------------------------------------------

# Цвета фар FH8016
COLOR_OFF     = 0
COLOR_RED     = 1
COLOR_GREEN   = 2
COLOR_BLUE    = 3
COLOR_CYAN    = 4
COLOR_MAGENTA = 5
COLOR_YELLOW  = 6
COLOR_WHITE   = 7

COLOR_NAMES = [
    "Выключен (OFF)",
    "Красный (Red)",
    "Зелёный (Green)",
    "Синий (Blue)",
    "Бирюзовый (Cyan)",
    "Пурпурный (Magenta)",
    "Жёлтый (Yellow)",
    "Белый (White)"
]

COLOR_RGB = {
    COLOR_OFF:     QColor(22, 26, 32),
    COLOR_RED:     QColor(255, 30, 60),
    COLOR_GREEN:   QColor(0, 240, 100),
    COLOR_BLUE:    QColor(0, 150, 255),
    COLOR_CYAN:    QColor(0, 240, 255),
    COLOR_MAGENTA: QColor(255, 20, 200),
    COLOR_YELLOW:  QColor(255, 215, 0),
    COLOR_WHITE:   QColor(240, 250, 255),
}

# 100-шаговая таблица Gamma 2.2 из gyver_rgbmath.c
GAMMA_100 = [
    0,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,   1,
    2,   2,   2,   2,   3,   3,   3,   4,   4,   4,   5,   5,   6,   6,   7,
    7,   8,   8,   9,   9,  10,  11,  11,  12,  13,  13,  14,  15,  16,  16,
   17,  18,  19,  20,  21,  22,  23,  24,  25,  26,  27,  28,  29,  30,  31,
   33,  34,  35,  36,  37,  39,  40,  41,  43,  44,  46,  47,  49,  50,  52,
   53,  55,  56,  58,  60,  61,  63,  65,  66,  68,  70,  72,  74,  75,  77,
   79,  81,  83,  85,  87,  89,  91,  94,  96,  98, 100
]

def gyver_gamma2(val):
    val = max(0, min(100, int(val)))
    return GAMMA_100[val]

def encode_fh8016_frame(percent, bars, icon_lightning, hl_l, hl_r):
    """Побитовое кодирование кадра FH8016 (26 бит) в точности по fh8016_py32.c"""
    if percent == 0 and bars == 0 and not icon_lightning and hl_l == COLOR_OFF and hl_r == COLOR_OFF:
        return 0

    frame = 0
    # 1. Цифры (аппаратный декодер)
    if percent >= 100:
        frame |= (1 << 7)
    elif percent > 0:
        frame |= (percent & 0x7F)

    # 2. Деления круговой шкалы (1..4)
    if bars == 1:
        frame |= (1 << 12)
    elif bars == 2:
        frame |= (1 << 12) | (1 << 13)
    elif bars == 3:
        frame |= (1 << 14)
    elif bars >= 4:
        frame |= (1 << 15)

    # 3. Молния (зарядка)
    if icon_lightning:
        frame |= (1 << 17)

    # 4. Фары RGB
    if hl_l in (COLOR_RED, COLOR_YELLOW, COLOR_MAGENTA, COLOR_WHITE) or \
       hl_r in (COLOR_RED, COLOR_YELLOW, COLOR_MAGENTA, COLOR_WHITE):
        frame |= (1 << 20) # Общий красный (обе фары делят один канал)
    if hl_l in (COLOR_GREEN, COLOR_YELLOW, COLOR_BLUE, COLOR_CYAN, COLOR_WHITE):
        frame |= (1 << 18) # Левый зелёный
    if hl_r in (COLOR_GREEN, COLOR_YELLOW, COLOR_BLUE, COLOR_CYAN, COLOR_WHITE):
        frame |= (1 << 19) # Правый зелёный
    if hl_l in (COLOR_BLUE, COLOR_CYAN, COLOR_MAGENTA, COLOR_WHITE):
        frame |= (1 << 22) # Левый синий
    if hl_r in (COLOR_BLUE, COLOR_CYAN, COLOR_MAGENTA, COLOR_WHITE):
        frame |= (1 << 23) # Правый синий

    return frame

def calc_battery_percent_from_mv(mv):
    """Кривая разряда Li-ion из прошивки main.c"""
    if mv >= 4150: return 100
    if mv >= 4050: return 90 + int(((mv - 4050) * 10) / 100)
    if mv >= 3950: return 80 + int(((mv - 3950) * 10) / 100)
    if mv >= 3850: return 65 + int(((mv - 3850) * 15) / 100)
    if mv >= 3780: return 50 + int(((mv - 3780) * 15) / 70)
    if mv >= 3700: return 35 + int(((mv - 3700) * 15) / 80)
    if mv >= 3600: return 20 + int(((mv - 3600) * 15) / 100)
    if mv >= 3450: return 10 + int(((mv - 3450) * 10) / 150)
    if mv >= 3300: return 1 + int(((mv - 3300) * 9) / 150)
    return 0

# ---------------------------------------------------------------------------
# 2. ГРАФИЧЕСКИЙ ВИДЖЕТ: ТОЧНАЯ КОПИЯ ДИСПЛЕЯ FH8016
# ---------------------------------------------------------------------------

class FH8016DisplayWidget(QWidget):
    """
    Векторная модель дисплея вейпа Husky 20000 / контроллера FH8016.
    Поддерживает точное отображение:
    - Двух 7-сегментных цифр + иконка %
    - 4 круговых радиальных деления шкалы
    - Пиктограмма молнии ⚡
    - Две RGB-фары (глазки) с мягким свечением
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(280, 360)
        self.percent = 70
        self.bars = 3
        self.icon_lightning = False
        self.hl_left = COLOR_GREEN
        self.hl_right = COLOR_GREEN
        self.screen_on = True

        # Карта 7-сегментных сегментов (A..G)
        #       A
        #     F   B
        #       G
        #     E   C
        #       D
        self.DIGIT_MAP = {
            '0': (True,  True,  True,  True,  True,  True,  False),
            '1': (False, True,  True,  False, False, False, False),
            '2': (True,  True,  False, True,  True,  False, True),
            '3': (True,  True,  True,  True,  False, False, True),
            '4': (False, True,  True,  False, False, True,  True),
            '5': (True,  False, True,  True,  False, True,  True),
            '6': (True,  False, True,  True,  True,  True,  True),
            '7': (True,  True,  True,  False, False, False, False),
            '8': (True,  True,  True,  True,  True,  True,  True),
            '9': (True,  True,  True,  True,  False, True,  True),
            ' ': (False, False, False, False, False, False, False),
        }

    def set_display_state(self, percent, bars, icon_lightning, hl_l, hl_r, screen_on=True):
        self.percent = percent
        self.bars = bars
        self.icon_lightning = icon_lightning
        self.hl_left = hl_l
        self.hl_right = hl_r
        self.screen_on = screen_on
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0

        # 1. Корпус экрана (стеклянная капсула / безель вейпа)
        margin = 12
        screen_rect = QRectF(margin, margin, w - 2*margin, h - 2*margin)
        
        # Внешняя рамка (темный титан)
        p.setPen(QPen(QColor(40, 46, 56), 2))
        p.setBrush(QBrush(QColor(12, 14, 18)))
        p.drawRoundedRect(screen_rect, 28, 28)

        # Внутреннее глубокое стекло (обсидиан с градиентом)
        inner_rect = screen_rect.adjusted(6, 6, -6, -6)
        glass_grad = QRadialGradient(cx, cy - 30, max(w, h) * 0.7)
        glass_grad.setColorAt(0.0, QColor(16, 20, 26))
        glass_grad.setColorAt(0.8, QColor(8, 9, 12))
        glass_grad.setColorAt(1.0, QColor(4, 5, 7))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glass_grad))
        p.drawRoundedRect(inner_rect, 22, 22)

        # Тонкий стеклянный блик сверху
        glare_path = QPainterPath()
        glare_path.addRoundedRect(inner_rect.adjusted(4, 4, -4, -inner_rect.height()*0.55), 18, 18)
        glare_grad = QLinearGradient(0, inner_rect.top(), 0, cy)
        glare_grad.setColorAt(0.0, QColor(255, 255, 255, 18))
        glare_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillPath(glare_path, glare_grad)

        if not self.screen_on:
            # Экран выключен - показываем лишь слабые очертания линз
            self._draw_headlights(p, cx, inner_rect.top() + 38, is_off=True)
            return

        # 2. Фары (RGB глазки) в верхней части
        self._draw_headlights(p, cx, inner_rect.top() + 38, is_off=False)

        # 3. Круговая радиальная шкала (4 деления)
        scale_center_y = cy + 18
        self._draw_circular_bars(p, cx, scale_center_y, radius=78)

        # 4. Пиктограмма молнии (зарядка)
        self._draw_lightning(p, cx, scale_center_y - 48)

        # 5. Цифровой индикатор процентов (7-сегментный стиль)
        self._draw_digits(p, cx, scale_center_y + 8)

    def _draw_headlights(self, p: QPainter, cx: float, cy: float, is_off: bool):
        """Отрисовка левой и правой фары с физическим эффектом рассеянного света"""
        dx = 48.0
        r_core = 11.0

        for side, color_code in [(-1, self.hl_left), (1, self.hl_right)]:
            hx = cx + side * dx
            hy = cy

            active_color = COLOR_RGB.get(color_code, COLOR_RGB[COLOR_OFF])
            is_active = (not is_off) and (color_code != COLOR_OFF)

            # Внешняя ниша линзы
            p.setPen(QPen(QColor(30, 36, 46), 1.5))
            p.setBrush(QBrush(QColor(14, 16, 22)))
            p.drawEllipse(QPointF(hx, hy), r_core + 4, r_core + 4)

            if is_active:
                # Ореол рассеяния (Bloom halo)
                halo = QRadialGradient(hx, hy, r_core * 3.2)
                halo_col = QColor(active_color)
                halo_col.setAlpha(120)
                halo.setColorAt(0.0, halo_col)
                halo_col.setAlpha(40)
                halo.setColorAt(0.5, halo_col)
                halo.setColorAt(1.0, QColor(0, 0, 0, 0))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(halo))
                p.drawEllipse(QPointF(hx, hy), r_core * 3.2, r_core * 3.2)

                # Яркая сердцевина светодиода
                core_grad = QRadialGradient(hx - 2, hy - 2, r_core)
                core_grad.setColorAt(0.0, QColor(255, 255, 255))
                core_grad.setColorAt(0.35, active_color)
                core_grad.setColorAt(1.0, active_color.darker(140))
                p.setPen(QPen(active_color.lighter(130), 1.0))
                p.setBrush(QBrush(core_grad))
                p.drawEllipse(QPointF(hx, hy), r_core, r_core)
            else:
                # Потухший светодиод (тёмный кремниевый кристалл)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QBrush(QColor(24, 28, 36)))
                p.drawEllipse(QPointF(hx, hy), r_core, r_core)

    def _draw_circular_bars(self, p: QPainter, cx: float, cy: float, radius: float):
        """Отрисовка 4 дуговых делений шкалы вокруг цифр"""
        bar_angles = [
            (205, 65),  # Деление 1 (левый низ)
            (115, 65),  # Деление 2 (левый верх)
            (0,   65),  # Деление 3 (правый верх)
            (290, 65),  # Деление 4 (правый низ)
        ]

        bar_rect = QRectF(cx - radius, cy - radius, radius * 2, radius * 2)

        for i, (start_deg, span_deg) in enumerate(bar_angles, start=1):
            is_lit = (self.bars >= i)

            if is_lit:
                color_core = QColor(0, 230, 118)  # Неоновый зеленый
                glow_color = QColor(0, 230, 118, 60)

                # Мягкое свечение деления
                pen_glow = QPen(glow_color, 14, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                p.setPen(pen_glow)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawArc(bar_rect, int(start_deg * 16), int(span_deg * 16))

                # Яркая центральная линия деления
                pen_core = QPen(color_core, 7, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                p.setPen(pen_core)
                p.drawArc(bar_rect, int(start_deg * 16), int(span_deg * 16))
            else:
                # Теневое незажженное деление
                pen_dark = QPen(QColor(22, 28, 36), 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                p.setPen(pen_dark)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawArc(bar_rect, int(start_deg * 16), int(span_deg * 16))

    def _draw_lightning(self, p: QPainter, cx: float, cy: float):
        """Пиктограмма зарядки ⚡"""
        is_lit = self.icon_lightning

        pts = [
            QPointF(cx + 2,  cy - 12),
            QPointF(cx - 8,  cy),
            QPointF(cx - 1,  cy),
            QPointF(cx - 3,  cy + 13),
            QPointF(cx + 8,  cy - 1),
            QPointF(cx + 1,  cy - 1),
        ]
        poly = QPolygonF(pts)

        if is_lit:
            # Золотой ореол
            halo = QRadialGradient(cx, cy, 22)
            halo.setColorAt(0.0, QColor(255, 185, 0, 150))
            halo.setColorAt(1.0, QColor(255, 185, 0, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(halo))
            p.drawEllipse(QPointF(cx, cy), 22, 22)

            # Яркая молния
            p.setPen(QPen(QColor(255, 240, 180), 1.0))
            p.setBrush(QBrush(QColor(255, 195, 0)))
            p.drawPolygon(poly)
        else:
            # Теневая неактивная молния
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(22, 26, 32)))
            p.drawPolygon(poly)

    def _draw_digits(self, p: QPainter, cx: float, cy: float):
        """Отрисовка 7-сегментных цифр процента и знака %"""
        p_val = max(0, min(100, self.percent))
        is_hundred = (p_val >= 100)
        num_str = f"{p_val:02d}"[-2:]

        digit_w = 26.0
        digit_h = 50.0
        spacing = 8.0

        total_w = digit_w * 2 + spacing + 22.0
        if is_hundred:
            total_w += 14.0

        start_x = cx - total_w / 2.0

        if is_hundred:
            self._draw_segment_bar(p, start_x + 6, cy - digit_h/2.0, 5, digit_h, is_lit=True)
            start_x += 16.0

        for ch in num_str:
            self._draw_7seg_digit(p, start_x, cy - digit_h/2.0, digit_w, digit_h, ch)
            start_x += digit_w + spacing

        self._draw_percent_sign(p, start_x + 2, cy - 8)

    def _draw_7seg_digit(self, p: QPainter, x: float, y: float, w: float, h: float, char: str):
        segs = self.DIGIT_MAP.get(char, self.DIGIT_MAP[' '])
        thick = 4.5
        gap = 1.5

        # A (top)
        self._draw_segment_h(p, x + gap, y, w - 2*gap, thick, segs[0])
        # B (top-right)
        self._draw_segment_v(p, x + w - thick, y + gap, thick, h/2.0 - gap, segs[1])
        # C (bottom-right)
        self._draw_segment_v(p, x + w - thick, y + h/2.0 + gap/2.0, thick, h/2.0 - gap, segs[2])
        # D (bottom)
        self._draw_segment_h(p, x + gap, y + h - thick, w - 2*gap, thick, segs[3])
        # E (bottom-left)
        self._draw_segment_v(p, x, y + h/2.0 + gap/2.0, thick, h/2.0 - gap, segs[4])
        # F (top-left)
        self._draw_segment_v(p, x, y + gap, thick, h/2.0 - gap, segs[5])
        # G (middle)
        self._draw_segment_h(p, x + gap, y + h/2.0 - thick/2.0, w - 2*gap, thick, segs[6])

    def _draw_segment_h(self, p: QPainter, x: float, y: float, w: float, t: float, is_lit: bool):
        pts = [
            QPointF(x + t/2, y),
            QPointF(x + w - t/2, y),
            QPointF(x + w, y + t/2),
            QPointF(x + w - t/2, y + t),
            QPointF(x + t/2, y + t),
            QPointF(x, y + t/2),
        ]
        self._fill_segment(p, QPolygonF(pts), is_lit)

    def _draw_segment_v(self, p: QPainter, x: float, y: float, t: float, h: float, is_lit: bool):
        pts = [
            QPointF(x + t/2, y),
            QPointF(x + t, y + t/2),
            QPointF(x + t, y + h - t/2),
            QPointF(x + t/2, y + h),
            QPointF(x, y + h - t/2),
            QPointF(x, y + t/2),
        ]
        self._fill_segment(p, QPolygonF(pts), is_lit)

    def _draw_segment_bar(self, p: QPainter, x: float, y: float, w: float, h: float, is_lit: bool):
        pts = [
            QPointF(x, y), QPointF(x + w, y),
            QPointF(x + w, y + h), QPointF(x, y + h)
        ]
        self._fill_segment(p, QPolygonF(pts), is_lit)

    def _fill_segment(self, p: QPainter, poly: QPolygonF, is_lit: bool):
        if is_lit:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(230, 250, 255)))
            p.drawPolygon(poly)
        else:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(QColor(20, 25, 32)))
            p.drawPolygon(poly)

    def _draw_percent_sign(self, p: QPainter, x: float, y: float):
        p.setPen(QPen(QColor(230, 250, 255), 2.2))
        p.drawEllipse(QPointF(x + 3, y - 6), 2.5, 2.5)
        p.drawLine(QPointF(x + 12, y - 8), QPointF(x + 1, y + 14))
        p.drawEllipse(QPointF(x + 10, y + 10), 2.5, 2.5)

# ---------------------------------------------------------------------------
# 3. ГРАФИЧЕСКИЙ ВИДЖЕТ: СИМУЛЯТОР СВЕЧЕНИЯ ФИЛАМЕНТА ЛАМПЫ
# ---------------------------------------------------------------------------

class FilamentLampWidget(QWidget):
    """
    Реалистичная визуализация филаментной светодиодной лампы для чтения.
    Яркость и спектр свечения рассчитываются по закону Gamma 2.2 (AlexGyver).
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(220, 360)
        self.brightness = 70
        self.lamp_on = True

    def set_lamp_state(self, brightness, lamp_on):
        self.brightness = brightness
        self.lamp_on = lamp_on
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0 - 15

        card_rect = QRectF(8, 8, w - 16, h - 16)
        p.setPen(QPen(QColor(38, 44, 54), 1.5))
        p.setBrush(QBrush(QColor(14, 17, 22)))
        p.drawRoundedRect(card_rect, 20, 20)

        duty = gyver_gamma2(self.brightness) if self.lamp_on else 0
        b_factor = (duty / 100.0)

        if duty <= 0:
            glow_color = QColor(0, 0, 0, 0)
            filament_color = QColor(140, 110, 40)
        elif duty < 15:
            glow_color = QColor(255, 80, 0, int(b_factor * 255))
            filament_color = QColor(255, 110, 20)
        elif duty < 55:
            glow_color = QColor(255, 160, 20, int(b_factor * 240))
            filament_color = QColor(255, 205, 70)
        else:
            glow_color = QColor(255, 220, 120, int(b_factor * 230))
            filament_color = QColor(255, 250, 210)

        if duty > 0:
            glow_radius = 45 + b_factor * 75
            ambient = QRadialGradient(cx, cy, glow_radius)
            c_center = QColor(glow_color)
            c_center.setAlpha(int(b_factor * 200))
            ambient.setColorAt(0.0, c_center)
            c_mid = QColor(glow_color)
            c_mid.setAlpha(int(b_factor * 70))
            ambient.setColorAt(0.5, c_mid)
            ambient.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(ambient))
            p.drawEllipse(QPointF(cx, cy), glow_radius, glow_radius)

        bulb_w = 64.0
        bulb_h = 130.0
        bulb_top = cy - bulb_h/2.0 + 8
        bulb_rect = QRectF(cx - bulb_w/2.0, bulb_top, bulb_w, bulb_h)

        glass_grad = QLinearGradient(bulb_rect.left(), 0, bulb_rect.right(), 0)
        glass_grad.setColorAt(0.0, QColor(255, 255, 255, 30))
        glass_grad.setColorAt(0.2, QColor(255, 255, 255, 10))
        glass_grad.setColorAt(0.8, QColor(255, 255, 255, 10))
        glass_grad.setColorAt(1.0, QColor(255, 255, 255, 35))
        p.setPen(QPen(QColor(80, 95, 115, 140), 1.8))
        p.setBrush(QBrush(glass_grad))
        p.drawRoundedRect(bulb_rect, bulb_w/2.0, bulb_w/2.0)

        fil_path = QPainterPath()
        start_y = bulb_top + 28
        end_y = bulb_top + bulb_h - 26
        fil_path.moveTo(cx - 10, end_y)
        fil_path.cubicTo(cx - 16, cy + 10, cx + 16, cy - 10, cx + 10, start_y)
        fil_path.arcTo(QRectF(cx - 10, start_y - 8, 20, 16), 0, 180)
        fil_path.cubicTo(cx - 16, cy - 10, cx + 16, cy + 10, cx - 10, end_y)

        if duty > 0:
            pen_glow = QPen(glow_color, 7.0 + b_factor * 4.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            p.setPen(pen_glow)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(fil_path)

            pen_core = QPen(filament_color, 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            p.setPen(pen_core)
            p.drawPath(fil_path)
        else:
            pen_off = QPen(filament_color, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
            p.setPen(pen_off)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(fil_path)

        base_y = bulb_top + bulb_h - 10
        base_w = 42.0
        base_h = 24.0
        base_rect = QRectF(cx - base_w/2.0, base_y, base_w, base_h)
        base_grad = QLinearGradient(base_rect.left(), 0, base_rect.right(), 0)
        base_grad.setColorAt(0.0, QColor(70, 75, 85))
        base_grad.setColorAt(0.5, QColor(140, 145, 160))
        base_grad.setColorAt(1.0, QColor(50, 55, 65))
        p.setPen(QPen(QColor(30, 35, 40), 1.0))
        p.setBrush(QBrush(base_grad))
        p.drawRoundedRect(base_rect, 4, 4)

        p.setFont(QFont("Segoe UI", 10, QFont.Weight.DemiBold))
        status_text = "СВЕТ ВКЛЮЧЕН" if self.lamp_on else "СВЕТ ПОГАШЕН"
        status_col = QColor(0, 230, 118) if self.lamp_on else QColor(130, 140, 155)
        p.setPen(status_col)
        p.drawText(QRectF(0, h - 56, w, 20), Qt.AlignmentFlag.AlignCenter, status_text)

        p.setFont(QFont("Segoe UI", 9))
        p.setPen(QColor(160, 175, 195))
        metrics_str = f"Яркость: {self.brightness}%  |  ШИМ: {duty}/100"
        p.drawText(QRectF(0, h - 36, w, 20), Qt.AlignmentFlag.AlignCenter, metrics_str)

# ---------------------------------------------------------------------------
# 4. ВИДЖЕТ ТАКТИЛЬНОЙ СЕНСОРНОЙ КНОПКИ
# ---------------------------------------------------------------------------

class TouchSensorButton(QPushButton):
    """
    Интерактивная сенсорная кнопка:
    - Различает короткий клик (<350 мс) и удержание (>=350 мс)
    - Визуализирует нажатие пульсирующим неоновым кольцом
    """
    touch_pressed = pyqtSignal()
    touch_released = pyqtSignal(int)
    touch_holding = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(64)
        self.setText("  КАСАНИЕ СЕНСОРА (УДЕРЖИВАЙТЕ ДЛЯ ДИММИРОВАНИЯ)")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.press_start_time = 0
        self.is_down = False

        self.hold_timer = QTimer(self)
        self.hold_timer.setInterval(40)
        self.hold_timer.timeout.connect(self._on_hold_tick)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_down = True
            self.press_start_time = time.time()
            self.touch_pressed.emit()
            self.hold_timer.start()
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if self.is_down:
            self.is_down = False
            self.hold_timer.stop()
            dur_ms = int((time.time() - self.press_start_time) * 1000)
            self.touch_released.emit(dur_ms)
            self.update()
        super().mouseReleaseEvent(event)

    def _on_hold_tick(self):
        dur_ms = int((time.time() - self.press_start_time) * 1000)
        if dur_ms >= 350:
            self.touch_holding.emit()

# ---------------------------------------------------------------------------
# 5. ФОНОВЫЙ ПОТОК СВЯЗИ С ПЛАТОЙ ПО SWD (БЕЗ ЗАВИСАНИЯ ИНТЕРФЕЙСА)
# ---------------------------------------------------------------------------

class HardwareWorker(QThread):
    """
    Фоновый воркер опроса микроконтроллера по SWD (PyOCD / PyLink).
    Поддерживает любые программаторы: ST-Link V2, J-Link, CMSIS-DAP.
    При отключенном программаторе мгновенно сообщает об автономном режиме.
    При подключенном - считывает регистры RAM и физические выводы GPIO.
    """
    telemetry_ready = pyqtSignal(dict)
    connection_changed = pyqtSignal(bool, str)

    def __init__(self):
        super().__init__()
        self.running = True
        self.is_connected = False
        self.pending_writes = []

    def queue_write_variable(self, addr, val, size=1):
        self.pending_writes.append((addr, val, size))

    def run(self):
        import pylink
        jlink = None
        fail_count = 0

        while self.running:
            try:
                # 1. Поиск подключенных программаторов
                if jlink is None:
                    jlink = pylink.JLink()

                emulators = jlink.connected_emulators()
                if not emulators:
                    if self.is_connected:
                        self.is_connected = False
                        self.connection_changed.emit(False, "Программатор отключен (автономный режим)")
                    try:
                        jlink.close()
                    except Exception:
                        pass
                    jlink = None
                    self.msleep(400)
                    continue

                emu = emulators[0]
                probe_name = "J-Link STLink"
                try:
                    if hasattr(emu, 'acProduct') and emu.acProduct:
                        probe_name = emu.acProduct.decode('utf-8', errors='ignore')
                except Exception:
                    pass
                sn = emu.SerialNumber

                if not jlink.opened():
                    jlink.open(serial_no=sn)
                    jlink.set_tif(pylink.enums.JLinkInterfaces.SWD)
                    jlink.set_speed(1000)
                    jlink.coresight_configure()

                hs = jlink.hardware_status
                vtarget = hs.VTarget / 1000.0

                if vtarget < 1.8:
                    if self.is_connected:
                        self.is_connected = False
                    self.connection_changed.emit(False, f"Программатор в USB ({probe_name}), но VTarget < 1.8V (нет питания)")
                    self.msleep(300)
                    continue

                # 2. Если связь ещё не установлена — проверяем DPIDR
                if not self.is_connected:
                    try:
                        jlink.coresight_configure()
                        dpidr = jlink.coresight_read(0, ap=False)
                    except Exception:
                        dpidr = 0

                    if dpidr in (0x0BC11477, 0x0BB11477, 0x2BA01477):
                        self.is_connected = True
                        fail_count = 0
                        self.connection_changed.emit(True, f"Связь с чипом активна ({probe_name}, {vtarget:.2f}V)")
                    else:
                        self.connection_changed.emit(False, f"Программатор в USB ({probe_name}), но нет связи с чипом (проверьте DA/CK)")
                        self.msleep(300)
                        continue

                # 3. Рабочий цикл чтения телеметрии (БЕЗ сброса coresight_configure!)
                try:
                    # Запись отложенных команд
                    while self.pending_writes:
                        addr, val, sz = self.pending_writes.pop(0)
                        try:
                            jlink.coresight_write(1, addr, ap=True)
                            jlink.coresight_write(3, val, ap=True)
                        except Exception:
                            pass

                    # Быстрое чтение переменных (RAM + GPIO)
                    jlink.coresight_write(1, 0x20000004, ap=True)
                    w_saved = jlink.coresight_read(3, ap=True)
                    saved_b = (w_saved >> 8) & 0xFF

                    jlink.coresight_write(1, 0x2000005C, ap=True)
                    w_state = jlink.coresight_read(3, ap=True)
                    is_chrg_mem = bool(w_state & 0xFF)
                    touch_mem   = bool((w_state >> 8) & 0xFF)
                    pwm_duty    = (w_state >> 16) & 0xFF
                    lamp_on     = bool((w_state >> 24) & 0xFF)

                    jlink.coresight_write(1, 0x20000060, ap=True)
                    w_bright = jlink.coresight_read(3, ap=True)
                    tgt_b = w_bright & 0xFF
                    cur_b = (w_bright >> 8) & 0xFF

                    jlink.coresight_write(1, 0x50000410, ap=True)
                    gpiob_idr = jlink.coresight_read(3, ap=True)
                    phys_touch = bool(gpiob_idr & (1 << 4))
                    phys_chrg  = not bool(gpiob_idr & (1 << 5))

                    fail_count = 0  # Успешное чтение

                    self.telemetry_ready.emit({
                        'saved_b': saved_b if saved_b > 0 else 70,
                        'tgt_b': tgt_b,
                        'cur_b': cur_b,
                        'lamp_on': lamp_on,
                        'pwm_duty': pwm_duty,
                        'touch_stable': touch_mem or phys_touch,
                        'phys_touch': phys_touch,
                        'is_charging': is_chrg_mem or phys_chrg,
                        'vtarget': vtarget
                    })
                    self.msleep(50)

                except Exception:
                    fail_count += 1
                    if fail_count < 4:
                        # Единичный сбой: пробуем мягко восстановить синхронизацию
                        try:
                            jlink.coresight_configure()
                        except Exception:
                            pass
                        self.msleep(20)
                    else:
                        # Только при 4 сбоях подряд объявляем потерю
                        self.is_connected = False
                        self.connection_changed.emit(False, f"Программатор в USB ({probe_name}), но нет связи с чипом (проверьте DA/CK)")
                        self.msleep(200)

            except Exception:
                fail_count += 1
                if fail_count >= 4 and self.is_connected:
                    self.is_connected = False
                    self.connection_changed.emit(False, "Программатор отключен (автономный режим)")
                try:
                    if jlink:
                        jlink.close()
                except Exception:
                    pass
                jlink = None
                self.msleep(300)

        if jlink:
            try:
                jlink.close()
            except Exception:
                pass

    def stop(self):
        self.running = False
        self.wait(1000)

# ---------------------------------------------------------------------------
# 6. ГЛАВНОЕ ОКНО ПРИЛОЖЕНИЯ
# ---------------------------------------------------------------------------

class BookLightStudioWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BookLight Studio — Интерактивный Центр Управления и Симулятор Дисплея")
        self.resize(1020, 720)
        self.setMinimumSize(920, 640)

        self.lamp_on = True
        self.brightness = 70
        self.saved_brightness = 70
        self.dim_direction = 1
        self.screen_on = True
        self.show_screen_until = time.time() + 999999.0

        self.bars_mode = "auto"
        self.custom_bars = 3
        self.icon_lightning = False
        self.hl_left = COLOR_GREEN
        self.hl_right = COLOR_GREEN

        self.battery_mv = 3950
        self.is_usb_plugged = False
        self.charging_step = 1

        self.sim_timer = QTimer(self)
        self.sim_timer.setInterval(30)
        self.sim_timer.timeout.connect(self._on_sim_tick)
        self.sim_timer.start()

        self.hw_worker = HardwareWorker()
        self.hw_worker.telemetry_ready.connect(self._on_hw_telemetry)
        self.hw_worker.connection_changed.connect(self._on_hw_connection_changed)
        self.hw_worker.start()

        self._init_ui()
        self._apply_qss()

    def _init_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(16, 14, 16, 14)
        main_layout.setSpacing(12)

        top_bar = self._create_top_bar()
        main_layout.addWidget(top_bar)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(16)

        left_col = QVBoxLayout()
        left_col.setSpacing(12)

        visual_row = QHBoxLayout()
        visual_row.setSpacing(12)

        self.display_widget = FH8016DisplayWidget(self)
        visual_row.addWidget(self.display_widget)

        self.lamp_widget = FilamentLampWidget(self)
        visual_row.addWidget(self.lamp_widget)

        left_col.addLayout(visual_row)

        self.touch_btn = TouchSensorButton(self)
        self.touch_btn.touch_pressed.connect(self._on_virtual_touch_pressed)
        self.touch_btn.touch_released.connect(self._on_virtual_touch_released)
        self.touch_btn.touch_holding.connect(self._on_virtual_touch_holding)
        left_col.addWidget(self.touch_btn)

        self.phys_touch_badge = QLabel("⚡ Физический сенсор на плате: [ ОЖИДАНИЕ СВЯЗИ ]", self)
        self.phys_touch_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.phys_touch_badge.setObjectName("physBadge")
        left_col.addWidget(self.phys_touch_badge)

        content_layout.addLayout(left_col, stretch=5)

        self.tabs = QTabWidget(self)
        self.tabs.addTab(self._create_display_control_tab(), " Экран FH8016")
        self.tabs.addTab(self._create_lamp_control_tab(), "💡 Филамент Лампы")
        self.tabs.addTab(self._create_battery_tab(), "🔋 Батарея и USB")
        self.tabs.addTab(self._create_presets_tab(), "⚡ Пресеты и SWD")

        content_layout.addWidget(self.tabs, stretch=6)
        main_layout.addLayout(content_layout)

        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Готов к работе. Автономный режим симулятора активен.")

    def _create_top_bar(self):
        bar = QFrame(self)
        bar.setObjectName("topBar")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(14, 8, 14, 8)

        title = QLabel("📖 BOOKLIGHT STUDIO — Лампа для чтения из вейпа", self)
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lay.addWidget(title)

        lay.addStretch()

        self.conn_indicator = QLabel("● АВТОНОМНЫЙ РЕЖИМ (ПРОГРАММАТОР ОТКЛЮЧЕН)", self)
        self.conn_indicator.setObjectName("connIndicator")
        lay.addWidget(self.conn_indicator)

        return bar

    # -----------------------------------------------------------------------
    # ВКЛАДКА 1: УПРАВЛЕНИЕ ЭКРАНОМ FH8016
    # -----------------------------------------------------------------------
    def _create_display_control_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(14)

        grp_pct = QGroupBox("1. Процент на экране (0 .. 100%)", w)
        pct_lay = QVBoxLayout(grp_pct)

        pct_row = QHBoxLayout()
        self.pct_slider = QSlider(Qt.Orientation.Horizontal, w)
        self.pct_slider.setRange(0, 100)
        self.pct_slider.setValue(70)
        self.pct_slider.valueChanged.connect(self._on_pct_slider_changed)
        pct_row.addWidget(self.pct_slider)

        self.pct_spin = QSpinBox(w)
        self.pct_spin.setRange(0, 100)
        self.pct_spin.setValue(70)
        self.pct_spin.valueChanged.connect(self.pct_slider.setValue)
        pct_row.addWidget(self.pct_spin)
        pct_lay.addLayout(pct_row)

        quick_pct_row = QHBoxLayout()
        for p in [0, 1, 25, 50, 70, 100]:
            btn = QPushButton(f"{p}%", w)
            btn.clicked.connect(lambda checked, val=p: self.pct_slider.setValue(val))
            quick_pct_row.addWidget(btn)
        pct_lay.addLayout(quick_pct_row)
        lay.addWidget(grp_pct)

        grp_bars = QGroupBox("2. Деления круговой шкалы", w)
        bars_lay = QHBoxLayout(grp_bars)

        self.bars_combo = QComboBox(w)
        self.bars_combo.addItems([
            "Автоматически (по процентам)",
            "Выключены (0 делений)",
            "1 деление (четверть)",
            "2 деления (половина)",
            "3 деления (три четверти)",
            "4 деления (полный круг)"
        ])
        self.bars_combo.setCurrentIndex(0)
        self.bars_combo.currentIndexChanged.connect(self._on_bars_combo_changed)
        bars_lay.addWidget(self.bars_combo)
        lay.addWidget(grp_bars)

        grp_icons = QGroupBox("3. Фары (RGB) и пиктограмма молнии", w)
        icons_lay = QGridLayout(grp_icons)

        icons_lay.addWidget(QLabel("Левая фара:"), 0, 0)
        self.combo_hl_l = QComboBox(w)
        self.combo_hl_l.addItems(COLOR_NAMES)
        self.combo_hl_l.setCurrentIndex(COLOR_GREEN)
        self.combo_hl_l.currentIndexChanged.connect(self._on_headlights_changed)
        icons_lay.addWidget(self.combo_hl_l, 0, 1)

        icons_lay.addWidget(QLabel("Правая фара:"), 1, 0)
        self.combo_hl_r = QComboBox(w)
        self.combo_hl_r.addItems(COLOR_NAMES)
        self.combo_hl_r.setCurrentIndex(COLOR_GREEN)
        self.combo_hl_r.currentIndexChanged.connect(self._on_headlights_changed)
        icons_lay.addWidget(self.combo_hl_r, 1, 1)

        self.chk_lightning = QCheckBox("⚡ Пиктограмма молнии (Зарядка)", w)
        self.chk_lightning.stateChanged.connect(self._on_lightning_toggled)
        icons_lay.addWidget(self.chk_lightning, 2, 0, 1, 2)

        self.chk_screen_power = QCheckBox("Включить экран (Питание FH8016)", w)
        self.chk_screen_power.setChecked(True)
        self.chk_screen_power.stateChanged.connect(self._on_screen_power_toggled)
        icons_lay.addWidget(self.chk_screen_power, 3, 0, 1, 2)

        lay.addWidget(grp_icons)

        grp_raw = QGroupBox("4. Побитовый пакет 1-Wire кадра FH8016", w)
        raw_lay = QVBoxLayout(grp_raw)
        self.lbl_frame_hex = QLabel("Кадр: 0x000C8046", w)
        self.lbl_frame_hex.setFont(QFont("Consolas", 11, QFont.Weight.Bold))
        raw_lay.addWidget(self.lbl_frame_hex)

        self.lbl_frame_bin = QLabel("Биты: 0b000011001000000001000110", w)
        self.lbl_frame_bin.setFont(QFont("Consolas", 9))
        self.lbl_frame_bin.setStyleSheet("color: #00e5ff;")
        raw_lay.addWidget(self.lbl_frame_bin)

        lay.addWidget(grp_raw)
        lay.addStretch()
        return w

    # -----------------------------------------------------------------------
    # ВКЛАДКА 2: УПРАВЛЕНИЕ ПОДСВЕТКОЙ (ФИЛАМЕНТ)
    # -----------------------------------------------------------------------
    def _create_lamp_control_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(14)

        grp_lamp = QGroupBox("Управление лампой для чтения", w)
        lamp_lay = QVBoxLayout(grp_lamp)

        self.btn_lamp_toggle = QPushButton("💡 ВКЛЮЧИТЬ / ВЫКЛЮЧИТЬ ЛАМПУ", w)
        self.btn_lamp_toggle.setMinimumHeight(44)
        self.btn_lamp_toggle.setObjectName("accentBtn")
        self.btn_lamp_toggle.clicked.connect(self._toggle_lamp)
        lamp_lay.addWidget(self.btn_lamp_toggle)

        lamp_lay.addWidget(QLabel("Уровень яркости (1 .. 100%):"))
        b_row = QHBoxLayout()
        self.b_slider = QSlider(Qt.Orientation.Horizontal, w)
        self.b_slider.setRange(1, 100)
        self.b_slider.setValue(70)
        self.b_slider.valueChanged.connect(self._on_lamp_slider_changed)
        b_row.addWidget(self.b_slider)

        self.b_spin = QSpinBox(w)
        self.b_spin.setRange(1, 100)
        self.b_spin.setValue(70)
        self.b_spin.valueChanged.connect(self.b_slider.setValue)
        b_row.addWidget(self.b_spin)
        lamp_lay.addLayout(b_row)

        preset_row = QHBoxLayout()
        presets = [
            ("Ночник (1%)", 1),
            ("Мягкий (15%)", 15),
            ("Чтение (50%)", 50),
            ("Комфорт (70%)", 70),
            ("Максимум (100%)", 100)
        ]
        for name, val in presets:
            btn = QPushButton(name, w)
            btn.clicked.connect(lambda checked, v=val: self.b_slider.setValue(v))
            preset_row.addWidget(btn)
        lamp_lay.addLayout(preset_row)

        lay.addWidget(grp_lamp)

        grp_gamma = QGroupBox("Математика ШИМ (AlexGyver Gamma 2.2)", w)
        gamma_lay = QVBoxLayout(grp_gamma)
        self.lbl_gamma_info = QLabel(
            "Для линейного восприятия глазом яркость филамента преобразуется\n"
            "по таблице Gamma 2.2:\n"
            "• При 1% яркости -> ШИМ = 1/100 (мягкое тление)\n"
            "• При 50% яркости -> ШИМ = 23/100\n"
            "• При 70% яркости -> ШИМ = 44/100\n"
            "• При 100% яркости -> ШИМ = 100/100"
        )
        self.lbl_gamma_info.setStyleSheet("color: #a0aec0; font-size: 11px;")
        gamma_lay.addWidget(self.lbl_gamma_info)
        lay.addWidget(grp_gamma)

        lay.addStretch()
        return w

    # -----------------------------------------------------------------------
    # ВКЛАДКА 3: БАТАРЕЯ И СТАТУС ЗАРЯДКИ USB
    # -----------------------------------------------------------------------
    def _create_battery_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(14)

        grp_bat = QGroupBox("Эмуляция аккумулятора Li-ion (3.7V)", w)
        bat_lay = QVBoxLayout(grp_bat)

        bat_lay.addWidget(QLabel("Напряжение батареи (милливольты):"))
        v_row = QHBoxLayout()
        self.v_slider = QSlider(Qt.Orientation.Horizontal, w)
        self.v_slider.setRange(3100, 4200)
        self.v_slider.setValue(3950)
        self.v_slider.valueChanged.connect(self._on_voltage_changed)
        v_row.addWidget(self.v_slider)

        self.lbl_voltage = QLabel("3.95 V (85%)", w)
        self.lbl_voltage.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        v_row.addWidget(self.lbl_voltage)
        bat_lay.addLayout(v_row)

        lay.addWidget(grp_bat)

        grp_usb = QGroupBox("Разъём USB Type-C и Зарядка", w)
        usb_lay = QVBoxLayout(grp_usb)

        self.chk_usb = QCheckBox("Кабель USB Type-C подключен (5V VBUS)", w)
        self.chk_usb.stateChanged.connect(self._on_usb_toggled)
        usb_lay.addWidget(self.chk_usb)

        self.chk_charge_anim = QCheckBox("Включить бегущую анимацию зарядки ⚡", w)
        self.chk_charge_anim.stateChanged.connect(self._on_charge_anim_toggled)
        usb_lay.addWidget(self.chk_charge_anim)

        lay.addWidget(grp_usb)
        lay.addStretch()
        return w

    # -----------------------------------------------------------------------
    # ВКЛАДКА 4: ПРЕСЕТЫ И SWD УПРАВЛЕНИЕ
    # -----------------------------------------------------------------------
    def _create_presets_tab(self):
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(14)

        grp_presets = QGroupBox("Быстрые сценарии тестирования", w)
        p_lay = QGridLayout(grp_presets)

        btn1 = QPushButton("⚡ Режим чтения (70%, фары зелёные)", w)
        btn1.clicked.connect(lambda: self._apply_preset(70, 3, False, COLOR_GREEN, COLOR_GREEN, 70, True))
        p_lay.addWidget(btn1, 0, 0)

        btn2 = QPushButton("🌙 Ночник (1%, мягкий янтарный свет)", w)
        btn2.clicked.connect(lambda: self._apply_preset(1, 1, False, COLOR_YELLOW, COLOR_YELLOW, 1, True))
        p_lay.addWidget(btn2, 0, 1)

        btn3 = QPushButton("🔋 Идет зарядка Type-C (бегущие огни)", w)
        btn3.clicked.connect(lambda: self._apply_preset(88, 4, True, COLOR_CYAN, COLOR_CYAN, 0, False))
        p_lay.addWidget(btn3, 1, 0)

        btn4 = QPushButton("🌟 Тест всех диодов (100%, белые фары)", w)
        btn4.clicked.connect(lambda: self._apply_preset(100, 4, True, COLOR_WHITE, COLOR_WHITE, 100, True))
        p_lay.addWidget(btn4, 1, 1)

        lay.addWidget(grp_presets)

        grp_swd = QGroupBox("Прямая запись в микроконтроллер (SWD)", w)
        swd_lay = QVBoxLayout(grp_swd)

        self.btn_send_hw = QPushButton("📤 Отправить текущий экран в чип (RAM)", w)
        self.btn_send_hw.clicked.connect(self._send_state_to_hardware)
        swd_lay.addWidget(self.btn_send_hw)

        self.btn_flash_mcu = QPushButton("🔥 Перепрошить чип прошивкой (battery_firmware.bin)", w)
        self.btn_flash_mcu.clicked.connect(self._flash_firmware)
        swd_lay.addWidget(self.btn_flash_mcu)

        lay.addWidget(grp_swd)
        lay.addStretch()
        return w

    # -----------------------------------------------------------------------
    # ЛОГИКА СИМУЛЯЦИИ И ОБНОВЛЕНИЯ СОСТОЯНИЯ
    # -----------------------------------------------------------------------
    def _on_sim_tick(self):
        if self.chk_charge_anim.isChecked():
            # Переключаем деление каждые ~500мс (каждый 17-й тик при 30мс таймере)
            if not hasattr(self, '_charge_anim_counter'):
                self._charge_anim_counter = 0
            self._charge_anim_counter += 1
            if self._charge_anim_counter >= 17:
                self._charge_anim_counter = 0
                self.charging_step += 1
                if self.charging_step > 4:
                    self.charging_step = 1
            cur_bars = self.charging_step
        else:
            if self.bars_mode == "auto":
                p = self.pct_slider.value()
                cur_bars = 4 if p >= 75 else 3 if p >= 50 else 2 if p >= 25 else 1 if p > 0 else 0
            else:
                cur_bars = self.custom_bars

        pct = self.pct_slider.value()
        lightning = self.chk_lightning.isChecked() or self.chk_charge_anim.isChecked()
        hl_l = self.combo_hl_l.currentIndex()
        hl_r = self.combo_hl_r.currentIndex()
        screen_on = self.chk_screen_power.isChecked()

        self.display_widget.set_display_state(pct, cur_bars, lightning, hl_l, hl_r, screen_on)
        self.lamp_widget.set_lamp_state(self.b_slider.value(), self.lamp_on)

        frame = encode_fh8016_frame(pct, cur_bars, lightning, hl_l, hl_r)
        self.lbl_frame_hex.setText(f"Кадр FH8016: 0x{frame:08X}")
        self.lbl_frame_bin.setText(f"Биты (26): {frame:026b}")

    def _on_pct_slider_changed(self, val):
        self.pct_spin.setValue(val)
        if self.lamp_on:
            self.b_slider.setValue(val)

    def _on_lamp_slider_changed(self, val):
        self.b_spin.setValue(val)
        self.pct_slider.setValue(val)

    def _on_bars_combo_changed(self, idx):
        if idx == 0:
            self.bars_mode = "auto"
        else:
            self.bars_mode = "custom"
            self.custom_bars = idx - 1

    def _on_headlights_changed(self):
        pass

    def _on_lightning_toggled(self):
        pass

    def _on_screen_power_toggled(self, state):
        pass

    def _toggle_lamp(self):
        self.lamp_on = not self.lamp_on
        if self.lamp_on:
            self.status_bar.showMessage("Лампа включена!")
        else:
            self.status_bar.showMessage("Лампа выключена.")

    def _on_voltage_changed(self, mv):
        pct = calc_battery_percent_from_mv(mv)
        self.lbl_voltage.setText(f"{mv/1000.0:.2f} V ({pct}%)")

    def _on_usb_toggled(self, state):
        is_plugged = (state == Qt.CheckState.Checked.value)
        if is_plugged:
            self.chk_charge_anim.setChecked(True)
            self.status_bar.showMessage("USB подключен: идёт зарядка АКБ.")
        else:
            self.chk_charge_anim.setChecked(False)
            self.status_bar.showMessage("USB отключен.")

    def _on_charge_anim_toggled(self, state):
        pass

    def _apply_preset(self, pct, bars, lightning, hl_l, hl_r, lamp_b, lamp_on):
        self.pct_slider.setValue(pct)
        self.bars_combo.setCurrentIndex(bars + 1 if bars > 0 else 1)
        self.chk_lightning.setChecked(lightning)
        self.combo_hl_l.setCurrentIndex(hl_l)
        self.combo_hl_r.setCurrentIndex(hl_r)
        self.b_slider.setValue(lamp_b)
        self.lamp_on = lamp_on
        self.chk_screen_power.setChecked(True)
        self.status_bar.showMessage(f"Применён пресет: {pct}%")

    # -----------------------------------------------------------------------
    # ТАКТИЛЬНЫЙ СЕНСОР: КЛИК, УДЕРЖАНИЕ, ДИММИРОВАНИЕ
    # -----------------------------------------------------------------------
    def _on_virtual_touch_pressed(self):
        self.phys_touch_badge.setText("⚡ Виртуальный сенсор: НАЖАТ (УДЕРЖАНИЕ...)")
        self.phys_touch_badge.setStyleSheet("background-color: #00e676; color: #000; font-weight: bold;")

    def _on_virtual_touch_released(self, dur_ms):
        self.phys_touch_badge.setText("⚪ Сенсор: ОТПУЩЕН")
        self.phys_touch_badge.setStyleSheet("")

        if dur_ms < 350:
            self.lamp_on = not self.lamp_on
            if self.lamp_on:
                self.b_slider.setValue(self.saved_brightness)
                self.status_bar.showMessage(f"Короткий клик: лампа ВКЛ ({self.saved_brightness}%)")
            else:
                self.status_bar.showMessage("Короткий клик: лампа ВЫКЛ")
        else:
            self.saved_brightness = self.b_slider.value()
            self.dim_direction = -self.dim_direction
            self.status_bar.showMessage(f"Яркость зафиксирована: {self.saved_brightness}% (направление развернуто)")

    def _on_virtual_touch_holding(self):
        self.lamp_on = True
        cur = self.b_slider.value()
        if self.dim_direction > 0:
            if cur < 100:
                self.b_slider.setValue(cur + 1)
            else:
                self.dim_direction = -1
        else:
            if cur > 1:
                self.b_slider.setValue(cur - 1)
            else:
                self.dim_direction = 1

    # -----------------------------------------------------------------------
    # ТЕЛЕМЕТРИЯ С МИКРОКОНТРОЛЛЕРА
    # -----------------------------------------------------------------------
    @pyqtSlot(dict)
    def _on_hw_telemetry(self, data):
        touch = data.get('touch_stable', False)
        if touch:
            self.phys_touch_badge.setText("🔴 ФИЗИЧЕСКАЯ КНОПКА НА ПЛАТЕ: НАЖАТА!")
            self.phys_touch_badge.setStyleSheet("background-color: #ff1744; color: #fff; font-weight: bold;")
        else:
            self.phys_touch_badge.setText("⚪ Физическая кнопка на плате: отпущена")
            self.phys_touch_badge.setStyleSheet("")

    @pyqtSlot(bool, str)
    def _on_hw_connection_changed(self, connected, msg):
        if connected:
            self.conn_indicator.setText(f"● {msg.upper()}")
            self.conn_indicator.setStyleSheet("color: #00e676; font-weight: bold;")
        else:
            if "нет связи" in msg.lower() or "проверьте" in msg.lower():
                self.conn_indicator.setText(f"▲ {msg.upper()}")
                self.conn_indicator.setStyleSheet("color: #ff9100; font-weight: bold;")
            else:
                self.conn_indicator.setText("● АВТОНОМНЫЙ РЕЖИМ (ПРОГРАММАТОР ОТКЛЮЧЕН)")
                self.conn_indicator.setStyleSheet("color: #94a3b8; font-weight: bold;")
        self.status_bar.showMessage(msg)

    def _send_state_to_hardware(self):
        if not self.hw_worker.is_connected:
            QMessageBox.information(
                self, "Программатор отключен",
                "Сейчас плата работает автономно от аккумулятора.\n"
                "Когда подключите программатор в USB, состояние запишется в чип автоматически!"
            )
            return

        duty = gyver_gamma2(self.b_slider.value()) if self.lamp_on else 0
        self.hw_worker.queue_write_variable(0x2000005F, 1 if self.lamp_on else 0, 1)  # lamp_on
        self.hw_worker.queue_write_variable(0x2000005E, duty, 1)                       # pwm_duty
        self.hw_worker.queue_write_variable(0x20000060, self.b_slider.value(), 1)     # target_brightness
        self.hw_worker.queue_write_variable(0x20000061, self.b_slider.value(), 1)     # current_brightness
        self.status_bar.showMessage("Параметры отправлены в микроконтроллер!")

    def _flash_firmware(self):
        flash_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "flash_direct.py")
        if not os.path.exists(flash_script):
            QMessageBox.critical(self, "Ошибка", f"Скрипт прошивки не найден:\n{flash_script}")
            return

        import subprocess
        self.status_bar.showMessage("Запуск прямой прошивки (on-the-fly)...")
        try:
            res = subprocess.run([sys.executable, flash_script], capture_output=True, text=True, timeout=20)
            if res.returncode == 0:
                QMessageBox.information(self, "Успех!", "Микроконтроллер успешно перепрошит новой прошивкой!")
            else:
                QMessageBox.warning(self, "Ошибка прошивки", f"{res.stderr}\n{res.stdout}")
        except Exception as e:
            QMessageBox.critical(self, "Исключение", str(e))

    def closeEvent(self, event):
        self.hw_worker.stop()
        super().closeEvent(event)

    # -----------------------------------------------------------------------
    # СТИЛИЗАЦИЯ ИНТЕРФЕЙСА (PREMIUM DARK THEME)
    # -----------------------------------------------------------------------
    def _apply_qss(self):
        qss = """
        QMainWindow {
            background-color: #0b0d13;
        }
        QFrame#topBar {
            background-color: #141822;
            border: 1px solid #222a3a;
            border-radius: 10px;
        }
        QFrame#topBar QLabel {
            color: #e2e8f0;
        }
        QLabel#connIndicator {
            color: #ffb703;
            font-size: 11px;
            font-weight: bold;
        }
        QLabel#physBadge {
            background-color: #141824;
            border: 1px solid #242c3d;
            border-radius: 8px;
            padding: 6px;
            color: #94a3b8;
            font-size: 11px;
        }
        QTabWidget::pane {
            border: 1px solid #222a3a;
            border-radius: 12px;
            background-color: #12151e;
        }
        QTabBar::tab {
            background-color: #181c28;
            color: #94a3b8;
            padding: 8px 16px;
            margin-right: 4px;
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
            font-weight: bold;
        }
        QTabBar::tab:selected {
            background-color: #222a3e;
            color: #00e5ff;
            border-bottom: 2px solid #00e5ff;
        }
        QGroupBox {
            font-weight: bold;
            color: #cbd5e1;
            border: 1px solid #222a3a;
            border-radius: 10px;
            margin-top: 10px;
            padding-top: 14px;
            background-color: #151924;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 12px;
            padding: 0 4px;
        }
        QPushButton {
            background-color: #1e2536;
            color: #e2e8f0;
            border: 1px solid #2e384f;
            border-radius: 8px;
            padding: 6px 12px;
            font-weight: 600;
        }
        QPushButton:hover {
            background-color: #283248;
            border-color: #00e5ff;
        }
        QPushButton:pressed {
            background-color: #161b28;
        }
        QPushButton#accentBtn {
            background-color: #00b4d8;
            color: #07131d;
            border: none;
            font-size: 12px;
            font-weight: bold;
        }
        QPushButton#accentBtn:hover {
            background-color: #00e5ff;
        }
        QPushButton#accentBtn:pressed {
            background-color: #0096c7;
        }
        QSlider::groove:horizontal {
            height: 6px;
            background: #242c3d;
            border-radius: 3px;
        }
        QSlider::sub-page:horizontal {
            background: #00e5ff;
            border-radius: 3px;
        }
        QSlider::handle:horizontal {
            background: #ffffff;
            border: 2px solid #00b4d8;
            width: 18px;
            margin-top: -6px;
            margin-bottom: -6px;
            border-radius: 9px;
        }
        QSlider::handle:horizontal:hover {
            background: #00e5ff;
        }
        QComboBox, QSpinBox {
            background-color: #1a202c;
            color: #e2e8f0;
            border: 1px solid #2e384f;
            border-radius: 6px;
            padding: 4px 8px;
        }
        QCheckBox {
            color: #cbd5e1;
            font-weight: 500;
        }
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
            border-radius: 4px;
            border: 1px solid #334155;
            background-color: #1e2536;
        }
        QCheckBox::indicator:checked {
            background-color: #00e5ff;
            border-color: #00e5ff;
        }
        QStatusBar {
            background-color: #0c0e14;
            color: #94a3b8;
            border-top: 1px solid #1a202c;
        }
        """
        self.setStyleSheet(qss)

# ---------------------------------------------------------------------------
# ТОЧКА ВХОДА
# ---------------------------------------------------------------------------

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    win = BookLightStudioWindow()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
