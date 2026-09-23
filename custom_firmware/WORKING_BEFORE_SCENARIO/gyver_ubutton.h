#ifndef GYVER_UBUTTON_H
#define GYVER_UBUTTON_H

#include <stdint.h>
#include <stdbool.h>

/**
 * Pure C implementation of AlexGyver's uButton / EncButton finite state machine.
 * Provides rock-solid debouncing, click, hold, and periodic step events for dimming.
 */

#define UB_DEB_TIME_MS      25U     /* Debounce time in ms */
#define UB_HOLD_TIME_MS     400U    /* Time before entering hold state in ms */
#define UB_STEP_PRD_MS      25U     /* Periodic step rate while holding in ms (dimming ramp) */

typedef enum {
    UB_STATE_IDLE = 0,
    UB_STATE_PRESS,
    UB_STATE_WAIT_HOLD,
    UB_STATE_HOLD,
    UB_STATE_STEP,
    UB_STATE_WAIT_STEP,
    UB_STATE_CLICK,
    UB_STATE_RELEASE_HOLD,
    UB_STATE_RELEASE_STEP,
    UB_STATE_RELEASE
} ubutton_state_t;

typedef struct {
    uint32_t tmr;           /* State transition timer */
    ubutton_state_t state;  /* Current state */
    bool pressed;           /* Raw debounced press state */
    bool is_step_active;    /* True if at least one step has fired during hold */
} ubutton_t;

void ubutton_init(ubutton_t *b);
void ubutton_reset(ubutton_t *b);

/* Call periodically (e.g. every 1-5 ms) with current pin state (true = touched/pressed) */
bool ubutton_tick(ubutton_t *b, bool pin_state, uint32_t now_ms);

/* Gyver-style event getters (true only for 1 tick when event occurs) */
static inline bool ubutton_press(const ubutton_t *b)        { return b->state == UB_STATE_PRESS; }
static inline bool ubutton_click(const ubutton_t *b)        { return b->state == UB_STATE_CLICK; }
static inline bool ubutton_hold(const ubutton_t *b)         { return b->state == UB_STATE_HOLD; }
static inline bool ubutton_step(const ubutton_t *b)         { return b->state == UB_STATE_STEP; }
static inline bool ubutton_release_step(const ubutton_t *b) { return b->state == UB_STATE_RELEASE_STEP; }
static inline bool ubutton_release(const ubutton_t *b)      { return b->state == UB_STATE_RELEASE || b->state == UB_STATE_RELEASE_STEP; }
static inline bool ubutton_is_pressed(const ubutton_t *b)   { return b->pressed; }

#endif /* GYVER_UBUTTON_H */