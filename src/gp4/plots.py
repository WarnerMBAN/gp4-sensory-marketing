"""
plots.py: every figure, in two versions (Plotly for the dashboard, Matplotlib for the report).

Where it fits
-------------
STEP 9 of the pipeline. Takes a run's data frame and its AnalysisResult
(analysis.analyze) and draws the figures. The dashboard calls the *_plotly
functions; scripts/analyze.py calls save_report_figures() for PNG files.

Figures
-------
1. distribution_*   answers by condition for one measure: box plus every
                    agent as a point, with the human means as labelled lines.
2. size_histogram_* share of agents choosing each screen size (10-20 in).
3. forest_*         effect size r with 95% CI: original, replication and AI,
                    for each measure (the key human-AI comparison figure).

Colour rules (validated with the dataviz palette checker, 2026-11-05)
---------------------------------------------------------------------
* Conditions: high = red #e34948 (circles), low = violet #6250d6
  (triangles, hatched bars). Passes colour-blind and contrast checks.
* Sources: original = blue #2a78d6 (squares), replication = orange #eb6834
  (diamonds), AI = aqua #1baf7a (circles). Passes all-pairs checks; aqua is
  low-contrast on white, so every forest-plot value is printed as text.
* The two sets never share a chart (red and orange are too close). Human
  means on distribution charts are dark neutral lines with text labels.
* Meaning never rests on colour alone: shapes, hatching, axis labels and
  direct labels repeat it.
* Mock data: every title starts with "MOCK DATA, NOT RESULTS".
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # draw to files, no window (works on servers too)
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402

from gp4.analysis import MEASURE_COLUMNS, MEASURE_LABELS, AnalysisResult, valid_rows  # noqa: E402
from gp4.benchmarks import MOOD_ORIGINAL, ORIGINAL, REPLICATION  # noqa: E402

# --------------------------------------------------------------------------
# Visual identity (one place; used by every chart and the dashboard)
# --------------------------------------------------------------------------
COLORS: dict[str, str] = {
    "high": "#e34948",
    "low": "#6250d6",
    "original": "#2a78d6",
    "replication": "#eb6834",
    "ai": "#1baf7a",
}
CONDITION_LABELS: dict[str, str] = {"high": "High saturation", "low": "Low saturation"}
SOURCE_LABELS: dict[str, str] = {"original": "Original (n = 77)", "replication": "Replication (n = 823)",
                                 "ai": "AI agents"}
PLOTLY_SYMBOLS: dict[str, str] = {"high": "circle", "low": "triangle-up", "original": "square",
                                  "replication": "diamond", "ai": "circle"}
MPL_MARKERS: dict[str, str] = {"high": "o", "low": "^", "original": "s", "replication": "D", "ai": "o"}
INK = "#0b0b0b"          # primary text
INK_SECONDARY = "#52514e"
GRID = "#e6e5e1"
SURFACE = "#fcfcfb"
MOCK_PREFIX = "MOCK DATA, NOT RESULTS: "
MEASURE_SHORT: dict[str, str] = {"size": "Screen size", "attention": "Attention", "arousal": "Arousal",
                                 "mood": "Mood (placebo)"}

# One-line "what this shows" captions (dashboard and report).
CAPTIONS: dict[str, str] = {
    "distribution": ("Each dot is one AI agent's answer; the box shows the middle half of answers and the "
                     "median. Dark lines mark the human group means for comparison."),
    "size_histogram": ("Share of agents in each condition who chose each screen size. Bunching on one or two "
                       "values means the model's answers have collapsed."),
    "forest": ("Effect of high vs low saturation as r, with 95% confidence intervals. Right of zero means "
               "higher ratings for the more saturated laptop. Overlapping intervals suggest similar effects."),
}


def _title(text: str, is_mock: bool) -> str:
    """Prefix the title with a mock warning when the data are from a dry run."""
    return (MOCK_PREFIX + text) if is_mock else text


def _human_means(measure: str) -> list[dict[str, Any]]:
    """Human group means to draw on a distribution chart, where the scale matches the AI's.

    Replication arousal is excluded: it used a 7-point scale.
    """
    marks: list[dict[str, Any]] = []
    if measure == "mood":
        marks.append({"source": "Original (order assumed)", "high": MOOD_ORIGINAL["mean_high_assumed"],
                      "low": MOOD_ORIGINAL["mean_low_assumed"], "dash": "solid"})
        return marks
    if measure in ORIGINAL:
        b = ORIGINAL[measure]
        marks.append({"source": "Original", "high": b.high.mean, "low": b.low.mean, "dash": "solid"})
    if measure in REPLICATION and measure != "arousal":
        b = REPLICATION[measure]
        marks.append({"source": "Replication", "high": b.high.mean, "low": b.low.mean, "dash": "dot"})
    return marks


def _axis_range(measure: str) -> tuple[float, float]:
    """The full response scale, padded slightly, so charts never exaggerate small gaps."""
    low, high = {"size": (10, 20), "attention": (1, 7), "arousal": (1, 9), "mood": (1, 9)}[measure]
    return low - 0.5, high + 0.5


# ==========================================================================
# 1. Distribution by condition
# ==========================================================================

def distribution_plotly(frame: pd.DataFrame, measure: str, is_mock: bool) -> go.Figure:
    """Box plus every agent's answer, by condition, with human means as styled lines (in the legend)."""
    valid = valid_rows(frame)
    column = MEASURE_COLUMNS[measure]
    fig = go.Figure()
    for position, condition in enumerate(("high", "low")):
        values = valid.loc[valid.condition == condition, column].dropna()
        fig.add_trace(go.Box(
            y=values, x=[position] * len(values), name=f"{CONDITION_LABELS[condition]} (n = {len(values)})",
            boxpoints="all", jitter=0.45, pointpos=0, width=0.5, line={"color": COLORS[condition], "width": 2},
            fillcolor="rgba(0,0,0,0)",
            marker={"color": COLORS[condition], "symbol": PLOTLY_SYMBOLS[condition], "size": 8,
                    "line": {"color": SURFACE, "width": 1}},
            hovertemplate=f"{CONDITION_LABELS[condition]}<br>answer %{{y}}<extra></extra>",
        ))
    for mark in _human_means(measure):
        xs: list[float | None] = []
        ys: list[float | None] = []
        for position, condition in enumerate(("high", "low")):
            xs += [position - 0.38, position + 0.38, None]
            ys += [mark[condition], mark[condition], None]
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="lines", name=f"{mark['source']} human mean",
            line={"color": INK_SECONDARY, "width": 2.5, "dash": mark["dash"]},
            hovertemplate=f"{mark['source']} human mean: %{{y:.2f}}<extra></extra>",
        ))
    fig.update_layout(
        title=_title(f"{MEASURE_SHORT[measure]}: AI answers by condition", is_mock),
        yaxis={"title": MEASURE_LABELS[measure], "range": _axis_range(measure), "gridcolor": GRID},
        xaxis={"title": "Condition (each agent saw one image)", "tickvals": [0, 1],
               "ticktext": [CONDITION_LABELS["high"], CONDITION_LABELS["low"]], "range": [-0.6, 1.6]},
        showlegend=True, legend={"orientation": "h", "y": -0.25},
        plot_bgcolor=SURFACE, paper_bgcolor=SURFACE, font={"color": INK},
    )
    return fig


