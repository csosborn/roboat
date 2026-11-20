"""State of charge for the boat's 12 V LiFePO4 battery.

Counts charge, and uses voltage only where it means something. The numbers come
from the cycles in docs/battery/README.md:

- Discharge is counted from the INA260's logic-side current. The Victron's
  battery current has 10 mA steps, a dead-band below ~30 mA, and an offset
  that drifts by tens of mA, so it's used only when it reads far more than the
  INA260: the ESC draws from the load output outside the INA260.
- Neither sensor sees what the MPPT itself uses (~21 mA, metered 2026-11-19)
  or the Smart Battery Sense (~0.7 mA). That draw is subtracted whenever
  nothing is charging, including while the load output is off.
- Charging is counted from the Victron, which reads ~5% low there (a meter in
  the battery lead, and the October and November charge/discharge balance).
- Full: 14.1 V or more with under 0.5 A going in, or the Victron in float.
- Voltage corrects the count only at steady, light discharge, at least
  QUIET_MS after any charging, and is compensated for the battery's ~0.2 ohm:
  in the final knee (below ~13.06 V) as a measurement, and on the two plateaus
  as a bound (the upper plateau means at least ~11.5 Ah left; the lower one at
  most ~10.5).
- The charge left is reported to the Victron's 12.0 V load cut-off, so 0%
  means the load output is about to turn off.
- Capacity is learned from each full-to-knee or knee-to-full stretch.
- The state is kept in flash, so a reset doesn't restart the estimate from a
  guess at the voltage. After a reset nothing is saved until the GPS clock
  says how long the board was down; until then the older save, with its own
  time, is the one to come back to.

Estimates carry a standard deviation, which grows while counting and shrinks
at each landmark. The charge is held as integer milliamp-seconds: the RP2040's
floats are too coarse to add up milliamp currents a second at a time.
"""
import json
import os
import time

NOMINAL_CAPACITY_AH = 19.0   # full to the 12.0 V cut-off: 18.8 (2026-11), 19.7 (2026-10)
CAPACITY_MIN_AH = 12.0
CAPACITY_MAX_AH = 21.0
CAPACITY_LEARN_WEIGHT = 0.3

HIDDEN_DRAW_A = 0.022       # the MPPT's own ~21 mA plus the Battery Sense
CHARGING_A = 0.05           # above this, the Victron's reading is used
CHARGE_GAIN = 1.05          # the Victron's charging current reads ~5% low
# The Victron is used while discharging only when it reads this much more than
# the INA260 (the motor); below that, its offset drift is larger than anything
# it could add.
VICTRON_OVER_INA_A = 0.1
# Ohms. The instant step when the Pi switches is ~0.1; 0.2 also covers the
# slower relaxation, and lines up the Pi-on and Pi-off discharge curves.
INTERNAL_R = 0.2

FULL_V = 14.1
FULL_TAIL_A = 0.5
FULL_HOLD_MS = 120000
VICTRON_FLOAT = "5"         # VE.Direct CS (charger state)

# Counting error, as a standard deviation growth rate: a share of the current
# plus a fixed offset (the hidden draw's spread, the Victron's steps).
COUNT_GAIN_ERR = 0.02
COUNT_OFFSET_ERR_A = 0.008

# Voltage is trusted only at a light, steady discharge long after charging.
QUIET_MS = 2 * 3600 * 1000
LANDMARK_MAX_A = 1.0
LANDMARK_EVERY_MS = 300000
EMA_MS = 60000
COUNT_GAP_MS = 60000        # readings come every second; longer is a gap

# Knee: compensated volts -> (Ah left to the cut-off, standard deviation).
# The mean of the 2026-10 run-down (0.12-0.37 A) and the 2026-11 one (0.28 A
# Pi on, 0.03 A Pi off), counted as above; they agree within ~0.3 Ah. Above
# ~13.06 V the lower plateau is too flat (20 mV over 3 Ah) to read.
KNEE = (
    (12.056, 0.0, 0.15),
    (12.37, 0.28, 0.15),
    (12.59, 0.55, 0.2),
    (12.68, 0.84, 0.25),
    (12.71, 1.0, 0.3),
    (12.74, 1.57, 0.3),
    (12.76, 1.8, 0.35),
    (12.81, 2.1, 0.4),
    (12.865, 2.45, 0.45),
    (12.885, 2.85, 0.5),
    (12.92, 3.28, 0.6),
    (12.96, 3.75, 0.7),
    (13.00, 4.35, 0.8),
    (13.03, 4.85, 1.0),
    (13.06, 5.25, 1.2),
)
# Plateaus, as bounds: at or above UPPER_PLATEAU_V at least UPPER_MIN_AH is
# left; between the knee's top and LOWER_PLATEAU_V at most LOWER_MAX_AH. The
# step between them (~13.14-13.25 V compensated) sits at 10-12 Ah: both
# run-downs leave the upper plateau at ~12.1 Ah and the step at 9.9-10.4.
UPPER_PLATEAU_V = 13.25
UPPER_MIN_AH = 11.8
LOWER_PLATEAU_V = 13.14
LOWER_MAX_AH = 11.0
PLATEAU_SD_AH = 1.0

