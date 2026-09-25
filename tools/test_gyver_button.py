"""
Automated Test Suite for Gyver uButton State Machine
Uses separate deb_tmr and hold_tmr for 100% rock-solid debouncing and event detection.
"""

UB_DEB_TIME_MS      = 25
UB_HOLD_TIME_MS     = 400
UB_STEP_PRD_MS      = 25
UB_LONG_HOLD_MS     = 1200
UB_CLICK_TIMEOUT_MS = 280

class GyverButtonTest:
    def __init__(self):
        self.reset()

    def reset(self):
        self.state = 'IDLE'
        self.last_event = 'NONE'
        self.deb_tmr = 0
        self.hold_tmr = 0
        self.press_start_ms = 0
        self.last_release_ms = 0
        self.clicks = 0
        self.pressed = False
        self.is_step_active = False
        self.long_hold_fired = False
        self.hold_duration_ms = 0

    def tick(self, pin_state: bool, now_ms: int) -> bool:
        self.last_event = 'NONE'

        # State transition back from one-shot states
        if self.state == 'PRESS':
            self.state = 'WAIT_HOLD'
        elif self.state in ('CLICK', 'RELEASE', 'RELEASE_STEP'):
            self.state = 'IDLE'
        elif self.state in ('HOLD', 'STEP'):
            self.state = 'WAIT_STEP'

        # 1. Dedicated Debounce logic
        if pin_state != self.pressed:
            if self.deb_tmr == 0:
                self.deb_tmr = now_ms
            elif now_ms - self.deb_tmr >= UB_DEB_TIME_MS:
                self.pressed = pin_state
                self.deb_tmr = 0

                if self.pressed:
                    self.state = 'PRESS'
                    self.last_event = 'PRESS'
                    self.hold_tmr = now_ms
                    self.press_start_ms = now_ms
                    self.is_step_active = False
                    self.long_hold_fired = False
                    self.hold_duration_ms = 0
                    return True
                else:
                    self.hold_duration_ms = now_ms - self.press_start_ms

                    if self.is_step_active:
                        self.state = 'RELEASE_STEP'
                        self.last_event = 'RELEASE_STEP'
                        self.clicks = 0
                        return True
                    elif self.state == 'WAIT_STEP':
                        self.state = 'RELEASE'
                        self.last_event = 'RELEASE'
                        self.clicks = 0
                        return True
                    elif self.state == 'WAIT_HOLD':
                        self.clicks += 1
                        self.last_release_ms = now_ms
                        self.state = 'CLICK'
                        if self.clicks == 1:
                            self.last_event = 'CLICK'
                        elif self.clicks == 2:
                            self.last_event = 'DOUBLE_CLICK'
                        else:
                            self.last_event = 'MULTI_CLICK'
                        return True
                    else:
                        self.state = 'RELEASE'
                        self.last_event = 'RELEASE'
                        return True
        else:
            self.deb_tmr = 0

        # 2. Multi-click timeout
        if not self.pressed and self.clicks > 0:
            if now_ms - self.last_release_ms >= UB_CLICK_TIMEOUT_MS:
                self.clicks = 0

        # 3. Holding & steps
        if self.pressed:
            self.hold_duration_ms = now_ms - self.press_start_ms

            if self.state == 'WAIT_HOLD':
                if now_ms - self.press_start_ms >= UB_HOLD_TIME_MS:
                    self.state = 'HOLD'
                    self.last_event = 'HOLD'
                    self.hold_tmr = now_ms
                    self.clicks = 0
                    return True
            elif self.state == 'WAIT_STEP':
                if not self.long_hold_fired and (now_ms - self.press_start_ms >= UB_LONG_HOLD_MS):
                    self.long_hold_fired = True
                    self.last_event = 'LONG_HOLD'
                    return True

                if now_ms - self.hold_tmr >= UB_STEP_PRD_MS:
                    self.state = 'STEP'
                    self.last_event = 'STEP'
                    self.is_step_active = True
                    self.hold_tmr = now_ms
                    return True

        return False


