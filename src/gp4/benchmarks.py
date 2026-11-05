"""
benchmarks.py: the human results the AI agents are compared against.

Where it fits
-------------
Reference data for STEP 8 (analysis). Nothing here is computed from AI data.
These are the published human numbers, typed in once, with sources.

Sources (all re-checked against the PDFs in brief/ on 2026-11-05)
-----------------------------------------------------------------
ORIGINAL:    Hagtvedt, H., and Brasel, S. A. (2017). Color saturation increases
             perceived product size. Journal of Consumer Research, 44(2), 396-413.
             Study 3, pp. 400-401 (procedure, results, mediation).
REPLICATION: Motoki, K., and Iseki, S. (2022). Frontiers in Communication,
             7:1048896. Results section "Hagtvedt and Brasel (2017)", and the
             summary table of effect sizes with 95% CIs. Scale details from the
             supplementary "Methodological Detail Appendix".

Important caveats (also shown on the dashboard)
-----------------------------------------------
1. Per-cell sample sizes are NOT reported in either paper. The splits below
   are ASSUMED (original 39 high / 38 low; replication 411 high / 412 low).
   Every place that uses them must say "assumed".
2. The replication measured AROUSAL ON A 7-POINT SCALE (1 = Very calm,
   7 = Very aroused), not the 9-point affect grid. Its arousal MEANS cannot be
   compared with AI means on a 1-9 scale. Compare effect sizes (r, d) only.
3. The original reports mood means without saying which is high and which is
   low ("M = 5.43 vs. M = 5.49, p > .87"). We record them as "order assumed
   high vs low" and use them only as a direction check, never in a test.
4. No raw human data exists for Group 1, so every comparison is at the level
   of these summary statistics.

What goes in and out
--------------------
In:  nothing (constants).
Out: ORIGINAL and REPLICATION dictionaries keyed by measure, plus mood,
     mediation and sample descriptions.
"""

from __future__ import annotations

from dataclasses import dataclass

# Measures in the order they were asked.
MEASURES: tuple[str, ...] = ("size", "attention", "arousal")


@dataclass(frozen=True)
class Cell:
    """Summary statistics for one condition (high or low saturation).

    n_assumed is True when n is our assumption, not a published number.
    """

    mean: float
    sd: float
    n: int
    n_assumed: bool = True


@dataclass(frozen=True)
class Benchmark:
    """One published human result for one measure.

    Fields:
      source        "original" or "replication"
      measure       "size", "attention" or "arousal"
      high, low     Cell statistics by condition
      f_value       published F statistic, df = (1, df_error)
      df_error      error degrees of freedom (n - 2)
      p_text        p-value as printed in the paper
      r_published   effect size r as published (replication paper's table)
      r_ci_published  95% CI for r as published (replication paper's table)
      eta_sq_published  partial eta-squared as printed
      scale_min, scale_max  response scale used by THAT study
      citation      where the numbers are printed
      note          anything the reader must know
    """

    source: str
    measure: str
    high: Cell
    low: Cell
    f_value: float
    df_error: int
    p_text: str
    r_published: float
    r_ci_published: tuple[float, float]
    eta_sq_published: float
    scale_min: int
    scale_max: int
    citation: str
    note: str = ""

    @property
    def n_total(self) -> int:
        """Total sample size (published)."""
        return self.df_error + 2


# --------------------------------------------------------------------------
# Original study: Hagtvedt and Brasel (2017), Study 3, n = 77
# --------------------------------------------------------------------------
_ORIG_CITE = "Hagtvedt and Brasel (2017), JCR 44(2), Study 3 results, p. 400"
_ORIG_CI_CITE = "95% CI for r from Motoki and Iseki (2022), summary table"

ORIGINAL: dict[str, Benchmark] = {
    "size": Benchmark(
        source="original", measure="size",
        high=Cell(mean=15.28, sd=1.26, n=39), low=Cell(mean=14.41, sd=1.59, n=38),
        f_value=7.13, df_error=75, p_text="p < .01",
        r_published=0.295, r_ci_published=(0.076, 0.487), eta_sq_published=0.09,
        scale_min=10, scale_max=20,
        citation=f"{_ORIG_CITE}; {_ORIG_CI_CITE}",
        note="Screen-size estimate in whole inches (10 to 20). Cell n assumed (39/38).",
    ),
    "attention": Benchmark(
        source="original", measure="attention",
        high=Cell(mean=5.19, sd=1.08, n=39), low=Cell(mean=4.66, sd=0.98, n=38),
        f_value=4.95, df_error=75, p_text="p < .05",
        r_published=0.249, r_ci_published=(0.026, 0.448), eta_sq_published=0.06,
        scale_min=1, scale_max=7,
        citation=f"{_ORIG_CITE}; {_ORIG_CI_CITE}",
        note="Mean of two 1-7 items; inter-item r = .60. Cell n assumed (39/38).",
    ),
    "arousal": Benchmark(
        source="original", measure="arousal",
        high=Cell(mean=6.05, sd=1.34, n=39), low=Cell(mean=5.14, sd=1.62, n=38),
        f_value=7.35, df_error=75, p_text="p < .01",
        r_published=0.299, r_ci_published=(0.080, 0.490), eta_sq_published=0.09,
        scale_min=1, scale_max=9,
        citation=f"Hagtvedt and Brasel (2017), JCR 44(2), Study 3 results, pp. 400-401; {_ORIG_CI_CITE}",
        note="Affect grid arousal, 9-point. Cell n assumed (39/38).",
    ),
}

