import json

import pytest
from sqlalchemy.exc import IntegrityError

from nvh_contract.db import (
    LimitConfigRow,
    MasterProfileRow,
    ModelRow,
    TableConfigParameterRow,
    TableConfigStepRow,
    TestRunRow,
    init_db,
    make_engine,
    make_session_factory,
)


def test_init_db_and_roundtrip_row(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    init_db(engine)
    Session = make_session_factory(engine)

    with Session() as session:
        session.add(
            ModelRow(
                model_id="MODEL-A",
                model_name="Nano 4 Speed",
                drive_teeth_json="{}",
                idler_teeth_1_json="{}",
                layshaft_teeth_json="{}",
                ratios_json="{}",
            )
        )
        session.add(
            TestRunRow(
                test_run_id="run-1",
                model_id="MODEL-A",
                serial_number="4112DK01781",
                started_at="2026-07-28T00:00:00",
                overall_result="PENDING",
            )
        )
        session.commit()

    with Session() as session:
        run = session.get(TestRunRow, "run-1")
        assert run is not None
        assert run.model_id == "MODEL-A"
        assert run.overall_result == "PENDING"


def test_model_row_new_columns_default_to_empty_json_object(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    init_db(engine)
    Session = make_session_factory(engine)

    with Session() as session:
        session.add(
            ModelRow(
                model_id="MODEL-B",
                model_name="Model B",
                drive_teeth_json="{}",
                idler_teeth_1_json="{}",
                layshaft_teeth_json="{}",
                ratios_json="{}",
            )
        )
        session.commit()

    with Session() as session:
        model = session.get(ModelRow, "MODEL-B")
        assert model.idler_teeth_2_json == "{}"
        assert model.drive_shaft_bearing_roll_json == "{}"
        assert model.layshaft_bearing_roll_json == "{}"
        assert model.fdr_teeth_json == "{}"
        assert model.fd_sel_json == "{}"


def test_model_row_new_columns_roundtrip_when_supplied(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    init_db(engine)
    Session = make_session_factory(engine)

    with Session() as session:
        session.add(
            ModelRow(
                model_id="MODEL-C",
                model_name="Model C",
                drive_teeth_json=json.dumps({"R": 12}),
                idler_teeth_1_json=json.dumps({"R": 36}),
                idler_teeth_2_json=json.dumps({"R": 18}),
                layshaft_teeth_json=json.dumps({"R": 32}),
                drive_shaft_bearing_roll_json=json.dumps({"R": 5.43}),
                layshaft_bearing_roll_json=json.dumps({"R": 7.91}),
                fdr_teeth_json=json.dumps({"FDR1": 27, "FDR2": 30}),
                fd_sel_json=json.dumps({"R": "FDR1"}),
                ratios_json=json.dumps({"R": 3.753}),
            )
        )
        session.commit()

    with Session() as session:
        model = session.get(ModelRow, "MODEL-C")
        assert json.loads(model.idler_teeth_2_json)["R"] == 18
        assert json.loads(model.drive_shaft_bearing_roll_json)["R"] == 5.43
        assert json.loads(model.fdr_teeth_json)["FDR1"] == 27
        assert json.loads(model.fd_sel_json)["R"] == "FDR1"


def _seed_model(session, model_id: str) -> None:
    session.add(
        ModelRow(
            model_id=model_id, model_name="Nano 4 Speed", drive_teeth_json="{}",
            idler_teeth_1_json="{}", layshaft_teeth_json="{}", ratios_json="{}",
        )
    )
    session.commit()


def test_master_profile_row_roundtrip(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    init_db(engine)
    Session = make_session_factory(engine)

    with Session() as session:
        _seed_model(session, "MODEL-A")
        session.add(MasterProfileRow(model_id="MODEL-A", program_name="REVA", created_at="2026-07-29T00:00:00"))
        session.commit()

    with Session() as session:
        profile = session.get(MasterProfileRow, ("MODEL-A", "REVA"))
        assert profile is not None
        assert profile.created_at == "2026-07-29T00:00:00"


def test_limit_config_row_roundtrip(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    init_db(engine)
    Session = make_session_factory(engine)

    with Session() as session:
        _seed_model(session, "MODEL-A")
        session.add(
            LimitConfigRow(
                model_id="MODEL-A", program_name="REVA", gear_label="R", direction="RU",
                channel_name="vib_a", stat_name="RMS Avg", order_number=None,
                limit_low=0.9, limit_high=1.1, threshold_low=0.05, threshold_high=0.1,
                updated_at="2026-07-29T00:00:00",
            )
        )
        session.commit()

    with Session() as session:
        row = session.get(LimitConfigRow, ("MODEL-A", "REVA", "R", "RU", "vib_a", "RMS Avg"))
        assert row is not None
        assert row.limit_low == 0.9
        assert row.threshold_high == 0.1


def test_limit_config_row_duplicate_key_conflicts(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    init_db(engine)
    Session = make_session_factory(engine)

    with Session() as session:
        _seed_model(session, "MODEL-A")
        session.commit()

    def _row():
        return LimitConfigRow(
            model_id="MODEL-A", program_name="REVA", gear_label="R", direction="RU",
            channel_name="vib_a", stat_name="RMS Avg", limit_low=0.9, limit_high=1.1,
            updated_at="2026-07-29T00:00:00",
        )

    with Session() as session:
        session.add(_row())
        session.commit()

    with Session() as session:
        session.add(_row())
        with pytest.raises(IntegrityError):
            session.commit()


def test_table_config_step_row_roundtrip(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    init_db(engine)
    Session = make_session_factory(engine)

    with Session() as session:
        _seed_model(session, "MODEL-A")
        session.add(
            TableConfigStepRow(
                model_id="MODEL-A", program_name="REVA", gear_label="R", direction="RU",
                channel_name="vib_a", step_order=1, updated_at="2026-07-29T00:00:00",
            )
        )
        session.commit()

    with Session() as session:
        row = session.get(TableConfigStepRow, ("MODEL-A", "REVA", "R", "RU", "vib_a"))
        assert row is not None
        assert row.step_order == 1


def test_table_config_step_row_merge_upserts_in_place(tmp_path):
    # This is the exact idempotency property seed_demo_data.py depends on
    # (see the historical LimitConfigRow add()-vs-merge() bug in PROGRESS.md).
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    init_db(engine)
    Session = make_session_factory(engine)

    with Session() as session:
        _seed_model(session, "MODEL-A")
        session.merge(
            TableConfigStepRow(
                model_id="MODEL-A", program_name="REVA", gear_label="R", direction="RU",
                channel_name="vib_a", step_order=1, updated_at="2026-07-29T00:00:00",
            )
        )
        session.commit()

    with Session() as session:
        session.merge(
            TableConfigStepRow(
                model_id="MODEL-A", program_name="REVA", gear_label="R", direction="RU",
                channel_name="vib_a", step_order=2, updated_at="2026-07-29T01:00:00",
            )
        )
        session.commit()

    with Session() as session:
        row = session.get(TableConfigStepRow, ("MODEL-A", "REVA", "R", "RU", "vib_a"))
        assert row.step_order == 2
        assert row.updated_at == "2026-07-29T01:00:00"


def test_table_config_parameter_row_roundtrip(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path}/test.db")
    init_db(engine)
    Session = make_session_factory(engine)

    with Session() as session:
        _seed_model(session, "MODEL-A")
        session.add(
            TableConfigParameterRow(
                model_id="MODEL-A", program_name="REVA", channel_name="vib_a",
                stat_name="RMS Avg", updated_at="2026-07-29T00:00:00",
            )
        )
        session.commit()

    with Session() as session:
        row = session.get(TableConfigParameterRow, ("MODEL-A", "REVA", "vib_a", "RMS Avg"))
        assert row is not None
