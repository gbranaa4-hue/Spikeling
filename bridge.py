import sys, time, math, serial, winsound, pyautogui
sys.path.insert(0, "core")
from compiler.compiler import SpikelingParser
from runtime.runtime import SpikelingRuntime

# FAILSAFE stays ON (default) for cursor control -- slamming the physical mouse
# to the screen's top-left corner immediately aborts the script if movement
# ever goes out of control. Real safety net, not decorative.

# pyautogui's hidden default: a 0.1s pause after EVERY call (moveRel, click,
# etc), meant as a general safety margin -- but since moveRel() fires every
# loop iteration here, that alone was adding real compounding lag on top of
# the Arduino's own refresh cycle. Confirmed and removed, not just guessed.
pyautogui.PAUSE = 0

with open("proximity_grid.spk") as f:
    ast = SpikelingParser().parse(f.read())
rt = SpikelingRuntime(ast)

# Movement: the 4 outer zones push the cursor continuously, proportional to
# closeness -- an analog-joystick model, not discrete jumps. Center is a dead
# zone for movement (no push) and instead drives a real Spikeling LIF neuron
# for click detection: its threshold/leak integrate-and-fire dynamics are
# naturally suited to "sustained enough proximity = a deliberate click", which
# is a genuinely different computation than proportional velocity control --
# hence the split: raw distance math for continuous movement, real neuron
# dynamics for the discrete click event.
DIRECTIONS = {
    "Left":        (-1.0,  0.0),
    "UpperRight":  ( 0.707, -0.707),
    "BottomRight": ( 0.707,  0.707),
    # BottomLeft disabled per request -- was intercepting left/right movement
    # (its physical position sits in the natural hand-approach path). Sensor
    # itself is still read from serial and still drives nothing; simply left
    # out of DIRECTIONS so it can never win a zone.
}
MAX_SPEED_PX = 35.0   # pixels per loop iteration at closest range (bumped up from 15 --
                       # the PAUSE fix above already helps responsiveness, this makes the
                       # movement itself feel punchier once it gets an update)
DEAD_ZONE_PX = 1.0    # ignore total speed below this -- avoids constant micro-jitter

# HYSTERESIS: once a zone has "control" of the cursor, another zone only
# takes over if it reads meaningfully closer -- not just closer by a noise-
# level margin. Without this, near-tied readings between neighboring zones
# (the same flickering seen earlier in the position-label test) cause the
# selected direction to flip almost every loop, which reads as the cursor
# randomly hovering/jittering instead of moving decisively.
SWITCH_MARGIN_CM = 4.0     # widened from 2.0 -- a real pass-by can genuinely read
                           # closer for a moment, not just noise-level, so distance
                           # margin alone isn't enough; paired with a time confirm below
SWITCH_CONFIRM_TICKS = 3   # a candidate must win for 3 consecutive readings (~300ms)
                           # before it's allowed to steal control from the current zone --
                           # filters out brief pass-by without slowing down first pickup
current_zone = None
_pending_zone = None
_pending_count = 0

CLICK_COOLDOWN_S = 0.5
_last_click = 0.0

def on_center_fire():
    global _last_click
    now = time.time()
    if now - _last_click < CLICK_COOLDOWN_S:
        return
    _last_click = now
    print("*** CLICK ***", flush=True)
    winsound.Beep(523, 100)
    pyautogui.click()

rt.register_handler("NEAR_CENTER", on_center_fire)

names = ["Left", "Center", "UpperRight", "BottomLeft", "BottomRight"]
print("Opening COM3...", flush=True)
ser = serial.Serial("COM3", 9600, timeout=1)
print("Connected. Hover over Left/UpperRight/BottomRight to move the", flush=True)
print("cursor, hold over Center to click. Move mouse to top-left corner to abort.", flush=True)
t0 = time.time()

while True:
    line = ser.readline().decode(errors="ignore").strip()
    if not line:
        continue
    try:
        dists = [float(x) for x in line.split(",") if x]
    except ValueError:
        continue
    if len(dists) != 5:
        continue

    readings = dict(zip(names, dists))
    now_ms = (time.time() - t0) * 1000

    # WINNER-TAKE-ALL + HYSTERESIS: move using only one zone at a time, and
    # don't switch away from the current one unless a candidate is closer by
    # a real margin (SWITCH_MARGIN_CM), not just noise.
    dx, dy = 0.0, 0.0
    candidate_zone, candidate_d = None, 1e9
    for zone in DIRECTIONS:
        d = readings[zone]
        if d >= 0 and d < candidate_d:
            candidate_zone, candidate_d = zone, d

    current_d = readings.get(current_zone, -1) if current_zone else -1
    if current_d < 0:
        current_d = 1e9   # current zone lost its signal entirely -- free to reconsider

    if current_zone is None:
        # nothing engaged yet -- pick up immediately, no need to protect against a steal
        if candidate_zone is not None:
            current_zone = candidate_zone
        _pending_zone, _pending_count = None, 0
    elif candidate_zone is not None and candidate_zone != current_zone and candidate_d < current_d - SWITCH_MARGIN_CM:
        # something already has control -- require the candidate to win by a real
        # margin AND hold that lead for several consecutive readings before it can steal it
        if candidate_zone == _pending_zone:
            _pending_count += 1
        else:
            _pending_zone, _pending_count = candidate_zone, 1
        if _pending_count >= SWITCH_CONFIRM_TICKS:
            current_zone = candidate_zone
            _pending_zone, _pending_count = None, 0
    else:
        _pending_zone, _pending_count = None, 0

    if current_zone is not None:
        d = readings[current_zone]
        drive = max(0.0, 120.0 - 4.0 * d) if d >= 0 else 0.0
        if drive <= 0:
            current_zone = None   # released -- nothing close enough anymore
        else:
            speed = (drive / 120.0) * MAX_SPEED_PX
            ux, uy = DIRECTIONS[current_zone]
            dx, dy = ux * speed, uy * speed

    if math.hypot(dx, dy) > DEAD_ZONE_PX:
        try:
            pyautogui.moveRel(dx, dy, duration=0)
        except pyautogui.FailSafeException:
            print("FAILSAFE triggered -- stopping.", flush=True)
            break

    # Center -> real Spikeling LIF neuron, click on sustained fire
    d_center = readings["Center"]
    drive_center = max(0.0, 120.0 - 4.0 * d_center) if d_center >= 0 else 0.0
    rt.stimulate("Center", now_ms, drive=drive_center)
