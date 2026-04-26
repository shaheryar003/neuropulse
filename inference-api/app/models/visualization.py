"""Brain & metric visualizations rendered server-side as PNG bytes.

Three artifacts per inference run:
1. `render_cortical_activation` — mean activation over time, projected on fsaverage5 brain (4 views)
2. `render_network_timecourses` — line plot of 7 Yeo networks over time
3. `render_metrics_radar` — 6 advertiser metrics on a polar radar chart

Designed for the Meta pitch — a visual that says "this is your model's output, here's our translation."
"""
from __future__ import annotations

from io import BytesIO

# Set matplotlib to a headless backend BEFORE importing pyplot
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .atlas import MetricResult
from .tribe import CorticalPrediction


_ACCENT = "#4af4b0"
_ACCENT2 = "#7b5cfa"
_BG = "#05060a"
_TEXT = "#e8eaf2"


def render_cortical_activation(prediction: CorticalPrediction) -> bytes:
    """Render mean cortical activation on fsaverage5. Returns PNG bytes (4-panel: lh+rh × lateral+medial)."""
    from nilearn import datasets, plotting

    fsaverage = datasets.fetch_surf_fsaverage(mesh="fsaverage5")
    activations = prediction.activations.mean(axis=0)

    n_per_hemi = activations.shape[0] // 2
    lh, rh = activations[:n_per_hemi], activations[n_per_hemi:]

    fig = plt.figure(figsize=(12, 7), facecolor=_BG)
    gs = fig.add_gridspec(2, 2)

    panels = [
        (gs[0, 0], "left", "lateral", lh, "pial_left", "sulc_left"),
        (gs[0, 1], "left", "medial", lh, "pial_left", "sulc_left"),
        (gs[1, 0], "right", "lateral", rh, "pial_right", "sulc_right"),
        (gs[1, 1], "right", "medial", rh, "pial_right", "sulc_right"),
    ]

    for slot, hemi, view, data, mesh_key, sulc_key in panels:
        ax = fig.add_subplot(slot, projection="3d")
        plotting.plot_surf_stat_map(
            fsaverage[mesh_key],
            data,
            hemi=hemi,
            view=view,
            bg_map=fsaverage[sulc_key],
            colorbar=False,
            axes=ax,
            cmap="inferno",
            darkness=0.5,
        )
        ax.set_facecolor(_BG)
        ax.set_title(f"{hemi}/{view}", color=_TEXT, fontsize=10)

    fig.suptitle("TRIBE v2 cortical activation (mean over stimulus duration)", color=_TEXT, fontsize=13)
    fig.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor=_BG)
    plt.close(fig)
    return buf.getvalue()


def render_network_timecourses(
    network_timeseries: dict[str, np.ndarray], prediction: CorticalPrediction
) -> bytes:
    """Line plot of Yeo network activations over time. Returns PNG bytes."""
    fig, ax = plt.subplots(figsize=(10, 5), facecolor=_BG)
    ax.set_facecolor(_BG)

    times = prediction.timestamps_sec
    palette = plt.colormaps["plasma"](np.linspace(0.1, 0.9, len(network_timeseries)))

    for color, (name, ts) in zip(palette, network_timeseries.items()):
        ax.plot(times[: len(ts)], ts, label=name, linewidth=1.8, color=color)

    ax.set_xlabel("Time (s)", color=_TEXT)
    ax.set_ylabel("Network activation (z)", color=_TEXT)
    ax.set_title("Yeo 7-network activation timecourse", color=_TEXT, fontsize=13)
    ax.tick_params(colors=_TEXT)
    for spine in ax.spines.values():
        spine.set_edgecolor("#1e2235")
    ax.legend(
        loc="upper right",
        fontsize=8,
        facecolor=_BG,
        edgecolor="#1e2235",
        labelcolor=_TEXT,
    )
    ax.grid(alpha=0.15, color=_TEXT)

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor=_BG)
    plt.close(fig)
    return buf.getvalue()


def render_metrics_radar(metrics: dict[str, MetricResult]) -> bytes:
    """Polar radar of the 6 advertiser metrics on a 0-100 scale. Returns PNG bytes."""
    names = [m.name.replace("_", " ").title() for m in metrics.values()]
    values = [m.value for m in metrics.values()]

    angles = np.linspace(0, 2 * np.pi, len(names), endpoint=False).tolist()
    values_closed = values + [values[0]]
    angles_closed = angles + [angles[0]]

    fig, ax = plt.subplots(figsize=(7, 7), subplot_kw={"projection": "polar"}, facecolor=_BG)
    ax.set_facecolor(_BG)
    ax.fill(angles_closed, values_closed, alpha=0.25, color=_ACCENT)
    ax.plot(angles_closed, values_closed, color=_ACCENT, linewidth=2.5)

    ax.set_xticks(angles)
    ax.set_xticklabels(names, color=_TEXT, fontsize=10)
    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"], color=_TEXT, fontsize=8)
    ax.set_title("Advertiser metrics — TRIBE-derived", color=_TEXT, pad=24, fontsize=13)
    ax.tick_params(colors=_TEXT)
    ax.grid(alpha=0.25, color=_TEXT)

    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor=_BG)
    plt.close(fig)
    return buf.getvalue()
