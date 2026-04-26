"""Cortical atlas + advertiser-metrics mapper. The IP layer of NeuroPulse.

Takes TRIBE v2's (T, ~20484) cortical predictions on fsaverage5 → 6 advertiser metrics.

# What's well-validated
- Yeo 7-network parcellation (Yeo et al. 2011) — published, peer-reviewed.

# What's our hypothesis
- The mapping from network activation → advertiser metric. We document the rationale per metric
  but the precise weights are calibrated heuristics, to be refined against ground-truth campaign
  performance data when we have it.

# Networks (Yeo 7)
1 Visual              — V1, V2, V4 etc. Primary visual processing.
2 Somatomotor         — Sensorimotor; not very useful for advertising.
3 DorsalAttention     — Top-down, goal-directed attention; gaze control.
4 VentralAttention    — Bottom-up salience; reorienting; emotional salience.
5 Limbic              — OFC, temporal pole; emotion, motivation, memory consolidation.
6 Frontoparietal      — Executive control, decision-making, working memory.
7 DefaultMode         — Self-referential, mentalizing, narrative comprehension.
"""
from __future__ import annotations

import os
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy.special import expit

from .tribe import CorticalPrediction


NETWORK_NAMES = ["Visual", "Somatomotor", "DorsalAttention", "VentralAttention", "Limbic", "Frontoparietal", "DefaultMode"]


@dataclass
class AdvertiserMetric:
    name: str
    description: str
    network_weights: dict[str, float]  # contribution per network
    temporal_aggregation: str  # "mean" | "stability" | "early_slope" | "max"
    normalization_center: float = 0.0
    normalization_scale: float = 4.0


ADVERTISER_METRICS: list[AdvertiserMetric] = [
    AdvertiserMetric(
        name="attention_sustainment",
        description="How well the creative holds visual attention over time. Higher = more sustained gaze.",
        network_weights={"Visual": 1.0, "DorsalAttention": 0.8},
        temporal_aggregation="stability",
        normalization_center=0.5,
    ),
    AdvertiserMetric(
        name="emotional_arousal",
        description="Strength of activation in salience and limbic networks — does the creative move people?",
        network_weights={"Limbic": 1.0, "VentralAttention": 0.6},
        temporal_aggregation="mean",
        normalization_center=0.0,
    ),
    AdvertiserMetric(
        name="memorability",
        description="Predicted memory encoding strength — limbic/temporal regions associated with consolidation.",
        network_weights={"Limbic": 0.7, "DefaultMode": 0.5},
        temporal_aggregation="mean",
        normalization_center=0.0,
    ),
    AdvertiserMetric(
        name="reward_anticipation",
        description="Approach motivation — does the creative make viewers want what's being shown?",
        network_weights={"Frontoparietal": 0.5, "DefaultMode": 0.3, "Limbic": 0.2},
        temporal_aggregation="mean",
        normalization_center=0.0,
    ),
    AdvertiserMetric(
        name="social_processing",
        description="Activation of social-cognition / mentalizing networks. Important for human-centered creative.",
        network_weights={"DefaultMode": 0.7, "VentralAttention": 0.3},
        temporal_aggregation="mean",
        normalization_center=0.0,
    ),
    AdvertiserMetric(
        name="thumb_stop_power",
        description="Speed of attention capture in the first 2 seconds — critical for feed/Reels formats.",
        network_weights={"Visual": 1.0, "DorsalAttention": 0.5},
        temporal_aggregation="early_slope",
        normalization_center=0.5,
    ),
]


def _default_labels_path() -> Path:
    return Path(os.environ.get("MODEL_WEIGHTS_DIR", "weights")) / "yeo7_fsaverage5_labels.npy"


# Yeo 7-network annotations on fsaverage5, hosted by the Yeo lab at CBIG (Thomas Yeo, NUS/Harvard).
# Files: lh.Yeo2011_7Networks_N1000.annot.fsaverage5 + rh.Yeo2011_7Networks_N1000.annot.fsaverage5
# CBIG repo: github.com/ThomasYeoLab/CBIG
_YEO_BASE_URL = (
    "https://github.com/ThomasYeoLab/CBIG/raw/master/stable_projects/brain_parcellation/"
    "Yeo2011_fcMRI_clustering/1000subjects_reference/Yeo_JNeurophysiol11_SplitLabels"
)


class CorticalAtlas:
    """Loads vertex→Yeo7-network labels for fsaverage5 and aggregates activations to networks."""

    def __init__(self, labels_path: Path | None = None):
        self.labels_path = labels_path or _default_labels_path()
        self._labels: np.ndarray | None = None

    def labels(self) -> np.ndarray:
        if self._labels is None:
            if not self.labels_path.exists():
                raise FileNotFoundError(
                    f"Atlas labels not found at {self.labels_path}.\n"
                    f"Run: python -m app.models.atlas download"
                )
            self._labels = np.load(self.labels_path)
            if self._labels.shape[0] not in (20480, 20484):
                raise ValueError(
                    f"Expected fsaverage5 vertex count (~20484); got {self._labels.shape[0]}"
                )
        return self._labels

    def parcellate(self, prediction: CorticalPrediction) -> dict[str, np.ndarray]:
        """Return {network_name: (T,) mean activation across vertices in that network}."""
        labels = self.labels()
        if prediction.activations.shape[1] != labels.shape[0]:
            raise ValueError(
                f"Prediction has {prediction.activations.shape[1]} vertices; "
                f"atlas has {labels.shape[0]}. Mesh mismatch."
            )

        out: dict[str, np.ndarray] = {}
        for net_id, net_name in enumerate(NETWORK_NAMES, start=1):
            mask = labels == net_id
            if not mask.any():
                out[net_name] = np.zeros(prediction.n_timesteps, dtype=np.float32)
            else:
                out[net_name] = prediction.activations[:, mask].mean(axis=1).astype(np.float32)
        return out


