"""Integration & unit tests for the TRIBE-based pipeline.

GPU-bound tests (full TRIBE inference) are skipped without CUDA. The atlas/metrics tests
run on synthetic data and don't need a GPU — they validate the IP layer's behavior.
"""
from __future__ import annotations

import numpy as np
import pytest

GPU_AVAILABLE = False
try:
    import torch

    GPU_AVAILABLE = torch.cuda.is_available()
except ImportError:
    pass


# ============================================================
# Atlas / metrics tests (no GPU required)
# ============================================================


def _make_synthetic_prediction(n_steps: int = 30, n_vertices: int = 20484, seed: int = 0):
    from app.models.tribe import CorticalPrediction

    rng = np.random.default_rng(seed)
    activations = rng.standard_normal((n_steps, n_vertices)).astype(np.float32)
    timestamps = np.arange(n_steps, dtype=np.float32) * 1.5
    return CorticalPrediction(
        activations=activations,
        timestamps_sec=timestamps,
        duration_sec=n_steps * 1.5,
        sampling_rate_hz=1 / 1.5,
        n_vertices=n_vertices,
    )


def _make_synthetic_atlas_labels(n_vertices: int = 20484) -> np.ndarray:
    """Roughly even split across 7 networks. Returns (n_vertices,) int8 labels in [1, 7]."""
    rng = np.random.default_rng(42)
    labels = rng.integers(1, 8, size=n_vertices, dtype=np.int8)
    return labels


def test_atlas_parcellates_to_seven_networks(tmp_path, monkeypatch):
    from app.models.atlas import NETWORK_NAMES, CorticalAtlas

    labels_path = tmp_path / "labels.npy"
    np.save(labels_path, _make_synthetic_atlas_labels())

    atlas = CorticalAtlas(labels_path=labels_path)
    prediction = _make_synthetic_prediction()
    network_ts = atlas.parcellate(prediction)

    assert set(network_ts.keys()) == set(NETWORK_NAMES)
    for ts in network_ts.values():
        assert ts.shape == (prediction.n_timesteps,)


def test_metrics_mapper_outputs_in_zero_hundred(tmp_path):
    from app.models.atlas import (
        AdvertiserMetricsMapper,
        CorticalAtlas,
        composite_engagement_score,
    )

    labels_path = tmp_path / "labels.npy"
    np.save(labels_path, _make_synthetic_atlas_labels())

    atlas = CorticalAtlas(labels_path=labels_path)
    prediction = _make_synthetic_prediction(seed=7)
    network_ts = atlas.parcellate(prediction)

    mapper = AdvertiserMetricsMapper()
    metrics = mapper.compute(network_ts)

    assert len(metrics) == 6
    expected = {
        "attention_sustainment",
        "emotional_arousal",
        "memorability",
        "reward_anticipation",
        "social_processing",
        "thumb_stop_power",
    }
    assert set(metrics.keys()) == expected
    for m in metrics.values():
        assert 0 <= m.value <= 100, f"Metric {m.name} out of range: {m.value}"

    composite = composite_engagement_score(metrics)
    assert 0 <= composite <= 100


def test_metrics_differ_with_different_input(tmp_path):
    """Substantially different cortical activation patterns must produce different metrics.

    We bias the two synthetic predictions in opposite directions to ensure the metrics
    distinguish them — a regression check that the pipeline is sensitive to input variation.
    """
    from app.models.atlas import AdvertiserMetricsMapper, CorticalAtlas
    from app.models.tribe import CorticalPrediction

    labels_path = tmp_path / "labels.npy"
    np.save(labels_path, _make_synthetic_atlas_labels())
    atlas = CorticalAtlas(labels_path=labels_path)

    rng = np.random.default_rng(0)
    n_steps, n_vertices = 30, 20484

    base = rng.standard_normal((n_steps, n_vertices)).astype(np.float32)
    pred_high = CorticalPrediction(
        activations=base + 1.0,
        timestamps_sec=np.arange(n_steps, dtype=np.float32) * 1.5,
        duration_sec=n_steps * 1.5,
        sampling_rate_hz=1 / 1.5,
        n_vertices=n_vertices,
    )
    pred_low = CorticalPrediction(
        activations=base - 1.0,
        timestamps_sec=np.arange(n_steps, dtype=np.float32) * 1.5,
        duration_sec=n_steps * 1.5,
        sampling_rate_hz=1 / 1.5,
        n_vertices=n_vertices,
    )

    mapper = AdvertiserMetricsMapper()
    metrics_high = mapper.compute(atlas.parcellate(pred_high))
    metrics_low = mapper.compute(atlas.parcellate(pred_low))

    different = sum(
        1 for k in metrics_high if metrics_high[k].value != metrics_low[k].value
    )
    assert different >= 3, (
        f"Most metrics should differ between strongly distinct inputs; "
        f"got {different}/6 different"
    )

    # The high-activation prediction should outscore the low one on emotional_arousal
    # (mean-aggregated, sigmoid centered at 0, monotonic in input)
    assert metrics_high["emotional_arousal"].value > metrics_low["emotional_arousal"].value


def test_atlas_raises_on_vertex_mismatch(tmp_path):
    from app.models.atlas import CorticalAtlas

    labels_path = tmp_path / "labels.npy"
    np.save(labels_path, _make_synthetic_atlas_labels(n_vertices=20484))

    atlas = CorticalAtlas(labels_path=labels_path)
    bad_prediction = _make_synthetic_prediction(n_vertices=10000)
    with pytest.raises(ValueError, match="vertices"):
        atlas.parcellate(bad_prediction)


# ============================================================
# Full pipeline (GPU + TRIBE v2 weights required)
# ============================================================


@pytest.mark.skipif(not GPU_AVAILABLE, reason="No GPU available")
@pytest.mark.skipif(
    True,
    reason="Requires TRIBE v2 install + ~24GB VRAM + a sample video; run manually with --gpu --tribe",
)
def test_full_pipeline_smoke():
    from pathlib import Path

    from app.pipeline import Pipeline

    sample_video = Path("tests/fixtures/sample_ad.mp4")
    pipe = Pipeline(device="cuda")
    pipe.warmup()
    result, renders = pipe.run_video(sample_video)

    assert 0 <= result["composite_engagement_score"] <= 100
    assert len(result["metrics"]) == 6
    assert "brain" in renders
    assert renders["brain"][:8] == b"\x89PNG\r\n\x1a\n"
