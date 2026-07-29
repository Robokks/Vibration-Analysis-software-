"""FastAPI backend serving the NVH demo SQLite DB (populated by
scripts/seed_demo_data.py) so the web-frontend/qt-app Report GUI clients
can show real data. Reports are always reconstructed on the fly from the
raw Parquet signal + DB config rows via analysis_engine.pipeline.
analyze_dc_record(), never read back from persisted grading_results/
spc_points rows -- the same "compose from live analysis output" convention
every analysis_engine.reports.* builder already follows."""
