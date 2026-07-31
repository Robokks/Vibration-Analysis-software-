"""NVH runtime state machine driven by PLC-published PlcStateUpdate events.

The PLC owns the truth about (nvh_cmd, gear_id, nvh_id, final_log_trigger).
Everything on the acquisition/analysis side -- when to buffer, when to
open a new TDMS file, when to grade + persist a summary row -- reacts to
transitions of that tuple. Rather than duplicate that transition logic
across the producer, the launcher, and the Qt live display, it lives
once here and returns a list of `Transition` events that consumers
dispatch on.

State model (from the user's requirement):

- gear_id: 0-6 (0=N, 1=R, 2=I, 3=II, 4=III, 5=IV, 6=V). Cross-referenced
  by gear_label via `nvh_contract.gear_ids.gear_label_from_id`.
- nvh_id: -1 (no log, transport sentinel), 0=RU, 1=STYD, 2=STYC, 3=RD.
- nvh_cmd: START | STOP | IDLE (the run-level gate; -1 sentinels roll up
  through this).
- log_active: derived -- True iff nvh_cmd == START AND nvh_id != -1
  (matches the "initially gear_id=-1, nvh_id=-1 => no log" rule).

Transitions emitted from `.apply(update)`:

- RUN_STARTED       -- nvh_cmd flipped IDLE/STOP -> START
- RUN_STOPPED       -- nvh_cmd flipped START -> STOP/IDLE
- GEAR_CHANGED      -- gear_id changed while log_active
- NVH_ID_CHANGED    -- nvh_id changed while log_active (incl. -1 <-> valid)
- FINAL_LOG_REQUESTED -- final_log_trigger rising edge

The transition list is ordered so consumers can act in the right
sequence: RUN_STARTED before GEAR/NVH_ID changes (fresh run), and
RUN_STOPPED after them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum

from nvh_api_schemas.realtime import PlcStateUpdate

from nvh_contract.gear_ids import gear_label_from_id

_LOGGER = logging.getLogger(__name__)


class Transition(Enum):
    RUN_STARTED = "RUN_STARTED"
    RUN_STOPPED = "RUN_STOPPED"
    GEAR_CHANGED = "GEAR_CHANGED"
    NVH_ID_CHANGED = "NVH_ID_CHANGED"
    FINAL_LOG_REQUESTED = "FINAL_LOG_REQUESTED"


# nvh_id -> Direction label, matching qt-app/screens/live_display.py:88
# (the two must stay in lockstep; if the enum grows, add here first).
NVH_ID_TO_DIRECTION: dict[int, str] = {
    0: "RU",
    1: "STYD",
    2: "STYC",
    3: "RD",
}


def direction_from_nvh_id(nvh_id: int) -> str | None:
    """None for the -1 sentinel AND for any unknown nvh_id.

    Rationale (Phase O Bug 3): the state machine's `direction`
    @property is read on every signal chunk. Raising here on a rogue
    PLC packet (bit flip, wrong DB layout) crashed the producer with
    an uncaught ValueError. A production PLC producer must not die on
    transient bad data -- return None so callers can gate on
    `if sm.direction is None`.

    Rate limiting of the unknown-id warning is the consumer's job via
    stdlib `logging` filters -- keeping a module-global "already
    warned" set here breaks test isolation."""
    if nvh_id == -1:
        return None
    direction = NVH_ID_TO_DIRECTION.get(nvh_id)
    if direction is None:
        _LOGGER.warning("unknown nvh_id %r -- treating as no-log", nvh_id)
    return direction


@dataclass
class NvhStateMachine:
    """Holds the last-seen PLC state + a monotonic trial counter."""

    nvh_cmd: str = "IDLE"
    gear_id: int = -1
    nvh_id: int = -1
    final_log_trigger: bool = False
    trial_no: int = 0
    _transitions_seen: list[Transition] = field(default_factory=list, repr=False)

    @property
    def log_active(self) -> bool:
        """Log iff the operator has pressed START AND the PLC is
        currently reporting a valid (known) nvh_id.

        Bug 3c: previously this only checked `nvh_id != -1`, so a
        rogue value like 5 kept log_active True but sm.direction
        would be None -- causing silent chunk drops with no
        operator-visible signal. Now log_active is False when the
        direction can't be resolved, ensuring the emission guard
        and the "run active" UI stay consistent."""
        return self.nvh_cmd == "START" and direction_from_nvh_id(self.nvh_id) is not None

    @property
    def gear_label(self) -> str | None:
        """Human-facing gear label; None for the idle sentinel or
        any unknown gear_id (see `gear_label_from_id`)."""
        return gear_label_from_id(self.gear_id)

    @property
    def direction(self) -> str | None:
        return direction_from_nvh_id(self.nvh_id)

    def apply(self, update: PlcStateUpdate) -> list[Transition]:
        """Update the tuple, return the ordered list of transitions this
        update triggered. Safe to call repeatedly with an unchanged
        update -- no transitions are emitted for a no-op."""
        transitions: list[Transition] = []

        was_active = self.log_active
        prev_gear = self.gear_id
        prev_nvh = self.nvh_id
        prev_final = self.final_log_trigger

        run_start = self.nvh_cmd != "START" and update.nvh_cmd == "START"
        run_stop = self.nvh_cmd == "START" and update.nvh_cmd != "START"

        self.nvh_cmd = update.nvh_cmd
        self.gear_id = update.gear_id
        self.nvh_id = update.nvh_id
        self.final_log_trigger = update.final_log_trigger

        if run_start:
            self.trial_no += 1
            transitions.append(Transition.RUN_STARTED)

        # GEAR / NVH_ID changes only matter mid-run. On the RUN_STARTED
        # tick, the gear/nvh values are baked into RUN_STARTED's
        # semantics ("open a fresh writer at the current (gear_id,
        # nvh_id)") -- also emitting GEAR_CHANGED / NVH_ID_CHANGED on
        # the same tick caused the producer's rollover-writer handler
        # to fire three times, opening + closing + reopening the same
        # TDMS file (Phase O Bug 1).
        if (self.log_active or was_active) and not run_start:
            if update.gear_id != prev_gear:
                transitions.append(Transition.GEAR_CHANGED)
            if update.nvh_id != prev_nvh:
                transitions.append(Transition.NVH_ID_CHANGED)

        # Rising-edge on final_log_trigger, gated by log_active so a
        # spurious trigger while STOPped can't corrupt the summary DB.
        if update.final_log_trigger and not prev_final and (self.log_active or was_active):
            transitions.append(Transition.FINAL_LOG_REQUESTED)

        if run_stop:
            transitions.append(Transition.RUN_STOPPED)

        self._transitions_seen.extend(transitions)
        return transitions
