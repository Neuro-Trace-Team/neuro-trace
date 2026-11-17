from __future__ import annotations
import argparse, logging
from .config import PipelineConfig
from .pipeline import process_dataset

def main():
    p=argparse.ArgumentParser(description="EEG preprocessing and feature extraction")
    p.add_argument("--input", required=True); p.add_argument("--output", required=True)
    group=p.add_mutually_exclusive_group(required=True); group.add_argument("--all", action="store_true"); group.add_argument("--experiment"); p.add_argument("--subject")
    p.add_argument("--log-level", default="INFO")
    a=p.parse_args(); logging.basicConfig(level=getattr(logging,a.log_level.upper(),logging.INFO), format="%(levelname)s %(message)s")
    process_dataset(a.input,a.output,PipelineConfig(),None if a.all else a.experiment,a.subject)
if __name__ == "__main__": main()

