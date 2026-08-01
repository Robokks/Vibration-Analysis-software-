from nvh_api_schemas.realtime import PlcStateUpdate
from nvh_contract.state import (
    NVH_ID_TO_DIRECTION,
    NvhStateMachine,
    Transition,
    direction_from_nvh_id,
)

import pytest


def _plc(nvh_cmd="IDLE", gear_id=-1, nvh_id=-1, final_log_trigger=False):
    return PlcStateUpdate(
        nvh_cmd=nvh_cmd, gear_id=gear_id, nvh_id=nvh_id,
        final_log_trigger=final_log_trigger,
    )


class DirectionFromNvhIdTests:
    def test_valid_ids_map_correctly(self):
        assert NVH_ID_TO_DIRECTION == {0: "RU", 1: "STYD", 2: "STYC", 3: "RD"}
        assert direction_from_nvh_id(0) == "RU"
        assert direction_from_nvh_id(3) == "RD"

    def test_minus_one_is_none(self):
        assert direction_from_nvh_id(-1) is None

    def test_unknown_id_returns_none(self):
        # Post-Phase-O behavior: unknown nvh_id returns None, not raises.
        # A rogue PLC packet must not crash the producer -- the state
        # machine's `direction` @property is read on every chunk.
        assert direction_from_nvh_id(5) is None
        assert direction_from_nvh_id(99) is None


