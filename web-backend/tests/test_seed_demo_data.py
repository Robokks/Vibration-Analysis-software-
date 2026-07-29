"""Tests the demo-data seed script — the first thing in the repo to actually
persist data per docs/data-contract.md (Parquet files + nvh_contract DB rows).
Imported by file path since `scripts/` isn't (yet) an installed package;
the FastAPI app built in a later milestone will supersede this arrangement."""

import sys
from pathlib import Path

import pytest
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from seed_demo_data import seed  # noqa: E402

from nvh_contract.db import make_engine, make_session_factory  # noqa: E402
from nvh_contract.parquet_io import read_dc_parquet  # noqa: E402


@pytest.fixture
def seeded(tmp_path):
    data_root = tmp_path / "data"
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    summary = seed(data_root, db_url, n_trials=15, seed_value=0)
    return data_root, db_url, summary


def test_seed_writes_a_parquet_file_per_run(seeded):
    data_root, _, summary = seeded
    parquet_files = list(data_root.rglob("dc_R_RU.parquet"))
    assert len(parquet_files) == len(summary["runs"])


def test_seed_parquet_files_have_expected_columns(seeded):
    data_root, _, _ = seeded
    parquet_file = next(data_root.rglob("dc_R_RU.parquet"))
    columns = read_dc_parquet(parquet_file)
    assert set(columns.keys()) == {"sample_index", "time_s", "rpm", "tach_pulse", "ch_vib_a"}
    assert len(columns["time_s"]) > 0


def test_seed_writes_manifest_with_contract_version(seeded):
    import json

    data_root, _, _ = seeded
    manifest_file = next(data_root.rglob("manifest.json"))
    manifest = json.loads(manifest_file.read_text())
    assert manifest["model_id"] == "MODEL-A"
    assert manifest["schema_version"] == "1.0"


def test_seed_populates_all_contract_tables(seeded):
    _, db_url, summary = seeded
    engine = make_engine(db_url)
    with engine.connect() as conn:
        counts = {
            table: conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            for table in (
                "models", "test_runs", "dc_records", "master_signatures", "grading_results", "spc_points",
                "master_profiles", "limit_configs",
            )
        }

    # GEAR_R (in seed_demo_data.py) has no fdr_teeth/fd_sel, so the CM_H*
    # harmonic parameters (9 of the 49-entry catalog) are always absent for
    # it -- both master-building and every run's own parameter computation
    # use this same gear, so the present-parameter count is deterministic
    # and identical across both (n_master_params), not the full 49.
    assert counts["models"] == 1
    assert counts["test_runs"] == len(summary["runs"])
    assert counts["dc_records"] == len(summary["runs"])
    assert counts["master_signatures"] == summary["n_master_params"]
    assert counts["grading_results"] == summary["n_master_params"] * len(summary["runs"])
    assert counts["spc_points"] == summary["n_master_params"] * len(summary["runs"])
    # Phase C: one named profile ("REVA") importing the master band into a
    # limit-config row per parameter -- persisted, but not fed into the
    # existing 3 demo scenarios' own grading (they still grade via `masters`).
    assert counts["master_profiles"] == 1
    assert counts["limit_configs"] == summary["n_limit_config_rows"]


def test_seed_limit_config_rows_import_the_master_band(seeded):
    _, db_url, summary = seeded
    engine = make_engine(db_url)
    session_factory = make_session_factory(engine)

    with session_factory() as session:
        from nvh_contract.db import LimitConfigRow, MasterProfileRow, MasterSignatureRow

        profile = session.get(MasterProfileRow, ("MODEL-A", "REVA"))
        assert profile is not None

        rms_master = session.query(MasterSignatureRow).filter_by(stat_name="RMS Avg").one()
        rms_limit = session.get(LimitConfigRow, ("MODEL-A", "REVA", "R", "RU", "vib_a", "RMS Avg"))

        assert rms_limit is not None
        assert rms_limit.limit_low == pytest.approx(rms_master.band_min)
        assert rms_limit.limit_high == pytest.approx(rms_master.band_max)
        assert rms_limit.threshold_low == 0.0
        assert rms_limit.threshold_high == 0.0

        in_h1_limit = session.get(LimitConfigRow, ("MODEL-A", "REVA", "R", "RU", "vib_a", "IN_H1(g)"))
        assert in_h1_limit is not None
        assert in_h1_limit.order_number is not None  # harmonic param carries its resolved order


def test_seed_scenarios_produce_expected_results(seeded):
    _, _, summary = seeded
    results_by_label = {run["label"]: run["result"] for run in summary["runs"]}
    assert results_by_label["healthy-unit"] == "PASS"
    assert results_by_label["crash-noise-unit"] == "FAIL"
    assert results_by_label["slippage-unit"] == "FAIL"


def test_seed_fail_reason_codes_are_specific_to_the_injected_fault(seeded):
    _, db_url, summary = seeded
    dc_id_by_label = {run["label"]: run["dc_id"] for run in summary["runs"]}

    engine = make_engine(db_url)
    session_factory = make_session_factory(engine)
    with session_factory() as session:
        from nvh_contract.db import DcRecordRow

        crash_row = session.get(DcRecordRow, dc_id_by_label["crash-noise-unit"])
        slip_row = session.get(DcRecordRow, dc_id_by_label["slippage-unit"])

    assert "CRASH_NOISE" in crash_row.fail_reason_codes
    assert "SLIPPAGE" in slip_row.fail_reason_codes


def test_seed_is_rerunnable_without_error(tmp_path):
    data_root = tmp_path / "data"
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    seed(data_root, db_url, n_trials=15, seed_value=0)
    # re-running against the same DB/data-root must not raise (model row is
    # upserted via session.merge; new test runs/dc records get fresh UUIDs)
    seed(data_root, db_url, n_trials=15, seed_value=1)