def distribution_mpl(frame: pd.DataFrame, measure: str, is_mock: bool) -> plt.Figure:
    """Matplotlib version of distribution_plotly (for the report)."""
    valid = valid_rows(frame)
    column = MEASURE_COLUMNS[measure]
    fig, ax = plt.subplots(figsize=(6.4, 4.8), facecolor=SURFACE)
    rng = np.random.default_rng(0)  # fixed jitter so the PNG is reproducible
    for position, condition in enumerate(("high", "low")):
        values = valid.loc[valid.condition == condition, column].dropna().to_numpy()
        if len(values):
            ax.boxplot(values, positions=[position], widths=0.5, showfliers=False,
                       boxprops={"color": COLORS[condition], "linewidth": 1.5},
                       medianprops={"color": COLORS[condition], "linewidth": 2},
                       whiskerprops={"color": COLORS[condition]}, capprops={"color": COLORS[condition]})
            ax.scatter(position + rng.uniform(-0.18, 0.18, len(values)), values, s=26,
                       marker=MPL_MARKERS[condition], color=COLORS[condition], edgecolor=SURFACE,
                       linewidth=0.6, zorder=3, label=f"{CONDITION_LABELS[condition]} (n = {len(values)})")
    for mark in _human_means(measure):
        style = "-" if mark["dash"] == "solid" else ":"
        for position, condition in enumerate(("high", "low")):
            ax.hlines(mark[condition], position - 0.32, position + 0.32, colors=INK_SECONDARY, linestyles=style,
                      lw=2, zorder=2, label=f"{mark['source']} human mean" if position == 0 else None)
    ax.set_xticks([0, 1], [CONDITION_LABELS["high"], CONDITION_LABELS["low"]])
    ax.set_xlim(-0.6, 1.6)
    ax.set_ylim(*_axis_range(measure))
    ax.set_ylabel(MEASURE_LABELS[measure])
    ax.set_xlabel("Condition (each agent saw one image)")
    ax.set_title(_title(f"{MEASURE_SHORT[measure]}: AI answers by condition", is_mock), fontsize=10,
                 color="#b00020" if is_mock else INK)
    _tidy_axes(ax)
    ax.legend(frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=2)
    fig.tight_layout()
    return fig


