"""
analysis.py: statistics for the AI data and the human-AI comparison.

Where it fits
-------------
STEP 8 of the pipeline. Reads the tidy CSV written by run_experiment.py and
the human numbers in benchmarks.py. Used by scripts/analyze.py (tables and
figures for the report) and by the Streamlit dashboard.

Flow of analyze() (numbered to match the comments below)
--------------------------------------------------------
  STEP 1 of 8  Data quality: agents, valid rate, retries, zero-variance flags.
  STEP 2 of 8  Descriptives by condition (n, mean, SD, median, range).
  STEP 3 of 8  One-way ANOVA per measure (size, attention, arousal, mood),
               with r, Cohen's d and partial eta-squared, each with a 95% CI.
  STEP 4 of 8  Human-AI comparison: AI r vs original r and vs replication r
               (Fisher-z test), plus level and spread where scales match.
  STEP 5 of 8  TOST equivalence test for the size effect (bound from config).
  STEP 6 of 8  Mood placebo check (a mood difference signals a halo response).
  STEP 7 of 8  Outcome label A-D, with the reasons spelled out.
  STEP 8 of 8  Mediation, ONLY if the AI size effect appears (the original
               study's own rule); otherwise recorded as skipped, with why.

Zero variance (every agent gives the same answer)
-------------------------------------------------
Tests and intervals are then undefined. The code reports NaN (blank) and a
plain-English flag rather than crashing or printing a fake interval.

What goes in and out
--------------------
In:  a data frame from a run CSV; the Config (alpha, TOST bound, bootstrap
     samples, seed).
Out: an AnalysisResult holding pandas tables and plain dictionaries.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import optimize, stats

from gp4.benchmarks import BENCHMARKS, MOOD_ORIGINAL, Benchmark
from gp4.config import Config

# Measures in question order: short name -> CSV column.
MEASURE_COLUMNS: dict[str, str] = {
    "size": "screen_size",
    "attention": "attention",
    "arousal": "arousal",
    "mood": "mood",
}
MEASURE_LABELS: dict[str, str] = {
    "size": "Screen-size estimate (inches, 10-20)",
    "attention": "Attention (mean of 2 items, 1-7)",
    "arousal": "Arousal (1-9)",
    "mood": "Mood (1-9, placebo)",
}
# The three measures the original study predicted would rise with saturation.
EFFECT_MEASURES: tuple[str, ...] = ("size", "attention", "arousal")

OUTCOME_NAMES: dict[str, str] = {
    "A": "Full original pattern (size, attention and arousal all higher for high saturation)",
    "B": "Replication pattern (attention and arousal higher, no size effect)",
    "C": "Blind to saturation (no effect on size, attention or arousal)",
    "D": "Exaggerated or halo effect (mood also differs, or an effect is larger than the original's)",
    "Mixed": "Mixed pattern (does not match A to D; see reasons)",
}


# ==========================================================================
# Effect-size helpers (checked against published values in test_analysis.py)
# ==========================================================================

def r_from_f(f_value: float, df_error: int) -> float:
    """Effect size r from a one-way, two-group F test: r = sqrt(F / (F + df_error)).

    Inputs:  F statistic with 1 numerator df; error (denominator) df.
    Output:  r between 0 and 1 (unsigned; direction comes from the means).
    Why this exists: the replication paper converts every original F into r
    this way, so we use the same formula for the human and AI results.
    """
    if f_value < 0 or df_error <= 0:
        raise ValueError("F must be >= 0 and df_error must be > 0.")
    return math.sqrt(f_value / (f_value + df_error))


def partial_eta_squared_from_f(f_value: float, df_effect: int, df_error: int) -> float:
    """Partial eta-squared from F: (F * df_effect) / (F * df_effect + df_error).

    Share of variance explained by condition, as printed in both papers.
    """
    numerator = f_value * df_effect
    return numerator / (numerator + df_error)


def pooled_sd(sd_1: float, n_1: int, sd_2: float, n_2: int) -> float:
    """Pooled standard deviation of two groups (weights each by n - 1)."""
    pooled_variance = ((n_1 - 1) * sd_1**2 + (n_2 - 1) * sd_2**2) / (n_1 + n_2 - 2)
    return math.sqrt(pooled_variance)


def cohens_d(mean_1: float, sd_1: float, n_1: int, mean_2: float, sd_2: float, n_2: int) -> float:
    """Cohen's d: (mean_1 - mean_2) / pooled SD. Positive when group 1 is higher.

    Returns NaN when the pooled SD is zero (every answer identical), because
    a standardised difference is undefined then. Never a fake number.
    """
    spread = pooled_sd(sd_1, n_1, sd_2, n_2)
    if spread == 0:
        return float("nan")
    return (mean_1 - mean_2) / spread


def fisher_z(r: float) -> float:
    """Fisher's z transform of r: atanh(r). Makes r roughly normal for CIs and tests."""
    return math.atanh(r)


