import numpy as np
import pytest

from eeg_pipeline.data_loader import iter_recording_dirs, load_recording


def write_recording(path, file_format):
    """Write a minimal real EDF/BDF with known samples and calibration."""
    def field(value, width):
        return str(value).encode("ascii").ljust(width)

    is_bdf = file_format == "bdf"
    minimum, maximum = (-8388608, 8388607) if is_bdf else (-32768, 32767)
    header = b"\xffBIOSEMI" if is_bdf else b"0       "
    for value, width in [
        ("patient", 80), ("recording", 80), ("01.01.24", 8),
        ("00.00.00", 8), (512, 8), ("", 44), (1, 8), (1, 8), (1, 4),
        ("Fp1", 16), ("", 80), ("uV", 8), (minimum, 8), (maximum, 8),
        (minimum, 8), (maximum, 8), ("", 80), (8, 8), ("", 32),
    ]:
        header += field(value, width)
    samples = [-100, -20, 0, 20, 100, 40, -40, 10]
    width = 3 if is_bdf else 2
    path.write_bytes(header + b"".join(value.to_bytes(width, "little", signed=True) for value in samples))
    return np.array(samples) * 1e-6


@pytest.mark.parametrize("preload", [False, True])
@pytest.mark.parametrize("file_format,filename", [
    ("bdf", "eeg_data.bdf"),
    ("edf", "eeg_data.edf"),
    ("edf", "eeg_data.EDF"),
    ("edf", "eeg_data.bdf"),
])
def test_load_real_recording(tmp_path, file_format, filename, preload):
    pytest.importorskip("mne")
    run = tmp_path / "experiment_01" / "subject" / "run"
    run.mkdir(parents=True)
    source = run / filename
    expected = write_recording(source, file_format)
    original = source.read_bytes()
    (run / "events.json").write_text("[500]")

    assert list(iter_recording_dirs(tmp_path)) == [("experiment_01", "subject", "run", run)]
    recording = load_recording(run, preload=preload)

    # Read after the loader returns, including after temporary EDF cleanup.
    np.testing.assert_allclose(recording.raw.get_data()[0], expected, atol=1e-12)
    assert recording.raw.ch_names == ["Fp1"]
    assert recording.raw.info["sfreq"] == 8
    assert recording.events_seconds == [0.5]
    assert recording.path == source
    assert source.read_bytes() == original
    assert sorted(p.name for p in run.iterdir()) == sorted([filename, "events.json"])