def run_tests():
    print("=" * 60)
    print("   GYVER UBUTTON AUTOMATED TEST SUITE")
    print("=" * 60)

    btn = GyverButtonTest()
    now = 0

    # TEST 1: Noise Pulse (< 25ms)
    print("[1] Testing noise pulse (15 ms)...", end=" ")
    btn.tick(True, now)
    now += 15
    btn.tick(False, now)
    now += 10
    btn.tick(False, now)
    assert not btn.pressed, "Button should remain unpressed for < 25ms pulse"
    assert btn.last_event == 'NONE', "No event should fire for noise pulse"
    print("PASSED (Noise pulse < 25ms completely filtered!)")

    # TEST 2: Single Click
    print("[2] Testing single click (120 ms pulse)...", end=" ")
    btn.reset()
    now += 100
    btn.tick(True, now)
    now += 30
    btn.tick(True, now)
    assert btn.last_event == 'PRESS', "Press event expected"

    now += 90 # 120 ms hold
    btn.tick(False, now)
    now += 30 # Debounce release
    btn.tick(False, now)
    assert btn.last_event == 'CLICK', "Click event expected"
    assert btn.clicks == 1, "Click count should be 1"
    print("PASSED (Single click cleanly registered!)")

    # TEST 3: Double Click
    print("[3] Testing double click...", end=" ")
    btn.reset()
    now += 500
    btn.tick(False, now)

    # Click 1
    btn.tick(True, now)
    now += 30; btn.tick(True, now)
    now += 80; btn.tick(False, now)
    now += 30; btn.tick(False, now)
    assert btn.last_event == 'CLICK'

    # Click 2 within 150 ms
    now += 120
    btn.tick(True, now)
    now += 30; btn.tick(True, now)
    now += 80; btn.tick(False, now)
    now += 30; btn.tick(False, now)
    assert btn.last_event == 'DOUBLE_CLICK', "Double click event expected"
    assert btn.clicks == 2, "Click count should be 2"
    print("PASSED (Double click event cleanly registered!)")

    # TEST 4: Hold & Smooth Step Dimming
    print("[4] Testing hold & smooth step dimming...", end=" ")
    btn.reset()
    now += 500
    btn.tick(True, now)
    now += 30; btn.tick(True, now) # Pressed down

    now += 400 # Reach hold threshold
    fired = btn.tick(True, now)
    assert fired and btn.last_event == 'HOLD', "Hold event expected at 400ms"

    step_count = 0
    for _ in range(15):
        now += 25
        if btn.tick(True, now) and btn.last_event == 'STEP':
            step_count += 1
    assert step_count >= 14, f"Expected ~15 steps, got {step_count}"
    print(f"PASSED (Hold detected + {step_count} dimming steps!)")

    # TEST 5: Long Hold Threshold (> 1200 ms)
    print("[5] Testing long hold threshold (> 1200 ms)...", end=" ")
    long_hold_seen = False
    for _ in range(30):
        now += 25
        if btn.tick(True, now) and btn.last_event == 'LONG_HOLD':
            long_hold_seen = True
            break
    assert long_hold_seen, "Long hold event expected after 1200ms"
    print("PASSED (Long hold > 1.2s cleanly triggered!)")

    # TEST 6: Release Step
    print("[6] Testing release after steps...", end=" ")
    now += 50
    btn.tick(False, now)
    now += 30
    btn.tick(False, now)
    assert btn.last_event == 'RELEASE_STEP', "Release step event expected"
    print("PASSED (Release-step cleanly triggered for dimming direction reverse!)")

    print("=" * 60)
    print("   [SUCCESS] ALL 6 GYVER BUTTON UNIT TESTS PASSED 100%!")
    print("=" * 60)

if __name__ == '__main__':
    run_tests()
