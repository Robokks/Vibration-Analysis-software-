import numpy as np

from nvh_contract.parquet_io import channel_names_in, read_dc_parquet, write_dc_parquet


def test_write_then_read_round_trips_all_columns(tmp_path):
    n = 100
    time_s = np.arange(n) / 5000.0
    rpm = np.linspace(1000, 2500, n)
    tach_pulse = (np.arange(n) % 2).astype(np.int8)
    channels = {
        "vib_a": np.sin(time_s * 100),
        "mic": np.cos(time_s * 50),
    }

    path = tmp_path / "dc_R_RU.parquet"
    write_dc_parquet(path, time_s, rpm, tach_pulse, channels)

    assert path.exists()
    result = read_dc_parquet(path)

    np.testing.assert_array_equal(result["sample_index"], np.arange(n))
    np.testing.assert_allclose(result["time_s"], time_s)
    np.testing.assert_allclose(result["rpm"], rpm)
    np.testing.assert_array_equal(result["tach_pulse"], tach_pulse)
    np.testing.assert_allclose(result["ch_vib_a"], channels["vib_a"])
    np.testing.assert_allclose(result["ch_mic"], channels["mic"])


def test_channel_names_in_extracts_calibrated_channels():
    columns = {"sample_index": None, "time_s": None, "rpm": None, "tach_pulse": None, "ch_vib_a": None, "ch_mic": None}
    assert sorted(channel_names_in(columns)) == ["mic", "vib_a"]


def test_write_creates_parent_directories(tmp_path):
    n = 10
    time_s = np.arange(n) / 1000.0
    rpm = np.full(n, 1500.0)
    tach_pulse = np.zeros(n, dtype=np.int8)

    nested_path = tmp_path / "nested" / "dirs" / "dc_R_RU.parquet"
    write_dc_parquet(nested_path, time_s, rpm, tach_pulse, {"vib_a": np.zeros(n)})

    assert nested_path.exists()
