"""Read legacy CSV events without discarding available BIDS marker semantics."""
from pathlib import Path
import re

import numpy as np
import pandas as pd


def read_csv_events(directory):
    directory = Path(directory)
    source = directory / 'events.csv'
    frame = pd.read_csv(source)
    if 'onset' not in frame:
        raise ValueError('events.csv must contain onset in seconds')
    onsets = pd.to_numeric(frame.onset, errors='coerce').to_numpy(float)
    if not np.isfinite(onsets).all() or np.any(onsets < 0):
        raise ValueError('events.csv contains invalid onsets')
    # Converted datasets retain the original BIDS beside experiment directories.
    # Only enrich an exact, unambiguous match; never infer event times from EEG.
    if not {'value', 'trial_type'} & set(frame.columns) and len(directory.parents) >= 3:
        bids = directory.parents[2] / '_original_bids'
        run = directory.name.removesuffix('_run-01')
        task = re.search(r'(task-[^_]+)', run)
        session = re.search(r'(ses-[^_]+)', run)
        if bids.is_dir() and task:
            sub = directory.parent.name
            suffix = f'{sub}/{session[1]}/eeg' if session else f'{sub}/eeg'
            matches = list(bids.glob(f'*/{suffix}/*_{task[1]}_events.tsv'))
            if len(matches) != 1:
                raise ValueError('Cannot unambiguously match events.csv to original BIDS')
            original = pd.read_csv(matches[0], sep='\t')
            if len(original) != len(frame) or not np.allclose(
                    onsets, original.onset.to_numpy(float), rtol=0, atol=1e-7):
                raise ValueError('events.csv onsets differ from original BIDS; refusing unsafe event join')
            frame, source = original, matches[0]
    type_column = 'value' if 'value' in frame else 'trial_type' if 'trial_type' in frame else None
    events, metadata, rejected, boundaries = [], [], [], []
    for index, (_, row) in enumerate(frame.iterrows()):
        onset = float(row.onset)
        if type_column and (pd.isna(row[type_column]) or not str(row[type_column]).strip()):
            raise ValueError(f'Missing event type at source row {index+2}')
        marker = str(row[type_column]).strip() if type_column else None
        normalized = re.sub(r'\s+', '', marker or '').lower()
        boundary = normalized == 'boundary' or normalized.startswith(('newsegment', 'edge'))
        technical = boundary or 'impedance' in normalized
        # The task's BIDS descriptor explicitly identifies condition54 as laser.
        if 'task-26ByBiosemi' in directory.name and marker is not None:
            technical |= normalized != 'condition54'
        if technical:
            rejected.append(dict(source_csv_row=index+2, onset=onset,
                                 marker=marker, reason='recording_boundary' if boundary else 'non_stimulus_marker'))
            if boundary:
                boundaries.append(onset)
            continue
        events.append(onset)
        meta = {k: v for k, v in row.items() if pd.notna(v)}
        meta.update(source_csv_row=index+2, source_event_index=index, marker=marker,
                    event_type_known=marker is not None)
        metadata.append(meta)
    return events, metadata, rejected, boundaries, str(source)
