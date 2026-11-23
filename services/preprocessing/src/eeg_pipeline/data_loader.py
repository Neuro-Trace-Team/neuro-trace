from __future__ import annotations
import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

LOGGER = logging.getLogger(__name__)
SUPPORTED_EXTENSIONS = {".bdf", ".edf"}

@dataclass
class Recording:
    path: Path
    raw: Any
    config: dict = field(default_factory=dict)
    events_seconds: list[float] = field(default_factory=list)
    pain_ratings: Any = None
    warnings: list[str] = field(default_factory=list)
    event_metadata: list[dict] = field(default_factory=list)
    rejected_event_rows: list[dict] = field(default_factory=list)

def _find_eeg_file(directory: Path) -> Optional[Path]:
    files = [p for p in directory.iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS]
    return sorted(files)[0] if files else None

def _read_event_onsets(directory: Path, *, rejected_rows=None) -> list[float]:
    """Read event timestamps from timestamps.json and convert milliseconds to seconds."""
    path = directory / "timestamps.json"
    if not path.is_file():
        raise FileNotFoundError(f"Missing timestamps.json in {directory}")

    def reject_nonstandard_constant(value):
        raise ValueError(f"Invalid JSON timestamp value: {value}")

    try:
        with path.open(encoding="utf-8-sig") as stream:
            payload = json.load(stream, parse_constant=reject_nonstandard_constant)
    except OSError as exc:
        raise OSError(f"Could not read {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc

    timestamps = payload.get("timestamps") if isinstance(payload, dict) else payload
    if not isinstance(timestamps, list):
        raise ValueError(f"{path} must contain a JSON list of timestamps or an object with a 'timestamps' list")

    onsets = []
    for index, value in enumerate(timestamps):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Invalid timestamp at index {index} in {path}: {value!r}")
        timestamp = float(value)
        if not math.isfinite(timestamp) or timestamp < 0:
            raise ValueError(f"Invalid timestamp at index {index} in {path}: {value!r}")
        onsets.append(timestamp / 1000.0)
    return onsets

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
    reader = mne.io.read_raw_edf if eeg_path.suffix.lower() == '.edf' else mne.io.read_raw_bdf
    raw = reader(eeg_path, preload=preload, verbose="ERROR")
    _validate_bdf_metadata(raw, eeg_path)
    rejected_rows = []
    event_metadata = []
    if (directory / 'timestamps.json').is_file():
        events = _read_event_onsets(directory, rejected_rows=rejected_rows)
        event_source = str(directory / 'timestamps.json')
    elif (directory / 'events.csv').is_file():
        from .event_input import read_csv_events
        events, event_metadata, rejected_rows, boundaries, event_source = read_csv_events(directory)
        if boundaries:
            # Append in Raw's annotation time coordinate, retaining existing BADs.
            raw.annotations.append([t + raw.first_time for t in boundaries],
                                   [0.] * len(boundaries), ['EDGE recording_boundary'] * len(boundaries))
    else:
        raise FileNotFoundError(f'Missing timestamps.json or events.csv in {directory}')
    ratings = None
    rating_warnings = []
    ratings_path = directory / "pain_ratings.csv"
    if ratings_path.exists():
        try:
            import pandas as pd
            ratings = pd.read_csv(ratings_path)
        except Exception as exc:
            rating_warnings.append(f'Could not read pain ratings: {exc}')
            LOGGER.warning(rating_warnings[-1])
    source_config = ({'events_json': event_source} if event_source.endswith('timestamps.json')
                     else {'event_source': event_source})
    recording = Recording(eeg_path, raw, source_config, events, ratings)
    recording.event_metadata = event_metadata
    if events and not any(m.get('event_type_known') for m in event_metadata) and not event_source.endswith('timestamps.json'):
        recording.warnings.append('Event types unavailable: supplied timestamps are assumed to be stimulus onsets')
    recording.warnings.extend(rating_warnings)
    recording.rejected_event_rows = rejected_rows
    return recording

def match_pain_rating(record, records, metadata, ratings):
    """Exact join only: event_id, source_csv_row, or onset in seconds.

    Multiple-marker clusters and duplicate event/rating keys are deliberately ambiguous.
    """
    result = dict(pain_rating=float('nan'), pain_rating_status='missing', pain_rating_source_csv_row=None)
    members = [r for r in records if r['cluster_id'] == record['cluster_id']]
    if ratings is None:
        return result
    if len(members) != 1:
        return {**result, 'pain_rating_status':'ambiguous_cluster'}
    import pandas as pd
    frame = ratings.rename(columns=lambda c: str(c).strip().lower())
    if not frame.columns.is_unique or 'rating' not in frame:
        return {**result, 'pain_rating_status':'unsupported_schema'}
    meta = metadata[record['event_index']] if record['event_index'] < len(metadata) else {}
    if 'event_id' in frame and meta.get('event_id'):
        key, value = 'event_id', str(meta['event_id'])
        candidates = frame[key].astype(str) == value
        unique = sum(str(m.get(key)) == value for m in metadata) == 1
    elif 'source_csv_row' in frame:
        key, value = 'source_csv_row', meta.get('source_csv_row')
        candidates = pd.to_numeric(frame[key], errors='coerce') == value
        unique = value is not None
    elif 'onset' in frame:
        value = record.get('source_event', record['event'])
        candidates = pd.to_numeric(frame['onset'], errors='coerce') == value
        unique = sum(r.get('source_event', r['event']) == value for r in records) == 1
    else:
        return {**result, 'pain_rating_status':'unsupported_schema'}
    indices = [i for i, match in enumerate(candidates) if match]
    if not unique or len(indices) > 1:
        return {**result, 'pain_rating_status':'ambiguous_match'}
    if not indices:
        return result
    i = indices[0]
    try:
        rating = float(frame.iloc[i]['rating'])
    except (TypeError, ValueError):
        rating = float('nan')
    if not math.isfinite(rating):
        return {**result, 'pain_rating_status':'invalid_rating', 'pain_rating_source_csv_row':i+2}
    return dict(pain_rating=rating, pain_rating_status='matched', pain_rating_source_csv_row=i+2)


def iter_recording_dirs(input_root: str | Path, experiment: Optional[str] = None, subject: Optional[str] = None):
    root = Path(input_root)
    for exp in sorted(p for p in root.iterdir() if p.is_dir()):
        if experiment and exp.name not in {experiment, f"experiment_{experiment}", f"experiment_{int(experiment):02d}" if experiment.isdigit() else experiment}: continue
        for sub in sorted(p for p in exp.iterdir() if p.is_dir()):
            if subject and sub.name != subject: continue
            for run in sorted(p for p in sub.iterdir() if p.is_dir()):
                if _find_eeg_file(run): yield exp.name, sub.name, run.name, run