class NvhStateMachineTests:
    def test_initial_state_is_idle_and_no_log(self):
        sm = NvhStateMachine()
        assert sm.nvh_cmd == "IDLE"
        assert sm.gear_id == -1
        assert sm.nvh_id == -1
        assert sm.trial_no == 0
        assert not sm.log_active
        assert sm.gear_label is None
        assert sm.direction is None

    def test_start_from_idle_emits_only_run_started(self):
        # Phase O Bug 1 fix: the initial IDLE->START tick emits ONLY
        # RUN_STARTED. GEAR_CHANGED / NVH_ID_CHANGED are suppressed on
        # the same apply() call because RUN_STARTED already means
        # "open a fresh writer at the current (gear_id, nvh_id)".
        # Emitting all three caused the producer to open+close+reopen
        # the TDMS file 3x on the first packet.
        sm = NvhStateMachine()
        transitions = sm.apply(_plc(nvh_cmd="START", gear_id=1, nvh_id=0))
        assert transitions == [Transition.RUN_STARTED]
        assert sm.trial_no == 1
        assert sm.log_active
        assert sm.gear_label == "R"
        assert sm.direction == "RU"

    def test_start_ignores_direction_call_with_unknown_nvh_id(self):
        # Phase O Bug 3a: `direction_from_nvh_id` used to raise on
        # unknown ids, which crashed the producer via sm.direction @property.
        # Fix returns None instead.
        sm = NvhStateMachine()
        sm.apply(_plc(nvh_cmd="START", gear_id=1, nvh_id=5))
        assert sm.direction is None
        # gear_label still works because gear_id=1 is valid.
        assert sm.gear_label == "R"

    def test_unknown_gear_id_returns_none_gear_label(self):
        # Phase O Bug 3b (symmetric with 3a): rogue gear_id must not
        # raise via sm.gear_label -- otherwise the fix is only half
        # done and the producer still crashes on garbage gear packets.
        sm = NvhStateMachine()
        sm.apply(_plc(nvh_cmd="START", gear_id=99, nvh_id=0))
        assert sm.gear_label is None
        assert sm.direction == "RU"  # nvh_id=0 is valid

    def test_log_active_requires_known_nvh_id(self):
        # Phase O Bug 3c: log_active used to be True whenever
        # nvh_id != -1, so a rogue value like 5 kept log_active True
        # while sm.direction was None -- causing silent chunk drops
        # with no operator-visible signal. Now log_active tracks
        # direction validity.
        sm = NvhStateMachine()
        sm.apply(_plc(nvh_cmd="START", gear_id=1, nvh_id=5))
        assert sm.log_active is False, "rogue nvh_id must NOT be log_active"
        # Valid nvh_id still logs.
        sm2 = NvhStateMachine()
        sm2.apply(_plc(nvh_cmd="START", gear_id=1, nvh_id=0))
        assert sm2.log_active is True

    def test_no_transitions_on_unchanged_update(self):
        sm = NvhStateMachine()
        sm.apply(_plc(nvh_cmd="START", gear_id=1, nvh_id=0))
        transitions = sm.apply(_plc(nvh_cmd="START", gear_id=1, nvh_id=0))
        assert transitions == []
        assert sm.trial_no == 1

    def test_gear_change_while_running_emits_gear_changed(self):
        sm = NvhStateMachine()
        sm.apply(_plc(nvh_cmd="START", gear_id=1, nvh_id=0))
        transitions = sm.apply(_plc(nvh_cmd="START", gear_id=2, nvh_id=0))
        assert transitions == [Transition.GEAR_CHANGED]
        assert sm.gear_label == "I"

    def test_nvh_id_change_while_running_emits_nvh_id_changed(self):
        sm = NvhStateMachine()
        sm.apply(_plc(nvh_cmd="START", gear_id=1, nvh_id=0))
        transitions = sm.apply(_plc(nvh_cmd="START", gear_id=1, nvh_id=1))
        assert transitions == [Transition.NVH_ID_CHANGED]
        assert sm.direction == "STYD"

    def test_nvh_id_to_minus_one_stops_logging_and_emits_nvh_id_changed(self):
        sm = NvhStateMachine()
        sm.apply(_plc(nvh_cmd="START", gear_id=1, nvh_id=0))
        transitions = sm.apply(_plc(nvh_cmd="START", gear_id=1, nvh_id=-1))
        assert Transition.NVH_ID_CHANGED in transitions
        assert not sm.log_active

    def test_stop_emits_run_stopped(self):
        sm = NvhStateMachine()
        sm.apply(_plc(nvh_cmd="START", gear_id=1, nvh_id=0))
        transitions = sm.apply(_plc(nvh_cmd="STOP", gear_id=1, nvh_id=0))
        assert Transition.RUN_STOPPED in transitions
        assert not sm.log_active

    def test_final_log_trigger_rising_edge_emits_final_log_requested(self):
        sm = NvhStateMachine()
        sm.apply(_plc(nvh_cmd="START", gear_id=1, nvh_id=0))
        transitions = sm.apply(_plc(nvh_cmd="START", gear_id=1, nvh_id=0, final_log_trigger=True))
        assert transitions == [Transition.FINAL_LOG_REQUESTED]

    def test_final_log_trigger_held_high_only_fires_once(self):
        sm = NvhStateMachine()
        sm.apply(_plc(nvh_cmd="START", gear_id=1, nvh_id=0))
        sm.apply(_plc(nvh_cmd="START", gear_id=1, nvh_id=0, final_log_trigger=True))
        transitions = sm.apply(_plc(nvh_cmd="START", gear_id=1, nvh_id=0, final_log_trigger=True))
        assert transitions == []

    def test_final_log_trigger_while_stopped_is_suppressed(self):
        sm = NvhStateMachine()
        transitions = sm.apply(_plc(nvh_cmd="IDLE", gear_id=1, nvh_id=0, final_log_trigger=True))
        assert Transition.FINAL_LOG_REQUESTED not in transitions

    def test_trial_no_increments_per_run_cycle(self):
        sm = NvhStateMachine()
        sm.apply(_plc(nvh_cmd="START", gear_id=1, nvh_id=0))
        sm.apply(_plc(nvh_cmd="STOP", gear_id=1, nvh_id=0))
        sm.apply(_plc(nvh_cmd="START", gear_id=1, nvh_id=0))
        assert sm.trial_no == 2

    def test_transitions_seen_accumulates(self):
        sm = NvhStateMachine()
        sm.apply(_plc(nvh_cmd="START", gear_id=1, nvh_id=0))
        sm.apply(_plc(nvh_cmd="START", gear_id=2, nvh_id=0))
        assert Transition.RUN_STARTED in sm._transitions_seen
        assert Transition.GEAR_CHANGED in sm._transitions_seen
