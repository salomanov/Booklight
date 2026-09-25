#include "gyver_ubutton.h"

void ubutton_init(ubutton_t *b)
{
    ubutton_reset(b);
}

void ubutton_reset(ubutton_t *b)
{
    b->state = UB_STATE_IDLE;
    b->last_event = UB_EVT_NONE;
    b->deb_tmr = 0;
    b->hold_tmr = 0;
    b->press_start_ms = 0;
    b->last_release_ms = 0;
    b->clicks = 0;
    b->pressed = false;
    b->is_step_active = false;
    b->long_hold_fired = false;
    b->hold_duration_ms = 0;
}

bool ubutton_tick(ubutton_t *b, bool pin_state, uint32_t now_ms)
{
    /* Always clear one-shot event at beginning of each tick */
    b->last_event = UB_EVT_NONE;

    /* Transition internal states back from one-shot states */
    switch (b->state) {
        case UB_STATE_PRESS:
            b->state = UB_STATE_WAIT_HOLD;
            break;
        case UB_STATE_CLICK:
        case UB_STATE_RELEASE:
        case UB_STATE_RELEASE_HOLD:
        case UB_STATE_RELEASE_STEP:
            b->state = UB_STATE_IDLE;
            break;
        case UB_STATE_HOLD:
        case UB_STATE_STEP:
            b->state = UB_STATE_WAIT_STEP;
            break;
        default:
            break;
    }

    /* 1. Dedicated Debounce logic */
    if (pin_state != b->pressed) {
        if (b->deb_tmr == 0) {
            b->deb_tmr = now_ms;
        } else if (now_ms - b->deb_tmr >= UB_DEB_TIME_MS) {
            b->pressed = pin_state;
            b->deb_tmr = 0;

            if (b->pressed) {
                /* Button just pressed down */
                b->state = UB_STATE_PRESS;
                b->last_event = UB_EVT_PRESS;
                b->hold_tmr = now_ms;
                b->press_start_ms = now_ms;
                b->is_step_active = false;
                b->long_hold_fired = false;
                b->hold_duration_ms = 0;
                return true;
            } else {
                /* Button just released */
                b->hold_duration_ms = now_ms - b->press_start_ms;

                if (b->is_step_active) {
                    b->state = UB_STATE_RELEASE_STEP;
                    b->last_event = UB_EVT_RELEASE_STEP;
                    b->clicks = 0;
                    return true;
                } else if (b->state == UB_STATE_WAIT_STEP) {
                    b->state = UB_STATE_RELEASE_HOLD;
                    b->last_event = UB_EVT_RELEASE;
                    b->clicks = 0;
                    return true;
                } else if (b->state == UB_STATE_WAIT_HOLD) {
                    /* Short click registered */
                    b->clicks++;
                    b->last_release_ms = now_ms;
                    b->state = UB_STATE_CLICK;
                    if (b->clicks == 1) {
                        b->last_event = UB_EVT_CLICK;
                    } else if (b->clicks == 2) {
                        b->last_event = UB_EVT_DOUBLE_CLICK;
                    } else {
                        b->last_event = UB_EVT_MULTI_CLICK;
                    }
                    return true;
                } else {
                    b->state = UB_STATE_RELEASE;
                    b->last_event = UB_EVT_RELEASE;
                    return true;
                }
            }
        }
    } else {
        b->deb_tmr = 0;
    }

    /* 2. Check multi-click counter reset timeout */
    if (!b->pressed && b->clicks > 0) {
        if (now_ms - b->last_release_ms >= UB_CLICK_TIMEOUT_MS) {
            b->clicks = 0;
        }
    }

    /* 3. Timed state transitions while button remains held down */
    if (b->pressed) {
        b->hold_duration_ms = now_ms - b->press_start_ms;

        if (b->state == UB_STATE_WAIT_HOLD) {
            if (now_ms - b->press_start_ms >= UB_HOLD_TIME_MS) {
                b->state = UB_STATE_HOLD;
                b->last_event = UB_EVT_HOLD;
                b->hold_tmr = now_ms;
                b->clicks = 0;
                return true;
            }
        } else if (b->state == UB_STATE_WAIT_STEP) {
            /* Check Long Hold threshold (>1200 ms) */
            if (!b->long_hold_fired && (now_ms - b->press_start_ms >= UB_LONG_HOLD_MS)) {
                b->long_hold_fired = true;
                b->last_event = UB_EVT_LONG_HOLD;
                return true;
            }

            /* Periodic step ramp for smooth dimming */
            if (now_ms - b->hold_tmr >= UB_STEP_PRD_MS) {
                b->state = UB_STATE_STEP;
                b->last_event = UB_EVT_STEP;
                b->is_step_active = true;
                b->hold_tmr = now_ms;
                return true;
            }
        }
    }

    return false;
}