# ==========================================================================
# 2. Size histogram
# ==========================================================================

def _size_shares(frame: pd.DataFrame) -> pd.DataFrame:
    """Percentage of each condition's valid agents choosing each size 10-20."""
    valid = valid_rows(frame)
    sizes = list(range(10, 21))
    table = {}
    for condition in ("high", "low"):
        values = valid.loc[valid.condition == condition, "screen_size"].dropna().astype(int)
        counts = values.value_counts().reindex(sizes, fill_value=0)
        table[condition] = 100 * counts / max(len(values), 1)
    return pd.DataFrame(table, index=sizes)


def size_histogram_plotly(frame: pd.DataFrame, is_mock: bool) -> go.Figure:
    """Grouped bars: share of agents choosing each screen size, by condition."""
    shares = _size_shares(frame)
    fig = go.Figure()
    for condition, pattern in (("high", ""), ("low", "/")):
        fig.add_trace(go.Bar(
            x=shares.index, y=shares[condition], name=CONDITION_LABELS[condition],
            marker={"color": COLORS[condition], "pattern": {"shape": pattern, "fgcolor": SURFACE},
                    "line": {"color": SURFACE, "width": 2}},
            hovertemplate=f"{CONDITION_LABELS[condition]}<br>%{{x}} in: %{{y:.1f}}% of agents<extra></extra>",
        ))
    fig.update_layout(
        title=_title("Screen-size answers by condition", is_mock),
        xaxis={"title": "Estimated screen size (inches)", "dtick": 1, "range": [9.5, 20.5]},
        yaxis={"title": "Share of agents in the condition (%)", "gridcolor": GRID, "rangemode": "tozero"},
        barmode="group", bargap=0.25, bargroupgap=0.08, legend={"orientation": "h", "y": -0.22},
        plot_bgcolor=SURFACE, paper_bgcolor=SURFACE, font={"color": INK},
    )
    return fig


