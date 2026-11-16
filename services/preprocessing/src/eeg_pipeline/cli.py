from __future__ import annotations
import argparse, json, logging
from pathlib import Path
from .config import PipelineConfig
from .pipeline import process_dataset

def main():
    p=argparse.ArgumentParser(description="EEG preprocessing and feature extraction")
    p.add_argument("--input", required=True); p.add_argument("--output", required=True)
    group=p.add_mutually_exclusive_group(required=True); group.add_argument("--all", action="store_true"); group.add_argument("--experiment"); p.add_argument("--subject")
    p.add_argument("--epoch-peak-to-peak-uv", type=float, default=150.0,
                   help="Maximum per-channel epoch peak-to-peak in microvolts (default: 150)")
    p.add_argument("--isi-warning-threshold-seconds", type=float, default=11.0)
    p.add_argument("--baseline-protected-response-seconds", type=float, default=5.5)
    p.add_argument("--baseline-overlap-policy", choices=("reject", "trim"), default="trim")
    p.add_argument("--baseline-min-seconds", type=float, default=2.0)
    p.add_argument("--lowpass", type=float, default=100.0)
    p.add_argument("--target-sfreq", type=float, default=256.0)
    p.add_argument("--disable-high-gamma", action="store_true")
    p.add_argument("--disable-ica", action="store_true")
    p.add_argument("--tfr-config", help="JSON file with TFRConfig overrides; see docs/tfr.md")
    p.add_argument("--lep-config", help="JSON file with LEPConfig overrides; see docs/lep.md")
    p.add_argument("--log-level", default="INFO")
    a=p.parse_args(); logging.basicConfig(level=getattr(logging,a.log_level.upper(),logging.INFO), format="%(levelname)s %(message)s")
    process_dataset(a.input,a.output,PipelineConfig(epoch_peak_to_peak_uv=a.epoch_peak_to_peak_uv,
        tfr=json.loads(Path(a.tfr_config).read_text()) if a.tfr_config else {},
        lep=json.loads(Path(a.lep_config).read_text()) if a.lep_config else {},
        lowpass=a.lowpass, analysis_band=(0.5, a.lowpass), target_sfreq=a.target_sfreq,
        high_gamma_band=None if a.disable_high_gamma else (60.0, 90.0), enable_ica=not a.disable_ica,
        isi_warning_threshold_seconds=a.isi_warning_threshold_seconds,
        baseline_protected_response_seconds=a.baseline_protected_response_seconds,
        baseline_overlap_policy=a.baseline_overlap_policy, baseline_min_seconds=a.baseline_min_seconds),None if a.all else a.experiment,a.subject)
if __name__ == "__main__": main()

