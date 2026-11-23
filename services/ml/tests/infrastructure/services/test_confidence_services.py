from infrastructure.services.confidence_services import CqrConfidence, ProbabilityConfidence, build_confidence_estimator
from infrastructure.services.sklearn_predictor import SklearnPredictor
import numpy as np
import pytest


FEATURES = ["a", "b"]
X = np.zeros((1, 2))
POINT = np.array([5.0])


class Const:
    def __init__(self, value):
        self.value = value
    def predict(self, X):
        return np.full(len(X), self.value)


class Classifier(Const):
    def predict_proba(self, X):
        return np.tile([0.3, 0.7], (len(X), 1))


def cqr(lo, hi, qhat=0.0, width_quantiles=None, out_max=10.0):
    return CqrConfidence(Const(lo), Const(hi), qhat=qhat, alpha=0.2,
                         out_max=out_max, width_quantiles=width_quantiles)




def test_interval_applies_qhat_and_is_clipped_to_the_output_range():
    c = cqr(1.0, 9.5, qhat=1.0).estimate(X, POINT, None)
    assert c.interval == {"lower": [0.0], "upper": [10.0]}


def test_crossed_quantiles_are_reordered():
    assert cqr(7.0, 3.0).estimate(X, POINT, None).interval == {"lower": [3.0], "upper": [7.0]}


def test_without_reference_widths_score_is_relative_to_the_output_range():
    c = cqr(4.0, 7.0).estimate(X, POINT, None)
    assert c.kind == "interval_width_scale" and c.values == pytest.approx([0.7])


@pytest.mark.parametrize("width, expected", [(0.5, 1.0), (2.0, 0.625), (2.5, 0.5), (99.0, 0.0)])
def test_score_is_one_minus_midrank_percentile_of_validation_widths(width, expected):
    c = cqr(0.0, width, width_quantiles=[1.0, 2.0, 3.0, 4.0], out_max=100.0).estimate(X, POINT, None)
    assert c.kind == "interval_width_percentile" and c.values == pytest.approx([expected])


def test_narrower_interval_scores_higher():
    ref = [1.0, 3.0, 5.0, 7.0]
    wide = cqr(2.0, 8.0, width_quantiles=ref).estimate(X, POINT, None).values[0]
    narrow = cqr(4.5, 5.5, width_quantiles=ref).estimate(X, POINT, None).values[0]
    assert narrow > wide


def test_estimate_returns_one_score_per_row():
    c = cqr(4.0, 6.0).estimate(np.zeros((3, 2)), np.array([5.0] * 3), None)
    assert len(c.values) == 3


def test_probability_confidence_is_the_probability_of_the_predicted_class():
    c = ProbabilityConfidence().estimate(X, np.array([1]), np.array([[0.2, 0.8]]))
    assert (c.values, c.kind) == ([0.8], "max_probability")


POINT_META = {"preproc_version": "p1", "target_version": "t1"}


def test_cqr_loads_from_the_shared_base_path(cqr_files):
    est = CqrConfidence.load(cqr_files(), feature_names=FEATURES, point_meta=POINT_META)
    assert (est.qhat, est.alpha, est.out_max) == (0.5, 0.2, 10.0)
    assert est.info()["nominal_coverage"] == 0.8


def test_cqr_adopts_feature_order_from_its_own_models_when_none_given(cqr_files):
    CqrConfidence.load(cqr_files(), feature_names=None, point_meta={})


@pytest.mark.parametrize("kwargs", [{"lo_features": ("b", "a")}, {"hi_features": ("a",)}])
def test_cqr_rejects_models_trained_on_different_features(cqr_files, kwargs):
    with pytest.raises(RuntimeError, match="different feature"):
        CqrConfidence.load(cqr_files(**kwargs), feature_names=FEATURES, point_meta={})


@pytest.mark.parametrize("key", ["preproc_version", "target_version"])
def test_cqr_rejects_version_mismatch_with_point_model(cqr_files, key):
    with pytest.raises(RuntimeError, match=key):
        CqrConfidence.load(cqr_files(), feature_names=FEATURES, point_meta={key: "other"})


