#ifndef GYVER_UBUTTON_H
#define GYVER_UBUTTON_H

#include <stdint.h>
#include <stdbool.h>

/**
 * Pure C implementation of AlexGyver's uButton / EncButton finite state machine.
 * Provides rock-solid debouncing, click, multi-click, hold, step dimming, and long-press.
 */

#define UB_DEB_TIME_MS      25U     /* Debounce time in ms */
#define UB_HOLD_TIME_MS     400U    /* Time before entering hold state in ms */
#define UB_STEP_PRD_MS      25U     /* Periodic step rate while holding in ms (dimming ramp) */
#define UB_LONG_HOLD_MS     1200U   /* Time before triggering long press in ms */
#define UB_CLICK_TIMEOUT_MS 280U    /* Timeout to wait for next click in multi-click in ms */

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

typedef enum {
    UB_EVT_NONE = 0,
    UB_EVT_PRESS,
    UB_EVT_CLICK,
    UB_EVT_DOUBLE_CLICK,
    UB_EVT_MULTI_CLICK,
    UB_EVT_HOLD,
    UB_EVT_STEP,
    UB_EVT_RELEASE_STEP,
    UB_EVT_RELEASE,
    UB_EVT_LONG_HOLD
} ubutton_event_t;

typedef struct {
    uint32_t deb_tmr;           /* Dedicated debounce timer */
    uint32_t hold_tmr;          /* Dedicated timer for hold and step intervals */
    uint32_t press_start_ms;    /* Timestamp when press started */
    uint32_t last_release_ms;   /* Timestamp when button was released */
    ubutton_state_t state;      /* Current internal state */
    ubutton_event_t last_event; /* Most recent one-shot event */
    uint8_t clicks;             /* Number of clicks registered */
    bool pressed;               /* Raw debounced press state */
    bool is_step_active;        /* True if at least one step has fired during hold */
    bool long_hold_fired;       /* True if long hold event has already triggered */
    uint32_t hold_duration_ms;  /* Duration button is currently held in ms */
} ubutton_t;

void ubutton_init(ubutton_t *b);
void ubutton_reset(ubutton_t *b);

/* Call periodically (e.g. every 1-5 ms) with current pin state (true = touched/pressed) */
bool ubutton_tick(ubutton_t *b, bool pin_state, uint32_t now_ms);

/* Gyver-style event getters (true only for 1 tick when event occurs) */
static inline bool ubutton_press(const ubutton_t *b)        { return b->last_event == UB_EVT_PRESS; }
static inline bool ubutton_click(const ubutton_t *b)        { return b->last_event == UB_EVT_CLICK || b->last_event == UB_EVT_DOUBLE_CLICK || b->last_event == UB_EVT_MULTI_CLICK; }
static inline bool ubutton_single_click(const ubutton_t *b) { return b->last_event == UB_EVT_CLICK; }
static inline bool ubutton_double_click(const ubutton_t *b) { return b->last_event == UB_EVT_DOUBLE_CLICK; }
static inline bool ubutton_has_clicks(const ubutton_t *b, uint8_t n) { return (b->last_event == UB_EVT_CLICK || b->last_event == UB_EVT_DOUBLE_CLICK || b->last_event == UB_EVT_MULTI_CLICK) && b->clicks == n; }
static inline uint8_t ubutton_get_clicks(const ubutton_t *b){ return b->clicks; }

static inline bool ubutton_hold(const ubutton_t *b)         { return b->last_event == UB_EVT_HOLD; }
static inline bool ubutton_long_hold(const ubutton_t *b)    { return b->last_event == UB_EVT_LONG_HOLD; }
static inline bool ubutton_step(const ubutton_t *b)         { return b->last_event == UB_EVT_STEP; }
static inline bool ubutton_release_step(const ubutton_t *b) { return b->last_event == UB_EVT_RELEASE_STEP; }
static inline bool ubutton_release(const ubutton_t *b)      { return b->last_event == UB_EVT_RELEASE || b->last_event == UB_EVT_RELEASE_STEP; }
static inline bool ubutton_is_pressed(const ubutton_t *b)   { return b->pressed; }
static inline uint32_t ubutton_get_hold_ms(const ubutton_t *b) { return b->hold_duration_ms; }

#endif /* GYVER_UBUTTON_H */
