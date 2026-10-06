"""Process-local counter. Not the order record and not read by the HTTP handlers."""
HOLD_COUNT = 0
def inc_hold() -> None:
    global HOLD_COUNT
    HOLD_COUNT += 1
