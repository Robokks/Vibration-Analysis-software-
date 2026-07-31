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

    def test_unknown_id_raises(self):
        with pytest.raises(ValueError):
            direction_from_nvh_id(9)


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

    def test_start_from_idle_emits_run_started_and_bumps_trial(self):
        sm = NvhStateMachine()
        transitions = sm.apply(_plc(nvh_cmd="START", gear_id=1, nvh_id=0))
        assert Transition.RUN_STARTED in transitions
        assert Transition.GEAR_CHANGED in transitions
        assert Transition.NVH_ID_CHANGED in transitions
        assert sm.trial_no == 1
        assert sm.log_active
        assert sm.gear_label == "R"
        assert sm.direction == "RU"

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