def size_histogram_mpl(frame: pd.DataFrame, is_mock: bool) -> plt.Figure:
    """Matplotlib version of size_histogram_plotly."""
    shares = _size_shares(frame)
    fig, ax = plt.subplots(figsize=(6.4, 3.6), facecolor=SURFACE)
    width = 0.38
    for offset, condition, hatch in ((-width / 2, "high", None), (width / 2, "low", "///")):
        ax.bar(shares.index + offset, shares[condition], width=width - 0.04, color=COLORS[condition],
               hatch=hatch, edgecolor=SURFACE, linewidth=0.8, label=CONDITION_LABELS[condition])
    ax.set_xticks(range(10, 21))
    ax.set_xlabel("Estimated screen size (inches)")
    ax.set_ylabel("Share of agents in the condition (%)")
    ax.set_title(_title("Screen-size answers by condition", is_mock), fontsize=10,
                 color="#b00020" if is_mock else INK)
    _tidy_axes(ax)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    return fig


# ==========================================================================
# 3. Forest plot of r: original vs replication vs AI
# ==========================================================================

FOREST_MEASURES: tuple[str, ...] = ("size", "attention", "arousal", "mood")
FOREST_OFFSETS: dict[str, float] = {"original": -0.25, "replication": 0.0, "ai": 0.25}


def _forest_rows(comparison: pd.DataFrame) -> pd.DataFrame:
    """Rows for the forest plot, with a y position for each (measure, source)."""
    rows = comparison[comparison.measure.isin(FOREST_MEASURES)].copy()
    order = {m: i for i, m in enumerate(FOREST_MEASURES)}
    rows["y"] = rows.apply(lambda r: order[r.measure] + FOREST_OFFSETS[r.source], axis=1)
    return rows


def _value_label(row: pd.Series) -> str:
    """Text printed beside each point: r and its CI (or why there is none)."""
    if pd.isna(row["r"]):
        return "undefined (zero variance)"
    if pd.isna(row["r_ci_low"]):
        return f"{row['r']:+.2f} (no CI)"
    return f"{row['r']:+.2f} [{row['r_ci_low']:+.2f}, {row['r_ci_high']:+.2f}]"


def forest_plotly(comparison: pd.DataFrame, is_mock: bool, ai_label: str = "AI agents") -> go.Figure:
    """Effect size r with 95% CI for each source and measure."""
    rows = _forest_rows(comparison)
    fig = go.Figure()
    for source in ("original", "replication", "ai"):
        part = rows[rows.source == source]
        has_ci = part.r_ci_low.notna()
        fig.add_trace(go.Scatter(
            x=part.r, y=part.y, mode="markers+text", name=SOURCE_LABELS[source] if source != "ai" else ai_label,
            marker={"color": COLORS[source], "symbol": PLOTLY_SYMBOLS[source], "size": 11,
                    "line": {"color": SURFACE, "width": 2}},
            error_x={"type": "data", "symmetric": False, "array": np.where(has_ci, part.r_ci_high - part.r, 0),
                     "arrayminus": np.where(has_ci, part.r - part.r_ci_low, 0), "color": COLORS[source],
                     "thickness": 2, "width": 0},
            text=[_value_label(r) for _, r in part.iterrows()], textposition="middle right",
            textfont={"size": 11, "color": INK_SECONDARY},
            hovertemplate="%{text}<extra>" + SOURCE_LABELS.get(source, source) + "</extra>",
        ))
    fig.add_vline(x=0, line={"color": INK_SECONDARY, "width": 1})
    fig.add_annotation(x=0.02, y=len(FOREST_MEASURES) - 0.45, xref="x", text="Mood: no human r published (p > .87)",
                       showarrow=False, xanchor="left", font={"size": 10, "color": INK_SECONDARY})
    fig.update_layout(
        title=_title("Saturation effect (r, 95% CI): humans vs AI", is_mock),
        xaxis={"title": "Effect size r (positive = higher for high saturation)", "range": [-0.6, 1.25],
               "gridcolor": GRID, "zeroline": False},
        yaxis={"tickvals": list(range(len(FOREST_MEASURES))), "ticktext": [m.capitalize() for m in FOREST_MEASURES],
               "autorange": "reversed", "title": ""},
        legend={"orientation": "h", "y": -0.18}, plot_bgcolor=SURFACE, paper_bgcolor=SURFACE,
        font={"color": INK}, height=520,
    )
    return fig