def r_confidence_interval(r: float, n: int, confidence: float = 0.95) -> tuple[float, float]:
    """Confidence interval for a correlation-type r, via Fisher's z.

    Inputs:  r; total sample size n (needs n > 3); confidence level.
    Output:  (lower, upper) on the r scale.
    Why this exists: the replication paper reports r with 95% CIs computed
    this way; we use the same method for the AI results so they are comparable.
    Returns (NaN, NaN) when r is NaN or exactly +1 or -1 (zero variance),
    rather than a misleading interval.
    """
    if n <= 3:
        raise ValueError("Need n > 3 for a Fisher-z confidence interval.")
    if math.isnan(r) or abs(r) >= 1:
        return float("nan"), float("nan")
    z_crit = stats.norm.ppf(0.5 + confidence / 2)
    standard_error = 1 / math.sqrt(n - 3)
    centre = fisher_z(r)
    return math.tanh(centre - z_crit * standard_error), math.tanh(centre + z_crit * standard_error)


def partial_eta_squared_ci(f_value: float, df_effect: int, df_error: int,
                           confidence: float = 0.95) -> tuple[float, float]:
    """Confidence interval for partial eta-squared, by inverting the noncentral F.

    Method (Steiger 2004): find the noncentrality values whose F distributions
    put the observed F at the 97.5th and 2.5th percentiles, then convert each
    to eta-squared = ncp / (ncp + df_effect + df_error + 1). The lower bound
    is 0 when even ncp = 0 cannot place F that high.
    Returns (NaN, NaN) when F is undefined or infinite (zero variance).
    """
    if not math.isfinite(f_value):
        return float("nan"), float("nan")
    upper_tail = 0.5 + confidence / 2  # 0.975
    lower_tail = 1 - upper_tail        # 0.025

    def cdf_at(ncp: float) -> float:
        return stats.ncf.cdf(f_value, df_effect, df_error, ncp)

    def to_eta(ncp: float) -> float:
        return ncp / (ncp + df_effect + df_error + 1)

    def solve(target: float) -> float:
        if cdf_at(0.0) <= target:
            return 0.0
        high = max(10.0, 10 * f_value)
        while cdf_at(high) > target:
            high *= 2
        return optimize.brentq(lambda ncp: cdf_at(ncp) - target, 0.0, high)

    return to_eta(solve(upper_tail)), to_eta(solve(lower_tail))


def fisher_z_compare(r_1: float, n_1: int, r_2: float, n_2: int) -> tuple[float, float]:
    """Test whether two independent r values differ (Fisher z test).

    Output: (z, two-sided p). z > 0 means r_1 is larger.
    Returns (NaN, NaN) if either r is undefined or exactly +/-1.
    Why this exists: it answers "is the AI effect the same size as the human
    effect?" with a test, not just by eye.
    """
    if any(math.isnan(x) or abs(x) >= 1 for x in (r_1, r_2)) or min(n_1, n_2) <= 3:
        return float("nan"), float("nan")
    z = (fisher_z(r_1) - fisher_z(r_2)) / math.sqrt(1 / (n_1 - 3) + 1 / (n_2 - 3))
    return z, 2 * stats.norm.sf(abs(z))


# ==========================================================================
# STEP 3: two-group comparison for one measure
# ==========================================================================

