import json

from nvh_contract.db import ModelRow, TestRunRow, init_db, make_engine, make_session_factory


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
