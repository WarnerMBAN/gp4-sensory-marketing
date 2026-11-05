"""
test_analysis.py: check our effect-size maths against the published human values.

Why this exists
---------------
"Statistics must be checked, not assumed." If our formulas reproduce the
numbers printed in the two papers, we can trust them on the AI data.

What is checked
---------------
1. r from F:   original .295, .249, .299; replication .011, .238, .180.
2. Cohen's d from means and SDs (assumed cell n): original 0.61, 0.51, 0.61;
   replication 0.02, 0.50, 0.36.
3. Fisher-z 95% CIs for r match the replication paper's table, including the
   cross-check [.076, .487] for the original size effect.
4. Partial eta-squared from F matches the papers (one known rounding
   discrepancy in the replication, documented below).
5. Zero-variance data gives NaN, not a fake number.
"""

import math

import pytest

from gp4.analysis import (
    cohens_d,
    partial_eta_squared_from_f,
    r_confidence_interval,
    r_from_f,
)
from gp4.benchmarks import ORIGINAL, REPLICATION

ALL = [(src, m, b) for src, table in (("original", ORIGINAL), ("replication", REPLICATION)) for m, b in table.items()]
IDS = [f"{src}-{m}" for src, m, _ in ALL]


@pytest.mark.parametrize("source,measure,bench", ALL, ids=IDS)
def test_r_from_f_reproduces_published_r(source, measure, bench):
    """r = sqrt(F / (F + df)) rounds to the published r (3 decimals)."""
    r = r_from_f(bench.f_value, bench.df_error)
    assert round(r, 3) == pytest.approx(bench.r_published, abs=1e-9), f"{source} {measure}: got {r:.4f}"


def test_r_from_f_named_values():
    """The six headline values from the build prompt, spelled out explicitly."""
    assert round(r_from_f(7.13, 75), 3) == 0.295
    assert round(r_from_f(4.95, 75), 3) == 0.249
    assert round(r_from_f(7.35, 75), 3) == 0.299
    assert round(r_from_f(0.095, 821), 3) == 0.011
    assert round(r_from_f(49.238, 821), 3) == 0.238
    assert round(r_from_f(27.539, 821), 3) == 0.180


EXPECTED_D = {
    ("original", "size"): 0.61,
    ("original", "attention"): 0.51,
    ("original", "arousal"): 0.61,
    ("replication", "size"): 0.02,
    ("replication", "attention"): 0.50,
    ("replication", "arousal"): 0.36,
}


@pytest.mark.parametrize("source,measure,bench", ALL, ids=IDS)
def test_cohens_d_from_means(source, measure, bench):
    """d from the published means and SDs (with the ASSUMED cell n) rounds to the expected value."""
    d = cohens_d(bench.high.mean, bench.high.sd, bench.high.n, bench.low.mean, bench.low.sd, bench.low.n)
    assert round(d, 2) == EXPECTED_D[(source, measure)], f"{source} {measure}: got {d:.4f}"


def test_original_size_ci_matches_replication_paper_crosscheck():
    """The replication paper prints [.076, .487] for the original size effect."""
    r = r_from_f(7.13, 75)
    low, high = r_confidence_interval(r, 77)
    assert (round(low, 3), round(high, 3)) == (0.076, 0.487)


@pytest.mark.parametrize("source,measure,bench", ALL, ids=IDS)
def test_r_confidence_intervals_match_published(source, measure, bench):
    """Every Fisher-z 95% CI is within 0.001 of the published one (rounding)."""
    r = r_from_f(bench.f_value, bench.df_error)
    low, high = r_confidence_interval(r, bench.n_total)
    assert low == pytest.approx(bench.r_ci_published[0], abs=0.0011), f"{source} {measure} lower {low:.4f}"
    assert high == pytest.approx(bench.r_ci_published[1], abs=0.0011), f"{source} {measure} upper {high:.4f}"


@pytest.mark.parametrize("source,measure,bench", ALL, ids=IDS)
def test_partial_eta_squared_matches_published(source, measure, bench):
    """Partial eta-squared from F matches the printed value.

    Original values are printed to 2 decimals, replication to 3. Known
    discrepancy: replication arousal is printed as .033, but F = 27.539 with
    df (1, 821) gives .0325, which rounds to .032. We allow 0.001 for that.
    """
    eta = partial_eta_squared_from_f(bench.f_value, 1, bench.df_error)
    decimals = 2 if source == "original" else 3
    assert eta == pytest.approx(bench.eta_sq_published, abs=0.5 * 10**-decimals + 0.0006)


def test_zero_variance_gives_nan_not_fake_numbers():
    """If every agent gives the same answer, d and the r CI must be NaN, not a number."""
    assert math.isnan(cohens_d(15, 0, 39, 15, 0, 38))
    low, high = r_confidence_interval(1.0, 77)
    assert math.isnan(low) and math.isnan(high)


# ---------------------------------------------------------------------------
# Phase 4: the full analysis, checked against independent implementations
# ---------------------------------------------------------------------------

import numpy as np
import pandas as pd
from scipy import stats as sstats
from statsmodels.formula.api import ols
from statsmodels.stats.weightstats import ttost_ind

from gp4.analysis import (
    classify_outcome,
    comparison_table,
    fisher_z_compare,
    partial_eta_squared_ci,
    serial_mediation,
    tost,
    two_group_test,
)

RNG = np.random.default_rng(7)
HIGH = RNG.normal(15.3, 1.3, 39).round()
LOW = RNG.normal(14.4, 1.6, 38).round()


