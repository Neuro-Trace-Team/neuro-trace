import dataclasses
from uuid import uuid4

from domain.entities.analysis import NewAnalysis
import pytest



def test_new_analysis_is_immutable():
    a = NewAnalysis(uuid4(), 1.0, 0.5, None, 1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.result = 0.9  # type: ignore[misc]