SAVE_EVERY_MS = 600000
STORE_FILE = "soc.json"
# Saved capacities are restored only from the same version: bump it when the
# counting changes, so the new nominal capacity takes over from one learned
# the old way. (1, unmarked: fused currents plus 11 mA.)
STORE_VERSION = 2
RESTORE_SD_AH = 0.3         # for counting lost since the last save
# Unknown draw while the RP2040 was down: the Pi's converter is on whenever
# its enable floats, so assume anything up to the Pi's load.
GAP_SD_A = 0.15
GAP_MAX_MS = 30 * 86400000

MAS_PER_AH = 3600000


def current(victron_a, logic_a, charging):
    """The battery's current (positive charging) from the two sensors."""
    if charging:
        return victron_a * CHARGE_GAIN if victron_a > 0 else victron_a
    i = min(victron_a, 0.0)
    if logic_a is not None and victron_a > -(abs(logic_a) + VICTRON_OVER_INA_A):
        i = -abs(logic_a)
    return i - HIDDEN_DRAW_A


def knee_lookup(v):
    """(Ah left, standard deviation) for a compensated voltage in the knee, or None."""
    if v > KNEE[-1][0]:
        return None
    if v <= KNEE[0][0]:
        return KNEE[0][1], KNEE[0][2]
    for (v0, a0, s0), (v1, a1, s1) in zip(KNEE, KNEE[1:]):
        if v <= v1:
            f = (v - v0) / (v1 - v0)
            return a0 + f * (a1 - a0), s0 + f * (s1 - s0)


