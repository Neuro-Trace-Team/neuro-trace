from __future__ import annotations
import json
from pathlib import Path
import numpy as np

def json_safe(value):
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [json_safe(v) for v in value]
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def export_recording(output_dir, channel_rows, feature_rows, micro_rows, network_rows, connectivity, report, connectivity_rows=None):
    # Spectral columns (including optional high_gamma) follow resolved config.
    # Preserve NaNs as missing CSV cells, never substitute zero powers or dB.
    output=Path(output_dir); output.mkdir(parents=True, exist_ok=True)
    try:
        import pandas as pd
        from .feature_merge import DEFAULT_EPOCH_KEYS, combine_feature_tables
        from .feature_schema import feature_defaults
        from .config import PipelineConfig
        cfg = PipelineConfig(**report.get('parameters', {}))
        defaults = feature_defaults(cfg)
        def table(rows, columns):
            extras = sorted({key for row in rows for key in row} - set(columns))
            return pd.DataFrame(rows, columns=list(columns)+extras)
        keys = list(DEFAULT_EPOCH_KEYS)
        channel = table(channel_rows, keys + ['event_index', 'channel', 'window_type'])
        features = table([{**defaults, **row} for row in feature_rows], defaults)
        micro = table(micro_rows, keys + ['microstate_class', 'duration_ms', 'coverage', 'occurrence_per_s'])
        network = table(network_rows, keys + ['band', 'graph_valid', 'graph_reason',
            'global_efficiency', 'local_efficiency', 'characteristic_path_length',
            'node_degree', 'node_strength', 'clustering_coefficient', 'betweenness_centrality'])
        for frame, name in [(channel,'channel_features'), (features,'features'), (micro,'microstates'), (network,'network_metrics')]:
            frame.to_csv(output/(name+'.csv'), index=False)
        pd.DataFrame(connectivity_rows or [], columns=["event_id", "event_timestamp", "window_type", "frequency_band", "channel_1", "channel_2", "dwpli", "n_valid_observations", "dwpli_valid"]).to_csv(output/"connectivity_dwpli.csv", index=False)
        combined = combine_feature_tables(features, micro, network)
        combined.to_csv(output/"combined_features.csv", index=False)
    except ImportError as exc: raise ImportError("CSV export requires pandas") from exc
    np.savez_compressed(output/"connectivity.npz", **connectivity)
    (output/"preprocessing_report.json").write_text(json.dumps(json_safe(report), indent=2, default=str, allow_nan=False))

