import dataclasses
from uuid import uuid4

from domain.entities.analysis import NewAnalysis
import pytest



def test_new_analysis_is_immutable():
    a = NewAnalysis(uuid4(), 1.0, 0.5, None, 1)
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.result = 0.9  # type: ignore[misc]

def test_valid_analysis_requires_a_result():
    with pytest.raises(ValueError):
        NewAnalysis(uuid4(), 1.0, None, None, 1)


@pytest.mark.parametrize("result, confidence, reason", [
    (0.5, None, "x"),
    (None, 0.9, "x"),
    (None, None, None),
    (None, None, ""),
])
def test_invalid_analysis_shape_is_enforced(result, confidence, reason):
    with pytest.raises(ValueError):
        NewAnalysis(uuid4(), 1.0, result, confidence, 1, is_valid=False, invalid_reason=reason)


def test_invalid_analysis_without_result_is_allowed():
    a = NewAnalysis(uuid4(), 1.0, None, None, 1, is_valid=False, invalid_reason="null_features")
    assert a.result is None


def test_valid_analysis_cannot_carry_a_reason():
    with pytest.raises(ValueError):
        NewAnalysis(uuid4(), 1.0, 0.5, None, 1, is_valid=True, invalid_reason="x")