class SocModel:

    def __init__(self, store=STORE_FILE, now_utc=None):
        self.store_ = store
        self.now_utc_ = now_utc   # () -> UTC ms or None
        self.capacity_ah = NOMINAL_CAPACITY_AH
        self.q_mas_ = None        # charge left to the cut-off, mA*s
        self.residual_ = 0        # mA*ms not yet folded into q_mas_
        self.var_ = 0.0           # Ah^2
        self.last_ms_ = None
        self.last_i_ = 0.0
        self.v_ema_ = None
        self.i_ema_ = None
        self.full_since_ = None
        self.full_synced_ = False
        self.charged_at_ = None   # ticks of the last charging, None if none seen
        self.landmark_ms_ = None
        self.saved_ms_ = None
        self.anchor_ = None       # ("full" | "knee", Ah left then); see _learn
        self.counted_mas_ = 0     # net charge since the anchor
        self.gap_from_utc_ = None # save time to settle once the clock is known
        self.boot_ms_ = None
        self.source = "none"      # how the estimate was last set
        self._restore()

    # -- reporting -----------------------------------------------------------

    @property
    def known(self):
        return self.q_mas_ is not None

    @property
    def remaining_ah(self):
        return self.q_mas_ / MAS_PER_AH

    @property
    def sd_ah(self):
        return self.var_ ** 0.5

    @property
    def soc(self):
        return min(1.0, max(0.0, self.remaining_ah / self.capacity_ah))

    def report(self):
        q, sd = self.remaining_ah, self.sd_ah
        cap = self.capacity_ah
        return {
            "soc": self.soc,
            "cap": q,
            "cap_min": max(0.0, q - sd),
            "cap_max": min(cap, q + sd),
            "sd": sd,
            "full_ah": cap,
            "basis": self.source,   # not "src": that's the Pi link's envelope
        }

    # -- the update ------------------------------------------------------------

    def update(self, now_ms, volts, victron_a, panel_w, logic_a=None,
               charger_state=None):
        """One reading. victron_a is the battery current (positive charging),
        logic_a the INA260's logic-side current or None if it isn't fresh.
        Returns True when the estimate is known."""
        if volts <= 0:
            return self.known
        if self.boot_ms_ is None:
            self.boot_ms_ = now_ms
        charging = panel_w > 0 or victron_a > CHARGING_A
        i = current(victron_a, logic_a, charging)

        if self.last_ms_ is not None:
            dt = time.ticks_diff(now_ms, self.last_ms_)
            if dt > COUNT_GAP_MS:
                # No readings for a while: assume only the hidden draw, and
                # widen the estimate for whatever else happened.
                self._count(-HIDDEN_DRAW_A, dt)
                self._widen(GAP_SD_A * dt / 3600000.0)
                self.v_ema_, self.i_ema_ = volts, i
            elif dt > 0:
                self._count(self.last_i_, dt)
                self._smooth(volts, i, dt)
        else:
            self.v_ema_, self.i_ema_ = volts, i
        self.last_ms_ = now_ms
        self.last_i_ = i
        if charging:
            self.charged_at_ = now_ms

        self._settle_gap(now_ms)
        if self.q_mas_ is None:
            self._first_guess(volts, i, charging)
        self._check_full(now_ms, volts, victron_a, charging, charger_state)
        self._check_voltage(now_ms)
        self._clamp()
        if self.saved_ms_ is None or time.ticks_diff(now_ms, self.saved_ms_) >= SAVE_EVERY_MS:
            self.save(now_ms)
        return self.known

    def _count(self, amps, dt_ms):
        self.residual_ += int(round(amps * 1000)) * dt_ms   # mA*ms
        r = self.residual_
        whole = r // 1000 if r >= 0 else -(-r // 1000)
        self.residual_ = r - whole * 1000
        self.counted_mas_ += whole
        if self.q_mas_ is not None:
            self.q_mas_ += whole
            # Counting errors are mostly steady biases, so they add up
            # linearly rather than like a random walk.
            self._widen((abs(amps) * COUNT_GAIN_ERR + COUNT_OFFSET_ERR_A) * dt_ms / 3600000.0)

    def _widen(self, sd_ah):
        if self.q_mas_ is not None:
            sd = self.var_ ** 0.5 + sd_ah
            self.var_ = sd * sd

    def _smooth(self, volts, amps, dt_ms):
        k = min(1.0, dt_ms / EMA_MS)
        self.v_ema_ += k * (volts - self.v_ema_)
        self.i_ema_ += k * (amps - self.i_ema_)

    def _set(self, ah, sd, source):
        self.q_mas_ = int(ah * MAS_PER_AH)
        self.var_ = sd * sd
        self.source = source

    def _measure(self, ah, sd, source):
        """Kalman update of the charge left with a measurement of it."""
        r = sd * sd
        k = self.var_ / (self.var_ + r)
        q = self.remaining_ah
        self.q_mas_ = int((q + k * (ah - q)) * MAS_PER_AH)
        # Successive voltage readings aren't independent, so never let them
        # claim more certainty than half the measurement's own.
        self.var_ = max((1 - k) * self.var_, r / 4)
        self.source = source

    def _clamp(self):
        if self.q_mas_ is None:
            return
        top = int(self.capacity_ah * MAS_PER_AH)
        if self.q_mas_ > top:
            self.q_mas_ = top
        elif self.q_mas_ < -int(0.5 * MAS_PER_AH):
            self.q_mas_ = -int(0.5 * MAS_PER_AH)   # below the cut-off, a little

    def _first_guess(self, volts, amps, charging):
        cap = self.capacity_ah
        if charging:
            self._set(cap / 2, cap / 2, "guess")
            return
        vc = volts - amps * INTERNAL_R
        knee = knee_lookup(vc)
        if knee is not None:
            self._set(knee[0], max(2 * knee[1], 0.5), "guess")
        elif vc >= UPPER_PLATEAU_V:
            self._set((UPPER_MIN_AH + cap) / 2, (cap - UPPER_MIN_AH) / 2, "guess")
        elif vc <= LOWER_PLATEAU_V:
            self._set((6.0 + LOWER_MAX_AH) / 2, 2.5, "guess")
        else:
            self._set((LOWER_MAX_AH + UPPER_MIN_AH) / 2, 2.0, "guess")

    # -- landmarks -------------------------------------------------------------

    def _check_full(self, now_ms, volts, victron_a, charging, charger_state):
        tail = volts >= FULL_V and 0 <= victron_a < FULL_TAIL_A
        floating = charger_state == VICTRON_FLOAT and charging
        if not (tail or floating):
            self.full_since_ = None
            self.full_synced_ = False
            return
        if self.full_since_ is None:
            self.full_since_ = now_ms
        if time.ticks_diff(now_ms, self.full_since_) < FULL_HOLD_MS:
            return
        if self.full_synced_:
            return  # once per absorption
        self.full_synced_ = True
        self.gap_from_utc_ = None   # full is full, however long the board was down
        self._learn(None, "full")
        self._set(self.capacity_ah, 0.15, "full")
        self.landmark_ms_ = now_ms
        self.save(now_ms)

    def _check_voltage(self, now_ms):
        if self.q_mas_ is None:
            return
        # Charging leaves the voltage high for a while. With none seen since
        # boot, it may have stopped just before the boot.
        since = self.charged_at_ if self.charged_at_ is not None else self.boot_ms_
        if time.ticks_diff(now_ms, since) < QUIET_MS:
            return
        if not (-LANDMARK_MAX_A < self.i_ema_ < 0):
            return
        if self.landmark_ms_ is not None and \
                time.ticks_diff(now_ms, self.landmark_ms_) < LANDMARK_EVERY_MS:
            return
        vc = self.v_ema_ - self.i_ema_ * INTERNAL_R
        q = self.remaining_ah
        knee = knee_lookup(vc)
        if knee is not None:
            ah, sd = knee
            self._measure(ah, sd, "knee")
            if sd <= 0.3:
                self._learn(ah, "knee")
        elif vc >= UPPER_PLATEAU_V:
            if q >= UPPER_MIN_AH:
                return
            self._measure(UPPER_MIN_AH + PLATEAU_SD_AH / 2, PLATEAU_SD_AH, "plateau")
        elif vc <= LOWER_PLATEAU_V:
            if q <= LOWER_MAX_AH:
                return
            self._measure(LOWER_MAX_AH - PLATEAU_SD_AH / 2, PLATEAU_SD_AH, "plateau")
        else:
            return
        self.landmark_ms_ = now_ms

    def _learn(self, knee_ah, kind):
        """Capacity from a full-to-knee or knee-to-full stretch of pure counting.

        Only stretches with no reset or restore in them count: the anchor is
        dropped whenever the state comes back from flash."""
        a = self.anchor_
        counted = self.counted_mas_ / MAS_PER_AH
        if a is not None:
            observed = None
            if a[0] == "full" and kind == "knee":
                observed = -counted + knee_ah
            elif a[0] == "knee" and kind == "full":
                observed = a[1] + counted
            if observed is not None and CAPACITY_MIN_AH <= observed <= CAPACITY_MAX_AH:
                self.capacity_ah += CAPACITY_LEARN_WEIGHT * (observed - self.capacity_ah)
        if kind == "knee" and a is not None and a[0] == "knee":
            return  # keep the first, lowest-error knee as the anchor
        self.anchor_ = (kind, knee_ah)
        self.counted_mas_ = 0

    # -- flash -----------------------------------------------------------------

    def save(self, now_ms):
        self.saved_ms_ = now_ms
        if self.q_mas_ is None or self.store_ is None:
            return
        if self.gap_from_utc_ is not None:
            # The downtime before this boot isn't settled yet, so this state
            # has no time to give. Keep the older save: it has one, and
            # another reset before the clock arrives should come back to it.
            return
        state = {"v": STORE_VERSION, "q": self.q_mas_, "var": self.var_,
                 "cap": self.capacity_ah, "src": self.source, "t": self.now_utc_() if self.now_utc_ else None}
        tmp = self.store_ + ".tmp"
        try:
            with open(tmp, "w") as f:
                f.write(json.dumps(state))
            os.rename(tmp, self.store_)
        except OSError:
            pass

    def _restore(self):
        if self.store_ is None:
            return
        try:
            with open(self.store_) as f:
                state = json.loads(f.read())
            q = int(state["q"])
            var = float(state["var"])
            cap = float(state["cap"])
        except (OSError, ValueError, KeyError, TypeError):
            return
        if state.get("v") == STORE_VERSION and CAPACITY_MIN_AH <= cap <= CAPACITY_MAX_AH:
            self.capacity_ah = cap
        self.q_mas_ = q
        self.var_ = var + RESTORE_SD_AH * RESTORE_SD_AH
        self.source = "restored"
        t = state.get("t")
        self.gap_from_utc_ = t if isinstance(t, int) else None
        if self.gap_from_utc_ is None:
            # No idea how long the board was down: widen to a day's worth.
            self.var_ += (GAP_SD_A * 24) ** 2

    def _settle_gap(self, now_ms):
        if self.gap_from_utc_ is None or self.now_utc_ is None:
            return
        utc = self.now_utc_()
        if utc is None:
            return
        boot_utc = utc - time.ticks_diff(now_ms, self.boot_ms_)
        gap_ms = boot_utc - self.gap_from_utc_
        self.gap_from_utc_ = None
        if gap_ms < 0 or gap_ms > GAP_MAX_MS:
            gap_ms = GAP_MAX_MS
        hours = gap_ms / 3600000.0
        self.q_mas_ -= int(HIDDEN_DRAW_A * hours * MAS_PER_AH)
        sd = GAP_SD_A * hours
        self.var_ += sd * sd
        self.save(now_ms)
