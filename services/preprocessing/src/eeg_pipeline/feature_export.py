from __future__ import annotations
import json
from pathlib import Path
import numpy as np

def export_recording(output_dir, channel_rows, feature_rows, micro_rows, network_rows, connectivity, report, connectivity_rows=None):
    output=Path(output_dir); output.mkdir(parents=True, exist_ok=True)
    try:
        import pandas as pd
        pd.DataFrame(channel_rows).to_csv(output/"channel_features.csv", index=False)
        pd.DataFrame(feature_rows).to_csv(output/"features.csv", index=False)
        pd.DataFrame(micro_rows).to_csv(output/"microstates.csv", index=False)
        pd.DataFrame(network_rows).to_csv(output/"network_metrics.csv", index=False)
        pd.DataFrame(connectivity_rows or [], columns=["event_id", "event_timestamp", "window_type", "frequency_band", "channel_1", "channel_2", "dwpli", "n_valid_observations", "dwpli_valid"]).to_csv(output/"connectivity_dwpli.csv", index=False)
        from .feature_merge import combine_feature_tables
        combined = combine_feature_tables(
            pd.DataFrame(feature_rows), pd.DataFrame(micro_rows), pd.DataFrame(network_rows)
        )
        combined.to_csv(output/"combined_features.csv", index=False)
    except ImportError as exc: raise ImportError("CSV export requires pandas") from exc
    np.savez_compressed(output/"connectivity.npz", **connectivity)
    (output/"preprocessing_report.json").write_text(json.dumps(report, indent=2, default=str))