# --------------------------------------------------------------------------
# Replication: Motoki and Iseki (2022), n = 823 (Japanese online adults)
# --------------------------------------------------------------------------
_REP_CITE = "Motoki and Iseki (2022), Frontiers in Communication 7:1048896, Results and summary table"

REPLICATION: dict[str, Benchmark] = {
    "size": Benchmark(
        source="replication", measure="size",
        high=Cell(mean=15.46, sd=1.94, n=411), low=Cell(mean=15.42, sd=1.84, n=412),
        f_value=0.095, df_error=821, p_text="p = .758",
        r_published=0.011, r_ci_published=(-0.058, 0.079), eta_sq_published=0.000,
        scale_min=10, scale_max=20,
        citation=_REP_CITE,
        note="Size effect NOT replicated. Cell n assumed (411/412).",
    ),
    "attention": Benchmark(
        source="replication", measure="attention",
        high=Cell(mean=5.30, sd=1.07, n=411), low=Cell(mean=4.75, sd=1.14, n=412),
        f_value=49.238, df_error=821, p_text="p < .001",
        r_published=0.238, r_ci_published=(0.172, 0.301), eta_sq_published=0.057,
        scale_min=1, scale_max=7,
        citation=_REP_CITE,
        note="Replicated. Cell n assumed (411/412).",
    ),
    "arousal": Benchmark(
        source="replication", measure="arousal",
        high=Cell(mean=5.83, sd=1.10, n=411), low=Cell(mean=5.41, sd=1.20, n=412),
        f_value=27.539, df_error=821, p_text="p < .001",
        r_published=0.180, r_ci_published=(0.113, 0.245), eta_sq_published=0.033,
        scale_min=1, scale_max=7,
        citation=f"{_REP_CITE}; 7-point scale per supplementary Methodological Detail Appendix",
        note=(
            "Replicated. MEASURED ON A 7-POINT SCALE (1 = Very calm, 7 = Very aroused): "
            "do not compare these means with 1-9 answers; compare r and d only. "
            "Published partial eta-squared .033; F gives .0325. Cell n assumed (411/412)."
        ),
    ),
}

BENCHMARKS: dict[str, dict[str, Benchmark]] = {"original": ORIGINAL, "replication": REPLICATION}

# --------------------------------------------------------------------------
# Mood (placebo check): original only
# --------------------------------------------------------------------------
MOOD_ORIGINAL: dict[str, object] = {
    "mean_high_assumed": 5.43,
    "mean_low_assumed": 5.49,
    "sd": None,  # not reported
    "p_text": "p > .87",
    "order_assumed": True,
    "scale_min": 1,
    "scale_max": 9,
    "citation": "Hagtvedt and Brasel (2017), JCR 44(2), Study 3 procedure, p. 400",
    "note": (
        "No difference expected or found. The paper does not say which mean belongs to "
        "which condition; we assume high then low. Direction check only, no test."
    ),
}
MOOD_REPLICATION_REPORTED: bool = False

# --------------------------------------------------------------------------
# Mediation: original only (replication skipped it because size failed)
# --------------------------------------------------------------------------
MEDIATION_ORIGINAL: dict[str, object] = {
    "model": "PROCESS model 6 (serial mediation), 10,000 bootstrap resamples",
    "path": "saturation -> arousal -> attention -> size estimate",
    "total_indirect_B": 0.53,
    "total_indirect_SE": 0.21,
    "total_indirect_CI95": (0.16, 1.01),
    "direct_B": 0.34,
    "direct_CI95": (-0.22, 0.90),
    "indirect_via_both_B": 0.14,
    "indirect_via_both_CI95": (0.03, 0.36),
    "citation": "Hagtvedt and Brasel (2017), JCR 44(2), Study 3 mediation, p. 401",
    "note": (
        "Appendix E reverses the order (attention before arousal) and gets the same total "
        "indirect effect (B = .53, 95% CI [.16, 1.02]). The replication skipped mediation "
        "because its size effect was not significant."
    ),
}

# --------------------------------------------------------------------------
# Samples and settings (for DEVIATIONS.md and the dashboard)
# --------------------------------------------------------------------------
SAMPLES: dict[str, dict[str, object]] = {
    "original": {
        "n_analysed": 77,
        "n_recruited": 80,
        "who": "Undergraduates (49% male)",
        "setting": (
            "Group session; red laptop image projected on a large screen; paper "
            "questionnaire; about $1 of snacks as payment"
        ),
        "stimulus_colour": "Red, HSV hue 356, value 70; saturation 100 (high) vs 50 (low); Appendix B",
        "citation": "Hagtvedt and Brasel (2017), Study 3 procedure, p. 400",
    },
    "replication": {
        "n_analysed": 823,
        "n_recruited": 1070,
        "who": "Japanese online adults via Crowdworks (mean age 40.8; 428 male, 391 female, 4 not stated)",
        "setting": (
            "Online Qualtrics survey in Japanese; 10 studies per person in random order "
            "(about 10 minutes in total); instructional manipulation check and attention "
            "check exclusions (1,070 to 823); pre-registered"
        ),
        "citation": "Motoki and Iseki (2022), Method; supplementary Methodological Detail Appendix",
    },
}
