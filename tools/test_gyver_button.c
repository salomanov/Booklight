#include <stdio.h>
#include <stdbool.h>
#include <assert.h>
#include "../custom_firmware/gyver_ubutton.h"

int main(void)
{
    printf("============================================================\n");
    printf("   GYVER UBUTTON AUTOMATED TEST SUITE (C99)\n");
    printf("============================================================\n");

    ubutton_t btn;
    ubutton_init(&btn);

    uint32_t now = 0;
    int events_count = 0;

    // --- TEST 1: Noise Filter (< 25 ms) ---
    printf("[1] Testing noise pulse (15 ms)... ");
    ubutton_tick(&btn, true, now);
    now += 15;
    ubutton_tick(&btn, false, now);
    now += 10;
    ubutton_tick(&btn, false, now);
    assert(btn.pressed == false);
    assert(ubutton_click(&btn) == false);
    printf("PASSED (Noise ignored!)\n");

    // --- TEST 2: Single Click (120 ms pulse) ---
    printf("[2] Testing single click (120 ms pulse)... ");
    ubutton_reset(&btn);
    now += 100;
    ubutton_tick(&btn, true, now); // Press down
    now += 30; // Debounce passed
    ubutton_tick(&btn, true, now);
    assert(ubutton_press(&btn) == true);

    now += 90; // Total 120 ms
    ubutton_tick(&btn, false, now); // Release
    now += 30; // Debounce release
    ubutton_tick(&btn, false, now);
    assert(ubutton_click(&btn) == true);
    assert(ubutton_get_clicks(&btn) == 1);
    printf("PASSED (Single click registered!)\n");

    // --- TEST 3: Double Click ---
    printf("[3] Testing double click... ");
    ubutton_reset(&btn);
    now += 400; // Reset state
    ubutton_tick(&btn, false, now);

    // Click 1:
    ubutton_tick(&btn, true, now);
    now += 30; ubutton_tick(&btn, true, now);
    now += 80; ubutton_tick(&btn, false, now);
    now += 30; ubutton_tick(&btn, false, now);
    assert(ubutton_single_click(&btn) == true);

    // Click 2 (within 150 ms):
    now += 100;
    ubutton_tick(&btn, true, now);
    now += 30; ubutton_tick(&btn, true, now);
    now += 80; ubutton_tick(&btn, false, now);
    now += 30; ubutton_tick(&btn, false, now);
    assert(ubutton_double_click(&btn) == true);
    assert(ubutton_get_clicks(&btn) == 2);
    printf("PASSED (Double click registered!)\n");

    // --- TEST 4: Hold & Step Dimming ---
    printf("[4] Testing hold & periodic step dimming... ");
    ubutton_reset(&btn);
    now += 500;
    ubutton_tick(&btn, true, now);
    now += 30; ubutton_tick(&btn, true, now); // Pressed

    now += 400; // Reached UB_HOLD_TIME_MS (400 ms)
    bool hold_fired = ubutton_tick(&btn, true, now);
    assert(hold_fired == true);
    assert(ubutton_hold(&btn) == true);

    int steps = 0;
    for (int i = 0; i < 10; i++) {
        now += 25; // UB_STEP_PRD_MS
        if (ubutton_tick(&btn, true, now) && ubutton_step(&btn)) {
            steps++;
        }
    }
    assert(steps >= 9);
    printf("PASSED (Hold detected + %d dimming steps!)\n", steps);

    // --- TEST 5: Long Hold (> 1200 ms) ---
    printf("[5] Testing long hold threshold (> 1200 ms)... ");
    // Keep holding until 1300 ms total
    now += 700;
    bool long_hold_detected = false;
    for (int t = 0; t < 30; t++) {
        now += 25;
        if (ubutton_tick(&btn, true, now)) {
            if (ubutton_long_hold(&btn)) {
                long_hold_detected = true;
            }
        }
    }
    assert(long_hold_detected == true);
    printf("PASSED (Long hold > 1.2s detected!)\n");

    // --- TEST 6: Release Step ---
    printf("[6] Testing release after steps... ");
    now += 50;
    ubutton_tick(&btn, false, now);
    now += 30;
    ubutton_tick(&btn, false, now);
    assert(ubutton_release_step(&btn) == true);
    printf("PASSED (Release-step fired!)\n");

    printf("\n============================================================\n");
    printf("   🎉 ALL 6 GYVER BUTTON UNIT TESTS PASSED 100%%! 🎉\n");
    printf("============================================================\n");
    return 0;
}