def two_group_test(high: np.ndarray, low: np.ndarray, alpha: float) -> dict[str, Any]:
    """One-way ANOVA (two groups) with effect sizes and confidence intervals.

    Inputs:  answers in the high and low conditions; alpha.
    Output:  dictionary of n, means, SDs, difference (high - low) with CI,
             F, p, signed r with CI, Cohen's d with CI, partial eta-squared
             with CI, and flags (significant, zero_variance, note).
    F is computed from sums of squares (identical to scipy's f_oneway and to
    t squared) so that zero variance can be handled explicitly.
    """
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    n_1, n_2 = len(high), len(low)
    out: dict[str, Any] = {"n_high": n_1, "n_low": n_2}
    if n_1 < 2 or n_2 < 2:
        out.update(note="fewer than 2 valid answers in a condition; no test possible",
                   significant=False, zero_variance=False)
        return out

    m_1, m_2 = high.mean(), low.mean()
    sd_1, sd_2 = high.std(ddof=1), low.std(ddof=1)
    df_error = n_1 + n_2 - 2
    n_total = n_1 + n_2
    grand = np.concatenate([high, low]).mean()
    ss_between = n_1 * (m_1 - grand) ** 2 + n_2 * (m_2 - grand) ** 2
    ss_within = (n_1 - 1) * sd_1**2 + (n_2 - 1) * sd_2**2
    diff = m_1 - m_2
    out.update(mean_high=m_1, sd_high=sd_1, mean_low=m_2, sd_low=sd_2,
               diff=diff, df_effect=1, df_error=df_error, n_total=n_total)

    zero_within = ss_within == 0
    out["zero_variance"] = bool(zero_within)
    if zero_within:
        # Every agent in each condition gave the same answer. Tests are undefined.
        identical = ss_between == 0
        out.update(
            F=float("nan") if identical else float("inf"),
            p=float("nan"),
            r=float("nan"), r_ci_low=float("nan"), r_ci_high=float("nan"),
            d=float("nan"), d_ci_low=float("nan"), d_ci_high=float("nan"),
            eta_sq=float("nan"), eta_ci_low=float("nan"), eta_ci_high=float("nan"),
            diff_ci_low=float("nan"), diff_ci_high=float("nan"),
            significant=False,
            note=("zero variance: every agent gave the same answer"
                  + ("" if identical else " within each condition, but the conditions differ")
                  + "; tests and intervals are undefined"),
        )
        return out

    f_value = (ss_between / 1) / (ss_within / df_error)
    p_value = stats.f.sf(f_value, 1, df_error)
    spread = math.sqrt(ss_within / df_error)
    r = math.copysign(r_from_f(f_value, df_error), diff) if diff != 0 else 0.0
    r_lo, r_hi = r_confidence_interval(r, n_total)
    d = diff / spread
    d_se = math.sqrt(n_total / (n_1 * n_2) + d**2 / (2 * n_total))  # large-sample approximation
    z_crit = stats.norm.ppf(0.975)
    t_crit = stats.t.ppf(0.975, df_error)
    diff_se = spread * math.sqrt(1 / n_1 + 1 / n_2)
    eta = partial_eta_squared_from_f(f_value, 1, df_error)
    eta_lo, eta_hi = partial_eta_squared_ci(f_value, 1, df_error)
    out.update(
        F=f_value, p=p_value,
        r=r, r_ci_low=r_lo, r_ci_high=r_hi,
        d=d, d_ci_low=d - z_crit * d_se, d_ci_high=d + z_crit * d_se,
        eta_sq=eta, eta_ci_low=eta_lo, eta_ci_high=eta_hi,
        diff_ci_low=diff - t_crit * diff_se, diff_ci_high=diff + t_crit * diff_se,
        significant=bool(p_value < alpha),
        note="",
    )
    return out


# ==========================================================================
# STEPS 1-2: data quality and descriptives
# ==========================================================================

def load_results(csv_path: Path | str) -> pd.DataFrame:
    """Read a run CSV. Booleans stay booleans; ratings stay numbers (blank = NaN)."""
    frame = pd.read_csv(csv_path)
    for column in ("valid", "dry_run"):
        frame[column] = frame[column].astype(str).str.lower().eq("true")
    return frame