def forest_mpl(comparison: pd.DataFrame, is_mock: bool, ai_label: str = "AI agents") -> plt.Figure:
    """Matplotlib version of forest_plotly."""
    rows = _forest_rows(comparison)
    fig, ax = plt.subplots(figsize=(7.2, 5.0), facecolor=SURFACE)
    for source in ("original", "replication", "ai"):
        part = rows[rows.source == source]
        for _, row in part.iterrows():
            if pd.notna(row.r_ci_low):
                ax.hlines(row.y, row.r_ci_low, row.r_ci_high, color=COLORS[source], lw=2)
            if pd.notna(row.r):
                ax.plot(row.r, row.y, MPL_MARKERS[source], color=COLORS[source], ms=7, mec=SURFACE, mew=1.2)
            x_text = row.r_ci_high if pd.notna(row.r_ci_high) else (row.r if pd.notna(row.r) else 0)
            ax.text(x_text + 0.03, row.y, _value_label(row), va="center", fontsize=7.5, color=INK_SECONDARY)
        ax.plot([], [], MPL_MARKERS[source], color=COLORS[source],
                label=SOURCE_LABELS[source] if source != "ai" else ai_label)
    ax.axvline(0, color=INK_SECONDARY, lw=1)
    ax.text(0.02, len(FOREST_MEASURES) - 1 - 0.42, "Mood: no human r published (p > .87)", fontsize=7.5,
            color=INK_SECONDARY)
    ax.set_yticks(range(len(FOREST_MEASURES)), [m.capitalize() for m in FOREST_MEASURES])
    ax.set_ylim(len(FOREST_MEASURES) - 0.5, -0.5)
    ax.set_xlim(-0.6, 1.25)
    ax.set_xlabel("Effect size r (positive = higher for high saturation)")
    ax.set_title(_title("Saturation effect (r, 95% CI): humans vs AI", is_mock), fontsize=10,
                 color="#b00020" if is_mock else INK)
    _tidy_axes(ax)
    ax.legend(frameon=False, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=3)
    fig.tight_layout()
    return fig


# ==========================================================================
# Shared styling and saving
# ==========================================================================

def _tidy_axes(ax: plt.Axes) -> None:
    """Recessive grid and spines, readable ticks."""
    ax.set_facecolor(SURFACE)
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK_SECONDARY)
    ax.tick_params(colors=INK_SECONDARY, labelsize=8)
    ax.xaxis.label.set_color(INK)
    ax.yaxis.label.set_color(INK)


def save_report_figures(frame: pd.DataFrame, result: AnalysisResult, out_dir: Path, stem: str) -> list[Path]:
    """Save every report figure as a PNG (200 dpi). Returns the file paths.

    File names: <stem>_fig1_size_distribution.png, _fig2_effect_sizes.png,
    _fig3_size_histogram.png, _fig4_attention_distribution.png,
    _fig5_arousal_distribution.png, _fig6_mood_distribution.png.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    is_mock = result.quality["is_mock"]
    figures = {
        "fig1_size_distribution": distribution_mpl(frame, "size", is_mock),
        "fig2_effect_sizes": forest_mpl(result.comparison, is_mock),
        "fig3_size_histogram": size_histogram_mpl(frame, is_mock),
        "fig4_attention_distribution": distribution_mpl(frame, "attention", is_mock),
        "fig5_arousal_distribution": distribution_mpl(frame, "arousal", is_mock),
        "fig6_mood_distribution": distribution_mpl(frame, "mood", is_mock),
    }
    paths = []
    for name, fig in figures.items():
        path = out_dir / f"{stem}_{name}.png"
        fig.savefig(path, dpi=200, facecolor=SURFACE)
        plt.close(fig)
        paths.append(path)
    return paths


def finite_or_none(value: float) -> float | None:
    """Helper for JSON output: NaN and infinity become None (shown as blank)."""
    return None if value is None or (isinstance(value, float) and not math.isfinite(value)) else value
