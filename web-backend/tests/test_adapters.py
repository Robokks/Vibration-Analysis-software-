import pytest
from fastapi import HTTPException
from nvh_contract.db import ModelRow, make_engine, make_session_factory

from nvh_web_backend.adapters import gear_orders_for, gear_teeth_for, model_row_to_model


@pytest.fixture
def model(seeded_db):
    db_url, summary = seeded_db
    engine = make_engine(db_url)
    session_factory = make_session_factory(engine)
    with session_factory() as session:
        row = session.get(ModelRow, summary["model_id"])
        return model_row_to_model(row)


def test_model_row_to_model_roundtrips_gear_teeth(model):
    assert model.model_id == "MODEL-A"
    assert model.drive_teeth["R"] == 12
    assert model.layshaft_teeth["R"] == 32
    assert model.ratios["R"] == pytest.approx(3.753)


def test_gear_teeth_for_configured_gear(model):
    teeth = gear_teeth_for(model, "R")
    assert teeth.drive_shaft == 12
    assert teeth.layshaft == 32


def test_gear_teeth_for_unconfigured_gear_raises_404(model):
    with pytest.raises(HTTPException) as excinfo:
        gear_teeth_for(model, "V")
    assert excinfo.value.status_code == 404


def test_gear_orders_for_configured_gear(model):
    gear_orders = gear_orders_for(model, "R")
    assert gear_orders.gear_label == "R"
    assert gear_orders.mesh_order > 0


def test_gear_orders_for_unconfigured_gear_raises_404(model):
    with pytest.raises(HTTPException) as excinfo:
        gear_orders_for(model, "V")
    assert excinfo.value.status_code == 404
