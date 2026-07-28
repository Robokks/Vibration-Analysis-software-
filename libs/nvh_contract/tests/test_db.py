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
                idler_teeth_json="{}",
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
