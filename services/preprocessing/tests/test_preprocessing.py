import numpy as np
import pytest
from eeg_pipeline.preprocessing import canonical_channel, select_channels
from eeg_pipeline.config import EEG_CHANNELS

class Raw:
    def __init__(self,names): self.ch_names=names

def test_aliases_and_order():
    raw=Raw(["EOG", "T3"]+[x for x in EEG_CHANNELS if x != "T7"])
    idx,names=select_channels(raw)
    assert names[7] == "T3"
    assert canonical_channel("T3")=="T7"

def test_missing_channel_rejected():
    with pytest.raises(ValueError): select_channels(Raw(EEG_CHANNELS[:-1]))