@dataclass
class MetricResult:
    name: str
    value: int  # 0-100 normalized
    raw: float  # Pre-normalization
    description: str


class AdvertiserMetricsMapper:
    """Project Yeo network activations → 6 advertiser-relevant metrics on a 0-100 scale."""

    def __init__(self, metrics: list[AdvertiserMetric] | None = None):
        self.metrics = metrics or ADVERTISER_METRICS

    def compute(self, network_timeseries: dict[str, np.ndarray]) -> dict[str, MetricResult]:
        results: dict[str, MetricResult] = {}
        if not network_timeseries:
            return results
        n_steps = len(next(iter(network_timeseries.values())))

        for metric in self.metrics:
            combined = np.zeros(n_steps, dtype=np.float32)
            total_weight = 0.0
            for net_name, weight in metric.network_weights.items():
                ts = network_timeseries.get(net_name)
                if ts is None:
                    continue
                combined += ts * weight
                total_weight += weight
            if total_weight > 0:
                combined /= total_weight

            raw = self._aggregate(combined, metric.temporal_aggregation)
            normalized = self._normalize(raw, metric.normalization_center, metric.normalization_scale)
            results[metric.name] = MetricResult(
                name=metric.name,
                value=int(round(float(normalized))),
                raw=round(float(raw), 4),
                description=metric.description,
            )
        return results

    @staticmethod
    def _aggregate(timeseries: np.ndarray, mode: str) -> float:
        if timeseries.size == 0:
            return 0.0
        if mode == "mean":
            return float(timeseries.mean())
        if mode == "max":
            return float(timeseries.max())
        if mode == "stability":
            mean = float(timeseries.mean())
            std = float(timeseries.std())
            cv = std / (abs(mean) + 1e-6)
            return 1.0 / (1.0 + cv)
        if mode == "early_slope":
            cutoff = max(2, len(timeseries) // 4)
            early = timeseries[:cutoff]
            denom = max(1e-6, abs(float(early[0])))
            return float((early.max() - early[0]) / denom)
        return float(timeseries.mean())

    @staticmethod
    def _normalize(raw: float, center: float, scale: float) -> float:
        """Sigmoid mapping raw → [0, 100]. Center/scale calibrated per metric, retunable from data."""
        return float(expit((raw - center) * scale) * 100.0)


def composite_engagement_score(metrics: dict[str, MetricResult]) -> int:
    """Single 0-100 score for the Bayesian A/B engine, weighted across the 6 metrics."""
    weights = {
        "attention_sustainment": 0.25,
        "emotional_arousal": 0.20,
        "memorability": 0.15,
        "reward_anticipation": 0.15,
        "social_processing": 0.10,
        "thumb_stop_power": 0.15,
    }
    total = 0.0
    weight_sum = 0.0
    for name, w in weights.items():
        m = metrics.get(name)
        if m is not None:
            total += m.value * w
            weight_sum += w
    if weight_sum == 0:
        return 0
    return int(round(total / weight_sum))


def download_yeo_atlas(target: Path | None = None) -> Path:
    """One-shot download of Yeo7 fsaverage5 labels and save as a (20484,) numpy array.

    Run once during repo setup or in the Modal image build step.
    Pulls .annot files from the Yeo lab's CBIG GitHub, parses with nibabel.freesurfer,
    concatenates lh+rh.
    """
    target = target or _default_labels_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    import nibabel.freesurfer  # type: ignore

    labels_per_hemi: list[np.ndarray] = []
    for hemi in ("lh", "rh"):
        url = f"{_YEO_BASE_URL}/{hemi}.Yeo2011_7Networks_N1000.split_components.annot.fsaverage5"
        tmp = target.parent / f"_{hemi}_yeo.annot"
        print(f"Fetching {url}")
        try:
            urllib.request.urlretrieve(url, tmp)
        except urllib.error.HTTPError as e:
            raise RuntimeError(
                f"Failed to download {url} ({e}). The Yeo lab may have changed the path. "
                f"Manual fallback: download lh.Yeo2011_7Networks_N1000.split_components.annot.fsaverage5 and "
                f"rh.Yeo2011_7Networks_N1000.split_components.annot.fsaverage5 from "
                f"github.com/ThomasYeoLab/CBIG, parse with nibabel.freesurfer.read_annot, "
                f"concatenate lh+rh, and save as {target}"
            )
        labels_arr, _ctab, _names = nibabel.freesurfer.read_annot(str(tmp))
        labels_per_hemi.append(labels_arr.astype(np.int8))
        tmp.unlink(missing_ok=True)

    combined = np.concatenate(labels_per_hemi).astype(np.int8)
    np.save(target, combined)
    n_per_network = {
        f"network_{i}_{NETWORK_NAMES[i - 1]}": int((combined == i).sum())
        for i in range(1, 8)
    }
    print(f"Saved {combined.shape[0]} vertex labels to {target}")
    print(f"Vertices per network: {n_per_network}")
    return target


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "download":
        download_yeo_atlas()
    else:
        print("Usage: python -m app.models.atlas download")