def test_cqr_ignores_versions_missing_on_the_point_model(cqr_files):
    CqrConfidence.load(cqr_files(), feature_names=FEATURES, point_meta={})


@pytest.mark.parametrize("bad", [
    {"qhat": -1.0}, {"qhat": "x"}, {"alpha": 0.0}, {"alpha": 1.0}, {"out_max": 0.0},
    {"width_quantiles": [3.0, 1.0]}, {"width_quantiles": ["a"]},
])
def test_cqr_rejects_invalid_interval_metadata(cqr_files, bad):
    with pytest.raises(RuntimeError):
        CqrConfidence.load(cqr_files(interval=bad), feature_names=FEATURES, point_meta={})


def test_cqr_without_width_quantiles_falls_back_to_scale_score(cqr_files):
    est = CqrConfidence.load(cqr_files(interval={"width_quantiles": None}),
                             feature_names=FEATURES, point_meta={})
    assert est.kind == "interval_width_scale"


def test_cqr_missing_files_fail_loudly(tmp_path):
    with pytest.raises(FileNotFoundError):
        CqrConfidence.load(tmp_path / "nope", feature_names=FEATURES, point_meta={})


def test_cqr_rejects_lfs_pointer(cqr_files):
    base = cqr_files()
    (base.parent / f"{base.name}_lo.joblib").write_text("version https://git-lfs.github.com/spec/v1\n")
    with pytest.raises(RuntimeError, match="LFS pointer"):
        CqrConfidence.load(base, feature_names=FEATURES, point_meta={})


def test_regressor_without_cqr_has_no_estimator():
    assert build_confidence_estimator(Const(1.0), feature_names=FEATURES,
                                      cqr_base_path=None, point_meta={}) is None


def test_classifier_gets_probability_confidence():
    assert isinstance(build_confidence_estimator(Classifier(1.0), feature_names=FEATURES,
                                                 cqr_base_path="", point_meta={}), ProbabilityConfidence)


def test_configured_cqr_beats_predict_proba(cqr_files):
    est = build_confidence_estimator(Classifier(1.0), feature_names=FEATURES,
                                     cqr_base_path=str(cqr_files()), point_meta=POINT_META)
    assert isinstance(est, CqrConfidence)


def make_predictor(estimator=None):
    p = SklearnPredictor(feature_names=FEATURES)
    p.model = Const(5.0)
    p.confidence_estimator = estimator
    return p


FEATURES_IN = {"a": 1.0, "b": 2.0}


def test_predict_returns_confidence_fields_from_the_estimator():
    r = make_predictor(cqr(4.0, 6.0)).predict(FEATURES_IN)
    assert r["confidence"] == pytest.approx([0.8])
    assert r["confidence_kind"] == "interval_width_scale"
    assert r["interval"] == {"lower": [4.0], "upper": [6.0]}


def test_prediction_is_identical_with_and_without_confidence():
    far_away = cqr(9.0, 9.5)
    assert (make_predictor(far_away).predict(FEATURES_IN)["prediction"]
            == make_predictor().predict(FEATURES_IN)["prediction"] == [5.0])


def test_no_estimator_means_no_confidence():
    r = make_predictor().predict(FEATURES_IN)
    assert (r["confidence"], r["confidence_kind"], r["interval"]) == (None, None, None)


def test_estimator_failure_degrades_to_no_confidence(caplog):
    class Broken:
        def estimate(self, *args):
            raise RuntimeError("boom")
        def info(self):
            return {}

    r = make_predictor(Broken()).predict(FEATURES_IN)

    assert (r["prediction"], r["confidence"]) == ([5.0], None)
    assert "Confidence estimation failed" in caplog.text


def test_model_info_reports_the_estimator():
    assert make_predictor(cqr(4.0, 6.0)).model_info()["confidence"]["method"] == "cqr"
    assert make_predictor().model_info()["confidence"] is None
