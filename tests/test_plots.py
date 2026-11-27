"""
test_plots.py: every figure builds, in both versions, on normal and zero-variance data.

Why this exists
---------------
The dashboard and the report depend on these figures. They must never crash,
must carry the MOCK warning on dry-run data, and must not invent intervals
when the AI answers have no variance.
"""

import dataclasses

import matplotlib.pyplot as plt
import pandas as pd
import pytest

from gp4.analysis import analyze, load_results
from gp4.config import load_config, verify_stimuli
from gp4.llm_client import MockClient
from gp4.plots import (
    distribution_mpl,
    distribution_plotly,
    forest_mpl,
    forest_plotly,
    save_report_figures,
    size_histogram_mpl,
    size_histogram_plotly,
)
from gp4.run_experiment import run_experiment


@pytest.fixture(scope="module", params=["fake_effect", "identical"])
def dataset(request, tmp_path_factory):
    config = dataclasses.replace(load_config(), mediation_bootstrap_samples=200)
    out = run_experiment(config, "main", MockClient(config, request.param, verify_stimuli()), dry_run=True,
                         echo=False, out_dir=tmp_path_factory.mktemp(request.param))
    frame = load_results(out.csv_path)
    return frame, analyze(frame, config), out.csv_path.stem


@pytest.mark.parametrize("measure", ["size", "attention", "arousal", "mood"])
def test_distribution_figures(dataset, measure):
    frame, result, _ = dataset
    fig = distribution_plotly(frame, measure, is_mock=True)
    assert fig.layout.title.text.startswith("MOCK DATA, NOT RESULTS")
    plt.close(distribution_mpl(frame, measure, is_mock=True))


def test_histogram_and_forest(dataset):
    frame, result, _ = dataset
    assert size_histogram_plotly(frame, True).layout.title.text.startswith("MOCK")
    forest = forest_plotly(result.comparison, True)
    ai_trace = [t for t in forest.data if t.name == "AI agents"][0]
    if result.anova.zero_variance.all():
        # no fake numbers, in the hover text or in the printed labels (a separate text-only trace)
        assert all(text == "undefined (zero variance)" for text in ai_trace.customdata)
        ai_index = list(forest.data).index(ai_trace)
        assert all(text == "undefined (zero variance)" for text in forest.data[ai_index + 1].text)
    plt.close(size_histogram_mpl(frame, True))
    plt.close(forest_mpl(result.comparison, True))


def test_save_report_figures(dataset, tmp_path):
    frame, result, stem = dataset
    paths = save_report_figures(frame, result, tmp_path, stem)
    assert len(paths) == 6 and all(p.stat().st_size > 10_000 for p in paths)


def test_r_labels_round_half_up():
    """The published r = .295 must print as +0.30, not +0.29 (float storage quirk)."""
    from gp4.plots import _r_text
    assert _r_text(0.295) == "+0.30"
    assert _r_text(0.249) == "+0.25"
    assert _r_text(-0.0727) == "-0.07"


def test_mood_original_bound_is_derived_and_small():
    """p > .87 with n = 77 (df 75) implies |r| < about .02; check against a direct t calculation."""
    from scipy import stats
    from gp4.benchmarks import mood_original_r_bound
    bound = mood_original_r_bound()
    assert round(bound, 2) == 0.02
    # round trip: the p-value of the t that gives this r is exactly .87
    t = bound * (75 / (1 - bound ** 2)) ** 0.5
    assert abs(2 * stats.t.sf(t, 75) - 0.87) < 1e-9


def test_forest_shows_mood_bound_band(dataset):
    """Both forest charts carry the derived band and label for the original's mood row."""
    _, result, _ = dataset
    fig = forest_plotly(result.comparison, is_mock=True)
    assert any(s.type == "rect" for s in fig.layout.shapes)
    assert any("derived from p > .87" in (a.text or "") for a in fig.layout.annotations)
    mfig = forest_mpl(result.comparison, is_mock=True)
    assert any("derived from p > .87" in t.get_text() for t in mfig.axes[0].texts)
    plt.close(mfig)


def test_size_histogram_low_bars_are_filled(dataset):
    """The hatched low-saturation bars need a background colour, or they are invisible on the pale chart."""
    frame, _, _ = dataset
    fig = size_histogram_plotly(frame, True)
    low = [t for t in fig.data if t.name == "Low saturation"][0]
    assert low.marker.pattern.bgcolor == low.marker.color
