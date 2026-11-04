from __future__ import annotations
import csv
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

LOGGER = logging.getLogger(__name__)
SUPPORTED_EXTENSIONS = {".bdf"}

@dataclass
class Recording:
    path: Path
    raw: Any
    config: dict = field(default_factory=dict)
    events_seconds: list[float] = field(default_factory=list)
    pain_ratings: Any = None
    warnings: list[str] = field(default_factory=list)

def _find_eeg_file(directory: Path) -> Optional[Path]:
    files = [p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]
    return sorted(files)[0] if files else None

def _read_event_onsets(directory: Path) -> list[float]:
    """Read event onset times, in seconds, from the recording's events.csv."""
    path = directory / "events.csv"
    if not path.is_file():
        raise FileNotFoundError(f"Missing events.csv in {directory}")
    try:
        with path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames or "onset" not in {name.strip().lower() for name in reader.fieldnames}:
                raise ValueError(f"events.csv must contain an 'onset' column: {path}")
            onset_name = next(name for name in reader.fieldnames if name.strip().lower() == "onset")
            onsets = []
            for row_number, row in enumerate(reader, start=2):
                value = row.get(onset_name, "")
                if value is None or not value.strip():
                    continue
                try:
                    onset = float(value)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"Invalid onset at row {row_number} in {path}: {value!r}") from exc
                if not math.isfinite(onset) or onset < 0:
                    raise ValueError(f"Invalid onset at row {row_number} in {path}: {value!r}")
                onsets.append(onset)
            return onsets
    except OSError as exc:
        raise OSError(f"Could not read {path}: {exc}") from exc

def _validate_bdf_metadata(raw, eeg_path: Path) -> None:
    """Ensure all metadata needed by preprocessing comes from the BDF/MNE object."""
    try:
        sfreq = float(raw.info.get("sfreq"))
    except (TypeError, ValueError):
        sfreq = math.nan
    if not math.isfinite(sfreq) or sfreq <= 0:
        raise ValueError(f"BDF header does not contain a valid sampling frequency: {eeg_path}")

    names = list(getattr(raw, "ch_names", []) or [])
    if not names or any(not isinstance(name, str) or not name.strip() for name in names):
        raise ValueError(f"BDF header does not contain channel names: {eeg_path}")
    if len(set(names)) != len(names):
        raise ValueError(f"BDF header contains duplicate channel names: {eeg_path}")

    try:
        channel_types = list(raw.get_channel_types())
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(f"BDF header does not contain channel types: {eeg_path}") from exc
    if len(channel_types) != len(names) or any(not isinstance(kind, str) or not kind.strip() for kind in channel_types):
        raise ValueError(f"BDF header contains incomplete channel types: {eeg_path}")

def load_recording(directory: str | Path, preload: bool = False) -> Recording:
    directory = Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(directory)
    eeg_path = _find_eeg_file(directory)
    if eeg_path is None:
        raise FileNotFoundError(f"No supported EEG file in {directory}")
    try:
        import mne
    except ImportError as exc:
        raise ImportError("Reading EEG files requires mne (pip install -r requirements.txt)") from exc
    raw = mne.io.read_raw_bdf(eeg_path, preload=preload, verbose="ERROR")
    _validate_bdf_metadata(raw, eeg_path)
    events = _read_event_onsets(directory)
    ratings = None
    ratings_path = directory / "pain_ratings.csv"
    if ratings_path.exists():
        try:
            import pandas as pd
            ratings = pd.read_csv(ratings_path)
        except Exception as exc: LOGGER.warning("Could not read pain ratings: %s", exc)
    recording = Recording(eeg_path, raw, {"events_csv": str(directory / "events.csv")}, events, ratings)
    return recording

def iter_recording_dirs(input_root: str | Path, experiment: Optional[str] = None, subject: Optional[str] = None):
    root = Path(input_root)
    for exp in sorted(p for p in root.iterdir() if p.is_dir()):
        if experiment and exp.name not in {experiment, f"experiment_{experiment}", f"experiment_{int(experiment):02d}" if experiment.isdigit() else experiment}: continue
        for sub in sorted(p for p in exp.iterdir() if p.is_dir()):
            if subject and sub.name != subject: continue
            for run in sorted(p for p in sub.iterdir() if p.is_dir()):
                if _find_eeg_file(run): yield exp.name, sub.name, run.name, run

