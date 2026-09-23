#include "gyver_ubutton.h"

void ubutton_init(ubutton_t *b)
{
    ubutton_reset(b);
}

void ubutton_reset(ubutton_t *b)
{
    b->state = UB_STATE_IDLE;
    b->tmr = 0;
    b->pressed = false;
    b->is_step_active = false;
}

bool ubutton_tick(ubutton_t *b, bool pin_state, uint32_t now_ms)
{
    /* Clear one-shot event states to Idle/Wait */
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

    /* Debounce raw input */
    if (pin_state != b->pressed) {
        if (b->tmr == 0) {
            b->tmr = now_ms;
        } else if (now_ms - b->tmr >= UB_DEB_TIME_MS) {
            b->pressed = pin_state;
            b->tmr = 0;

            if (b->pressed) {
                /* Button just pressed down */
                b->state = UB_STATE_PRESS;
                b->tmr = now_ms;
                b->is_step_active = false;
                return true;
            } else {
                /* Button just released */
                if (b->is_step_active) {
                    b->state = UB_STATE_RELEASE_STEP;
                } else if (b->state == UB_STATE_WAIT_STEP) {
                    b->state = UB_STATE_RELEASE_HOLD;
                } else if (b->state == UB_STATE_WAIT_HOLD) {
                    b->state = UB_STATE_CLICK;
                } else {
                    b->state = UB_STATE_RELEASE;
                }
                b->tmr = 0;
                return true;
            }
        }
    } else {
        b->tmr = 0;
    }

    /* Timed state transitions while button remains held */
    if (b->pressed) {
        if (b->state == UB_STATE_WAIT_HOLD) {
            if (now_ms - b->tmr >= UB_HOLD_TIME_MS) {
                b->state = UB_STATE_HOLD;
                b->tmr = now_ms;
                return true;
            }
        } else if (b->state == UB_STATE_WAIT_STEP) {
            if (now_ms - b->tmr >= UB_STEP_PRD_MS) {
                b->state = UB_STATE_STEP;
                b->is_step_active = true;
                b->tmr = now_ms;
                return true;
            }
        }
    }

    return false;
}