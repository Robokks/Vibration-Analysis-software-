"""SQLAlchemy ORM models mirroring docs/data-contract.md, plus engine/session
helpers. SQLite for local dev/tests, Postgres in production (same models, swap
the engine URL)."""

from __future__ import annotations

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    ForeignKey,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


class ModelRow(Base):
    __tablename__ = "models"

    model_id = Column(String, primary_key=True)
    model_name = Column(String, nullable=False)
    drive_teeth_json = Column(String, nullable=False)
    idler_teeth_1_json = Column(String, nullable=False)
    idler_teeth_2_json = Column(String, nullable=False, default="{}")
    layshaft_teeth_json = Column(String, nullable=False)
    drive_shaft_bearing_roll_json = Column(String, nullable=False, default="{}")
    layshaft_bearing_roll_json = Column(String, nullable=False, default="{}")
    fdr_teeth_json = Column(String, nullable=False, default="{}")
    fd_sel_json = Column(String, nullable=False, default="{}")
    ratios_json = Column(String, nullable=False)


class TestRunRow(Base):
    __tablename__ = "test_runs"

    test_run_id = Column(String, primary_key=True)
    model_id = Column(String, ForeignKey("models.model_id"), nullable=False)
    serial_number = Column(String, nullable=False)
    operator_id = Column(String)
    shift_number = Column(String)
    repeat_number = Column(Integer, nullable=False, default=1)
    line_id = Column(String)
    station_id = Column(String)
    started_at = Column(String, nullable=False)
    finished_at = Column(String)
    overall_result = Column(String, nullable=False, default="PENDING")


class DcRecordRow(Base):
    __tablename__ = "dc_records"

    dc_id = Column(String, primary_key=True)
    test_run_id = Column(String, ForeignKey("test_runs.test_run_id"), nullable=False)
    gear_label = Column(String, nullable=False)
    direction = Column(String, nullable=False)
    rpm_start = Column(Float, nullable=False)
    rpm_end = Column(Float, nullable=False)
    sample_rate_hz = Column(Float, nullable=False)
    parquet_path = Column(String, nullable=False)
    result = Column(String, nullable=False, default="PENDING")
    fail_reason_codes = Column(String, default="")


class ChannelRow(Base):
    __tablename__ = "channels"

    channel_id = Column(String, primary_key=True)
    dc_id = Column(String, ForeignKey("dc_records.dc_id"), nullable=False)
    channel_name = Column(String, nullable=False)
    sensor_type = Column(String)
    units = Column(String, nullable=False)
    sensitivity_mv_per_eu = Column(Float)
    pregain_db = Column(Float, default=0.0)
    weighting_filter = Column(String, default="linear")


class MasterSignatureRow(Base):
    __tablename__ = "master_signatures"

    master_id = Column(String, primary_key=True)
    model_id = Column(String, ForeignKey("models.model_id"), nullable=False)
    gear_label = Column(String, nullable=False)
    direction = Column(String, nullable=False)
    stat_name = Column(String, nullable=False)
    domain = Column(String, nullable=False)
    mean_value = Column(Float, nullable=False)
    band_min = Column(Float, nullable=False)
    band_max = Column(Float, nullable=False)
    full_scale = Column(Float, nullable=False)
    trial_count = Column(Integer, nullable=False)
    created_at = Column(String, nullable=False)


class GradingResultRow(Base):
    __tablename__ = "grading_results"

    dc_id = Column(String, ForeignKey("dc_records.dc_id"), primary_key=True)
    stat_name = Column(String, primary_key=True)
    domain = Column(String, primary_key=True)
    g_level = Column(Integer, nullable=False)
    ok_flag = Column(Boolean, nullable=False)


class SpcPointRow(Base):
    __tablename__ = "spc_points"

    id = Column(Integer, primary_key=True, autoincrement=True)
    serial_number = Column(String, nullable=False)
    model_id = Column(String, nullable=False)
    gear_label = Column(String, nullable=False)
    direction = Column(String, nullable=False)
    stat_name = Column(String, nullable=False)
    value = Column(Float, nullable=False)
    recorded_at = Column(String, nullable=False)


def make_engine(db_url: str):
    return create_engine(db_url)


def init_db(engine) -> None:
    Base.metadata.create_all(engine)


def make_session_factory(engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine)