def valid_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Only agents with valid answers (invalid agents are excluded from analysis)."""
    return frame[frame["valid"]].copy()


def data_quality(frame: pd.DataFrame) -> dict[str, Any]:
    """STEP 1: headline counts and warnings about the data.

    Duplicate-answer share: how many agents gave an answer vector (all five
    ratings) identical to another agent's. High values mean the model's
    answers have collapsed onto a few patterns.
    """
    valid = valid_rows(frame)
    ratings = ["screen_size", "attention_getting", "capture_attention", "arousal", "mood"]
    duplicated = valid.duplicated(subset=ratings, keep=False).mean() if len(valid) else float("nan")
    flags: list[str] = []
    for measure, column in MEASURE_COLUMNS.items():
        for condition in ("high", "low"):
            values = valid.loc[valid["condition"] == condition, column].dropna()
            if len(values) >= 2 and values.nunique() == 1:
                flags.append(f"{measure}, {condition}: every agent answered {values.iloc[0]:g}")
    return {
        "is_mock": bool(frame["dry_run"].any()),
        "run_labels": sorted(frame["run_label"].unique()),
        "run_ids": sorted(frame["run_id"].astype(str).unique()),
        "models": sorted(frame["model"].astype(str).unique()),
        "prompt_shas": sorted(frame["prompt_sha"].astype(str).unique()),
        "n_agents": int(len(frame)),
        "n_valid": int(len(valid)),
        "n_invalid": int((~frame["valid"]).sum()),
        "valid_rate": float(len(valid) / len(frame)) if len(frame) else float("nan"),
        "n_high_valid": int((valid["condition"] == "high").sum()),
        "n_low_valid": int((valid["condition"] == "low").sum()),
        "n_retried": int((frame["attempts"] > 1).sum()),
        "total_calls": int(frame["attempts"].sum()),
        "size_values_used": sorted(int(v) for v in valid["screen_size"].dropna().unique()),
        "duplicate_answer_share": float(duplicated),
        "zero_variance_flags": flags,
    }


def describe(frame: pd.DataFrame) -> pd.DataFrame:
    """STEP 2: n, mean, SD, median, min, max and number of distinct answers, by measure and condition."""
    valid = valid_rows(frame)
    rows = []
    for measure, column in MEASURE_COLUMNS.items():
        for condition in ("high", "low"):
            values = valid.loc[valid["condition"] == condition, column].dropna()
            rows.append({
                "measure": measure, "condition": condition, "n": len(values),
                "mean": values.mean(), "sd": values.std(ddof=1), "median": values.median(),
                "min": values.min(), "max": values.max(), "n_distinct": values.nunique(),
            })
    return pd.DataFrame(rows)


# ==========================================================================
# STEP 3: ANOVA table
# ==========================================================================

def anova_table(frame: pd.DataFrame, alpha: float) -> pd.DataFrame:
    """STEP 3: one row per measure with the full two_group_test output."""
    valid = valid_rows(frame)
    rows = []
    for measure, column in MEASURE_COLUMNS.items():
        high = valid.loc[valid["condition"] == "high", column].dropna().to_numpy()
        low = valid.loc[valid["condition"] == "low", column].dropna().to_numpy()
        rows.append({"measure": measure, **two_group_test(high, low, alpha)})
    return pd.DataFrame(rows)


# ==========================================================================
# STEP 4: human-AI comparison
# ==========================================================================

def human_row(bench: Benchmark) -> dict[str, Any]:
    """Summary row for one published human result (r and CI as published)."""
    d = cohens_d(bench.high.mean, bench.high.sd, bench.high.n, bench.low.mean, bench.low.sd, bench.low.n)
    return {
        "measure": bench.measure, "source": bench.source, "n_total": bench.n_total,
        "n_note": "cell n assumed", "r": bench.r_published,
        "r_ci_low": bench.r_ci_published[0], "r_ci_high": bench.r_ci_published[1],
        "d": d, "F": bench.f_value, "p_text": bench.p_text,
        "mean_high": bench.high.mean, "mean_low": bench.low.mean,
        "sd_high": bench.high.sd, "sd_low": bench.low.sd,
        "scale": f"{bench.scale_min}-{bench.scale_max}",
    }


def comparison_table(anova: pd.DataFrame, alpha: float, ai_label: str = "ai") -> pd.DataFrame:
    """STEP 4: r with CI for original, replication and AI, plus Fisher-z tests.

    One row per (measure, source). AI rows carry the Fisher-z test against
    each human source, and the ratio of AI to human SD (spread), where the
    scales match. Mood has no published human r, so only the AI row appears.
    """
    rows: list[dict[str, Any]] = []
    for _, ai in anova.iterrows():
        measure = ai["measure"]
        for source in ("original", "replication"):
            bench = BENCHMARKS[source].get(measure)
            if bench is not None:
                rows.append(human_row(bench))
        ai_row = {
            "measure": measure, "source": ai_label, "n_total": ai.get("n_total", np.nan),
            "n_note": "", "r": ai.get("r", np.nan), "r_ci_low": ai.get("r_ci_low", np.nan),
            "r_ci_high": ai.get("r_ci_high", np.nan), "d": ai.get("d", np.nan), "F": ai.get("F", np.nan),
            "p": ai.get("p", np.nan), "mean_high": ai.get("mean_high", np.nan),
            "mean_low": ai.get("mean_low", np.nan), "sd_high": ai.get("sd_high", np.nan),
            "sd_low": ai.get("sd_low", np.nan),
            "scale": "10-20" if measure == "size" else ("1-7" if measure == "attention" else "1-9"),
        }
        for source in ("original", "replication"):
            bench = BENCHMARKS[source].get(measure)
            if bench is None:
                continue
            z, p = fisher_z_compare(ai_row["r"], int(ai_row["n_total"]) if pd.notna(ai_row["n_total"]) else 0,
                                    bench.r_published, bench.n_total)
            ai_row[f"z_vs_{source}"] = z
            ai_row[f"p_vs_{source}"] = p
            ai_row[f"differs_from_{source}"] = bool(pd.notna(p) and p < alpha)
            comparable = not (source == "replication" and measure == "arousal")
            human_sd = (bench.high.sd + bench.low.sd) / 2
            ai_sd = np.nanmean([ai_row["sd_high"], ai_row["sd_low"]])
            ai_row[f"sd_ratio_vs_{source}"] = ai_sd / human_sd if comparable else np.nan
        rows.append(ai_row)
    return pd.DataFrame(rows)


def plain_reading(comparison: pd.DataFrame, anova: pd.DataFrame, alpha: float) -> pd.DataFrame:
    """Plain-English answers to: same direction? similar magnitude? statistical evidence?

    "Similar magnitude" means the Fisher-z test cannot reject equal r. With
    small samples that is weak evidence of similarity, so the reading says so.
    """
    rows = []
    for measure in EFFECT_MEASURES:
        ai = anova.set_index("measure").loc[measure]
        ai_cmp = comparison[(comparison.measure == measure) & (comparison.source == "ai")].iloc[0]
        r_ai = ai.get("r", np.nan)
        if pd.isna(r_ai):
            direction = "undefined (zero variance)"
        elif r_ai > 0:
            direction = "yes (high > low, as in both human studies)"
        elif r_ai < 0:
            direction = "no (high < low, the opposite of the humans)"
        else:
            direction = "no difference at all"
        magnitude_parts = []
        for source in ("original", "replication"):
            p = ai_cmp.get(f"p_vs_{source}", np.nan)
            if pd.isna(p):
                magnitude_parts.append(f"vs {source}: cannot test")
            elif p < alpha:
                bigger = "larger" if ai_cmp[f"z_vs_{source}"] > 0 else "smaller"
                magnitude_parts.append(f"vs {source}: AI effect significantly {bigger} (p = {p:.3f})")
            else:
                magnitude_parts.append(f"vs {source}: not significantly different (p = {p:.3f})")
        p_ai = ai.get("p", np.nan)
        evidence = ("undefined (zero variance)" if pd.isna(p_ai)
                    else f"{'yes' if p_ai < alpha else 'no'}: F = {ai['F']:.2f}, p = {p_ai:.3f}")
        rows.append({"measure": measure, "same_direction": direction,
                     "similar_magnitude": "; ".join(magnitude_parts), "ai_effect_significant": evidence})
    return pd.DataFrame(rows)


# ==========================================================================
# STEP 5: TOST equivalence for the size effect
# ==========================================================================

def tost(high: np.ndarray, low: np.ndarray, bound: float, alpha: float) -> dict[str, Any]:
    """Two one-sided t-tests: is the high-low difference inside +/- bound?

    Equivalent (practically no effect) if BOTH one-sided tests reject, i.e.
    p_tost = max(p_lower, p_upper) < alpha. Same as the 90% CI of the
    difference lying entirely inside (-bound, +bound).
    Why this exists: "not significant" is not the same as "no effect". TOST
    separates a true null from a sample too noisy to tell.
    """
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    n_1, n_2 = len(high), len(low)
    result: dict[str, Any] = {"bound": bound, "alpha": alpha, "n_high": n_1, "n_low": n_2}
    if n_1 < 2 or n_2 < 2:
        result.update(conclusion="not computable (fewer than 2 answers in a condition)", equivalent=None)
        return result
    diff = high.mean() - low.mean()
    df_error = n_1 + n_2 - 2
    spread = math.sqrt(((n_1 - 1) * high.var(ddof=1) + (n_2 - 1) * low.var(ddof=1)) / df_error)
    se = spread * math.sqrt(1 / n_1 + 1 / n_2)
    result.update(diff=diff, se=se, df=df_error)
    if se == 0:
        result.update(p_lower=np.nan, p_upper=np.nan, p_tost=np.nan, ci90_low=np.nan, ci90_high=np.nan,
                      equivalent=None,
                      conclusion=(f"undefined: zero variance (difference = {diff:.2f} in). "
                                  "Report the collapse itself rather than a test"))
        return result
    t_lower = (diff + bound) / se            # H0: diff <= -bound
    t_upper = (diff - bound) / se            # H0: diff >= +bound
    p_lower = stats.t.sf(t_lower, df_error)
    p_upper = stats.t.cdf(t_upper, df_error)
    p_tost = max(p_lower, p_upper)
    t_90 = stats.t.ppf(1 - alpha, df_error)
    equivalent = bool(p_tost < alpha)
    result.update(
        t_lower=t_lower, t_upper=t_upper, p_lower=p_lower, p_upper=p_upper, p_tost=p_tost,
        ci90_low=diff - t_90 * se, ci90_high=diff + t_90 * se, equivalent=equivalent,
        conclusion=(f"equivalent to zero within +/-{bound} in (p = {p_tost:.3f})" if equivalent
                    else f"NOT shown to be equivalent within +/-{bound} in (p = {p_tost:.3f}); "
                         "the data cannot rule out an effect of that size"),
    )
    return result


# ==========================================================================
# STEP 6-7: mood placebo and outcome label
# ==========================================================================

def mood_placebo(anova: pd.DataFrame) -> dict[str, Any]:
    """STEP 6: humans showed no mood difference (5.43 vs 5.49, p > .87).

    A significant AI mood difference suggests a halo response ("vivid makes
    everything higher") rather than a perceptual effect.
    """
    mood = anova.set_index("measure").loc["mood"]
    differs = bool(mood.get("significant", False))
    if mood.get("zero_variance", False):
        reading = "Undefined: every agent gave the same mood answer, so the placebo check cannot be run"
    elif differs:
        reading = "AI mood DIFFERS by condition: possible halo response (placebo check failed)"
    else:
        reading = "No AI mood difference, as in the original (placebo check passed)"
    return {
        "ai_mean_high": mood.get("mean_high", np.nan), "ai_mean_low": mood.get("mean_low", np.nan),
        "ai_p": mood.get("p", np.nan), "ai_r": mood.get("r", np.nan),
        "human_means_order_assumed": (MOOD_ORIGINAL["mean_high_assumed"], MOOD_ORIGINAL["mean_low_assumed"]),
        "human_p_text": MOOD_ORIGINAL["p_text"], "differs": differs, "reading": reading,
    }


def classify_outcome(anova: pd.DataFrame, comparison: pd.DataFrame, alpha: float) -> dict[str, Any]:
    """STEP 7: label the AI result A, B, C, D or Mixed, and say why.

    Rules, checked in this order:
      D  mood differs significantly (halo), OR any AI effect on size,
         attention or arousal is significantly LARGER than the original's
         (Fisher-z), i.e. exaggerated.
      A  size, attention and arousal all significantly higher for high.
      B  attention and arousal significantly higher; size not significant.
      C  none of size, attention, arousal significant.
      Mixed  anything else (e.g. size only, or an effect in the wrong direction).
    """
    by_measure = anova.set_index("measure")
    reasons: list[str] = []

    def up(measure: str) -> bool:
        row = by_measure.loc[measure]
        return bool(row.get("significant", False) and row.get("r", 0) > 0)

    def any_sig(measure: str) -> bool:
        return bool(by_measure.loc[measure].get("significant", False))

    for measure in EFFECT_MEASURES:
        row = by_measure.loc[measure]
        if row.get("zero_variance", False):
            reasons.append(f"{measure}: zero variance, no test possible")
        elif pd.notna(row.get("p")):
            reasons.append(f"{measure}: r = {row['r']:+.3f}, p = {row['p']:.3f}"
                           f"{' (significant)' if row['significant'] else ''}")

    mood_differs = any_sig("mood")
    ai_rows = comparison[comparison.source == "ai"].set_index("measure")
    exaggerated = [m for m in EFFECT_MEASURES
                   if ai_rows.loc[m].get("differs_from_original", False) and ai_rows.loc[m].get("z_vs_original", 0) > 0]
    if mood_differs:
        reasons.append("mood differs between conditions (humans: no difference)")
    for m in exaggerated:
        reasons.append(f"{m}: AI effect significantly larger than the original's")

    if mood_differs or exaggerated:
        label = "D"
    elif up("size") and up("attention") and up("arousal"):
        label = "A"
    elif up("attention") and up("arousal") and not any_sig("size"):
        label = "B"
    elif not any(any_sig(m) for m in EFFECT_MEASURES):
        label = "C"
    else:
        label = "Mixed"
    return {"label": label, "name": OUTCOME_NAMES[label], "reasons": reasons}


# ==========================================================================
# STEP 8: conditional serial mediation (original's PROCESS model 6 structure)
# ==========================================================================

def _ols_coefficients(y: np.ndarray, predictors: list[np.ndarray]) -> np.ndarray:
    """Least-squares coefficients for y ~ intercept + predictors (intercept first)."""
    design = np.column_stack([np.ones(len(y))] + predictors)
    coefficients, *_ = np.linalg.lstsq(design, y, rcond=None)
    return coefficients


def _serial_paths(x: np.ndarray, m1: np.ndarray, m2: np.ndarray, y: np.ndarray) -> dict[str, float]:
    """Path estimates for X -> M1 -> M2 -> Y (PROCESS model 6 structure).

    a1: X->M1; a2: X->M2 (controlling M1); d21: M1->M2;
    b1: M1->Y, b2: M2->Y, c_prime: X->Y (all controlling each other).
    """
    _, a1 = _ols_coefficients(m1, [x])
    _, a2, d21 = _ols_coefficients(m2, [x, m1])
    _, c_prime, b1, b2 = _ols_coefficients(y, [x, m1, m2])
    ind_m1 = a1 * b1
    ind_both = a1 * d21 * b2
    ind_m2 = a2 * b2
    return {"a1": a1, "a2": a2, "d21": d21, "b1": b1, "b2": b2, "c_prime": c_prime,
            "indirect_via_arousal_only": ind_m1, "indirect_via_both": ind_both,
            "indirect_via_attention_only": ind_m2, "total_indirect": ind_m1 + ind_both + ind_m2}


def serial_mediation(frame: pd.DataFrame, n_boot: int, seed: int) -> dict[str, Any]:
    """Saturation -> arousal -> attention -> size, with percentile bootstrap 95% CIs.

    Same structure as the original's PROCESS model 6 (high saturation = 1).
    """
    valid = valid_rows(frame).dropna(subset=["screen_size", "attention", "arousal"])
    x = (valid["condition"] == "high").astype(float).to_numpy()
    m1 = valid["arousal"].to_numpy(float)
    m2 = valid["attention"].to_numpy(float)
    y = valid["screen_size"].to_numpy(float)
    point = _serial_paths(x, m1, m2, y)
    rng = np.random.default_rng(seed)
    keys = ["indirect_via_arousal_only", "indirect_via_both", "indirect_via_attention_only", "total_indirect"]
    draws = {k: np.empty(n_boot) for k in keys}
    n = len(y)
    for i in range(n_boot):
        idx = rng.integers(0, n, n)
        paths = _serial_paths(x[idx], m1[idx], m2[idx], y[idx])
        for k in keys:
            draws[k][i] = paths[k]
    cis = {k: (float(np.percentile(draws[k], 2.5)), float(np.percentile(draws[k], 97.5))) for k in keys}
    return {"ran": True, "n": n, "bootstrap_samples": n_boot, "seed": seed, "paths": point, "ci95": cis,
            "total_indirect_significant": bool(cis["total_indirect"][0] > 0 or cis["total_indirect"][1] < 0)}


def mediation_if_warranted(frame: pd.DataFrame, anova: pd.DataFrame, config: Config) -> dict[str, Any]:
    """STEP 8: run mediation only if the AI size effect is significant and positive.

    This is the original study's own rule (and the replication's: it skipped
    mediation because its size effect failed).
    """
    size = anova.set_index("measure").loc["size"]
    if not (size.get("significant", False) and size.get("r", 0) > 0):
        why = ("zero variance in size answers" if size.get("zero_variance", False)
               else f"the AI size effect was not significant and positive (p = {size.get('p', float('nan')):.3f})")
        return {"ran": False, "reason": f"Skipped: {why}. Following the original study's rule (as the "
                                        "replication did), mediation is tested only when the size effect appears."}
    for measure in ("attention", "arousal"):
        if anova.set_index("measure").loc[measure].get("zero_variance", False):
            return {"ran": False, "reason": f"Skipped: {measure} has zero variance, so it cannot mediate."}
    return serial_mediation(frame, config.mediation_bootstrap_samples, config.seed)


# ==========================================================================
# Everything together
# ==========================================================================

@dataclass
class AnalysisResult:
    """All outputs of analyze(). Tables are pandas DataFrames; the rest are dictionaries."""

    quality: dict[str, Any]
    descriptives: pd.DataFrame
    anova: pd.DataFrame
    comparison: pd.DataFrame
    reading: pd.DataFrame
    tost_size: dict[str, Any]
    mood: dict[str, Any]
    outcome: dict[str, Any]
    mediation: dict[str, Any]
    settings: dict[str, Any] = field(default_factory=dict)


def analyze(frame: pd.DataFrame, config: Config) -> AnalysisResult:
    """Run STEPS 1 to 8 on one run's data and return everything.

    Inputs:  the run's data frame (load_results); the Config.
    Output:  AnalysisResult. Check result.quality["is_mock"] before reporting.
    """
    alpha = config.alpha
    quality = data_quality(frame)                                         # STEP 1
    descriptives = describe(frame)                                        # STEP 2
    anova = anova_table(frame, alpha)                                     # STEP 3
    comparison = comparison_table(anova, alpha)                           # STEP 4
    reading = plain_reading(comparison, anova, alpha)
    valid = valid_rows(frame)
    size_high = valid.loc[valid.condition == "high", "screen_size"].dropna().to_numpy()
    size_low = valid.loc[valid.condition == "low", "screen_size"].dropna().to_numpy()
    tost_size = tost(size_high, size_low, config.tost_bound_inches, alpha)  # STEP 5
    mood = mood_placebo(anova)                                            # STEP 6
    outcome = classify_outcome(anova, comparison, alpha)                  # STEP 7
    mediation = mediation_if_warranted(frame, anova, config)              # STEP 8
    return AnalysisResult(quality, descriptives, anova, comparison, reading, tost_size, mood, outcome,
                          mediation, settings={"alpha": alpha, "tost_bound_inches": config.tost_bound_inches})


def summary_lines(result: AnalysisResult) -> list[str]:
    """Short plain-English summary for the screen, the report draft and the dashboard."""
    q = result.quality
    lines = []
    if q["is_mock"]:
        lines.append("MOCK DATA, NOT RESULTS. These numbers come from a dry run and must not be reported.")
    lines.append(f"Agents: {q['n_agents']} ({q['n_valid']} valid, {q['n_invalid']} excluded); "
                 f"high {q['n_high_valid']}, low {q['n_low_valid']}; run label(s): {', '.join(q['run_labels'])}.")
    lines.append(f"Outcome {result.outcome['label']}: {result.outcome['name']}.")
    for _, row in result.anova.iterrows():
        if row.get("zero_variance"):
            lines.append(f"  {row['measure']}: {row['note']}.")
        elif pd.notna(row.get("p")):
            lines.append(f"  {row['measure']}: high {row['mean_high']:.2f} vs low {row['mean_low']:.2f}; "
                         f"F(1,{int(row['df_error'])}) = {row['F']:.2f}, p = {row['p']:.3f}, "
                         f"r = {row['r']:+.3f} [{row['r_ci_low']:+.3f}, {row['r_ci_high']:+.3f}], d = {row['d']:+.2f}.")
    lines.append(f"Size equivalence (TOST): {result.tost_size['conclusion']}.")
    lines.append(f"Mood placebo: {result.mood['reading']}.")
    lines.append("Mediation: " + (f"ran; total indirect effect B = {result.mediation['paths']['total_indirect']:.2f}, "
                                  f"95% CI [{result.mediation['ci95']['total_indirect'][0]:.2f}, "
                                  f"{result.mediation['ci95']['total_indirect'][1]:.2f}]."
                                  if result.mediation.get("ran") else result.mediation["reason"]))
    if q["zero_variance_flags"]:
        lines.append("Zero-variance warnings: " + "; ".join(q["zero_variance_flags"]) + ".")
    return lines