def test_two_group_test_matches_scipy_and_statsmodels():
    out = two_group_test(HIGH, LOW, 0.05)
    f_ref, p_ref = sstats.f_oneway(HIGH, LOW)
    assert out["F"] == pytest.approx(f_ref) and out["p"] == pytest.approx(p_ref)
    r_ref = sstats.pointbiserialr(np.r_[np.ones(39), np.zeros(38)], np.r_[HIGH, LOW])[0]
    assert out["r"] == pytest.approx(r_ref)  # signed r = point-biserial correlation
    t_ref = sstats.ttest_ind(HIGH, LOW)
    ci = t_ref.confidence_interval()
    assert (out["diff_ci_low"], out["diff_ci_high"]) == pytest.approx((ci.low, ci.high))


def test_eta_squared_ci_contains_estimate_and_is_ordered():
    low, high = partial_eta_squared_ci(7.13, 1, 75)
    assert 0 < low < partial_eta_squared_from_f(7.13, 1, 75) < high < 1
    assert partial_eta_squared_ci(0.095, 1, 821)[0] == 0.0  # null effect: lower bound at zero


def test_tost_matches_statsmodels():
    ours = tost(HIGH, LOW, bound=0.5, alpha=0.05)
    p_ref, _, _ = ttost_ind(HIGH, LOW, -0.5, 0.5, usevar="pooled")
    assert ours["p_tost"] == pytest.approx(p_ref)


def test_tost_shows_equivalence_for_a_true_null():
    same = RNG.normal(15, 1, 400).round()
    other = RNG.normal(15, 1, 400).round()
    assert tost(same, other, 0.5, 0.05)["equivalent"] is True


def test_fisher_z_compare_known_value():
    z, p = fisher_z_compare(0.295, 77, 0.011, 823)
    expected = (math.atanh(0.295) - math.atanh(0.011)) / math.sqrt(1 / 74 + 1 / 820)
    assert z == pytest.approx(expected) and 0 < p < 0.05


def _frame(high, low, att_high, att_low, aro_high, aro_low, mood_high, mood_low):
    rows = []
    for cond, size, att, aro, mood in (("high", high, att_high, aro_high, mood_high),
                                       ("low", low, att_low, aro_low, mood_low)):
        for s, a, r, m in zip(size, att, aro, mood):
            rows.append({"condition": cond, "screen_size": s, "attention": a, "arousal": r, "mood": m,
                         "valid": True})
    return pd.DataFrame(rows)


def test_mediation_point_estimates_match_statsmodels():
    n = 60
    x = np.r_[np.ones(n), np.zeros(n)]
    aro = 5 + 0.8 * x + RNG.normal(0, 1, 2 * n)
    att = 4 + 0.3 * x + 0.5 * aro + RNG.normal(0, 1, 2 * n)
    size = 12 + 0.2 * x + 0.1 * aro + 0.4 * att + RNG.normal(0, 1, 2 * n)
    df = pd.DataFrame({"condition": np.where(x == 1, "high", "low"), "screen_size": size,
                       "attention": att, "arousal": aro, "valid": True, "x": x})
    res = serial_mediation(df, n_boot=200, seed=1)
    a1 = ols("arousal ~ x", df).fit().params["x"]
    m2 = ols("attention ~ x + arousal", df).fit().params
    y = ols("screen_size ~ x + arousal + attention", df).fit().params
    expected_total = a1 * y["arousal"] + a1 * m2["arousal"] * y["attention"] + m2["x"] * y["attention"]
    assert res["paths"]["total_indirect"] == pytest.approx(expected_total)
    lo, hi = res["ci95"]["total_indirect"]
    assert lo < res["paths"]["total_indirect"] < hi


def _anova_for(effects):
    """Minimal anova/comparison tables with chosen (r, p) per measure, for the classifier."""
    rows = []
    for measure, (r, p) in effects.items():
        rows.append({"measure": measure, "r": r, "p": p, "significant": p < 0.05, "zero_variance": False,
                     "n_total": 77, "F": 1.0, "r_ci_low": r - .2, "r_ci_high": r + .2, "d": r * 2,
                     "mean_high": 1, "mean_low": 1, "sd_high": 1, "sd_low": 1})
    anova = pd.DataFrame(rows)
    return anova, comparison_table(anova, 0.05)


@pytest.mark.parametrize("effects,label", [
    ({"size": (.30, .01), "attention": (.25, .03), "arousal": (.30, .01), "mood": (0, .9)}, "A"),
    ({"size": (.01, .90), "attention": (.25, .03), "arousal": (.20, .04), "mood": (0, .9)}, "B"),
    ({"size": (.01, .90), "attention": (.05, .60), "arousal": (.02, .80), "mood": (0, .9)}, "C"),
    ({"size": (.01, .90), "attention": (.25, .03), "arousal": (.20, .04), "mood": (.3, .01)}, "D"),
    ({"size": (.01, .90), "attention": (.90, .0001), "arousal": (.20, .04), "mood": (0, .9)}, "D"),
    ({"size": (.30, .01), "attention": (.05, .60), "arousal": (.02, .80), "mood": (0, .9)}, "Mixed"),
    ({"size": (-.30, .01), "attention": (.25, .03), "arousal": (.30, .01), "mood": (0, .9)}, "Mixed"),
])
def test_outcome_classifier(effects, label):
    anova, comparison = _anova_for(effects)
    assert classify_outcome(anova, comparison, 0.05)["label"] == label


def test_zero_variance_two_group_no_crash():
    out = two_group_test(np.full(39, 15.0), np.full(38, 15.0), 0.05)
    assert out["zero_variance"] and math.isnan(out["F"]) and math.isnan(out["r_ci_low"])
    assert tost(np.full(39, 15.0), np.full(38, 15.0), 0.5, 0.05)["equivalent"] is None
