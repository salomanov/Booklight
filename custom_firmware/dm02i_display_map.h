// Автоматически сгенерированная карта сегментов DM02i V03
#ifndef DM02I_DISPLAY_MAP_H
#define DM02I_DISPLAY_MAP_H

typedef struct {
    const char *name;
    uint8_t high_pin;
    uint8_t low_pin;
} SegmentMap_t;

static const SegmentMap_t DM02I_SEGMENTS[] = {
    {"Цифра 1 Сегм D", PB5_IDX, PB0_IDX},
    {"Цифра 2 Сегм G", PB5_IDX, PB2_IDX},
    {"BOOST Диод 4", PB5_IDX, PB3_IDX},
    {"Цифра 1 Сегм F", PB0_IDX, PB1_IDX},
    {"Цифра 2 Сегм D", PB0_IDX, PB2_IDX},
    {"BOOST Буква B", PB0_IDX, PB3_IDX},
    {"Сотня 1 (Низ)", PB0_IDX, PB5_IDX},
    {"Цифра 1 Сегм A", PB1_IDX, PB0_IDX},
    {"Цифра 2 Сегм E", PB1_IDX, PB2_IDX},
    {"BOOST Буква T", PB1_IDX, PB3_IDX},
    {"Молния", PB1_IDX, PB5_IDX},
    {"Цифра 1 Сегм B", PB2_IDX, PB0_IDX},
    {"Цифра 1 Сегм G", PB2_IDX, PB1_IDX},
    {"BOOST Диод 2", PB2_IDX, PB3_IDX},
    {"- 3", PB2_IDX, PB5_IDX},
    {"Цифра 1 Сегм C", PB3_IDX, PB0_IDX},
    {"Цифра 2 Сегм A", PB3_IDX, PB1_IDX},
    {"Цифра 2 Сегм F", PB3_IDX, PB2_IDX},
    {"- 2", PB3_IDX, PB5_IDX},
};

#endif
