"""End-to-end inference pipeline.

Video → TRIBE v2 → cortical activations → Yeo7 parcellation → 6 advertiser metrics
                                                          → 3 visualizations
                                                          → composite 0-100 score for the Bayesian engine

Runnable as CLI for local sanity checks:
    python -m app.pipeline path/to/ad_video.mp4
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .models.atlas import (
    AdvertiserMetricsMapper,
    CorticalAtlas,
    MetricResult,
    composite_engagement_score,
)
from .models.tribe import VERSION as TRIBE_VERSION, CorticalPrediction, TribeModel
from .models.visualization import (
    render_cortical_activation,
    render_metrics_radar,
    render_network_timecourses,
)


_MODEL_VERSIONS = {
    "tribe": TRIBE_VERSION,
    "atlas": "yeo7-fsaverage5@2011",
    "metrics_mapper": "advertiser_metrics@v0.1",
}


class Pipeline:
    """Composes TRIBE + atlas + metrics. Lazy-loads on first inference, then caches."""

    def __init__(self, device: str = "cuda"):
        self.device = device
        self.tribe = TribeModel(device=device)
        self.atlas = CorticalAtlas()
        self.metrics_mapper = AdvertiserMetricsMapper()

    def model_versions(self) -> dict[str, str]:
        return dict(_MODEL_VERSIONS)

    def warmup(self) -> None:
        """Validate model + atlas are loadable. Cheap — does not run TRIBE inference."""
        self.tribe._load()
        self.atlas.labels()

    def run_video(self, video_path: str | Path) -> tuple[dict, dict[str, bytes]]:
        """Run end-to-end on a local video. Returns (result_dict, renders_dict)."""
        t0 = time.perf_counter()

        prediction = self.tribe.predict_video(video_path)
        network_ts = self.atlas.parcellate(prediction)
        metrics = self.metrics_mapper.compute(network_ts)
        composite = composite_engagement_score(metrics)

        renders = {
            "brain": render_cortical_activation(prediction),
            "timecourses": render_network_timecourses(network_ts, prediction),
            "radar": render_metrics_radar(metrics),
        }

        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        result = {
            "composite_engagement_score": composite,
            "metrics": {
                name: {"value": m.value, "raw": m.raw, "description": m.description}
                for name, m in metrics.items()
            },
            "network_timeseries": {name: ts.astype(float).tolist() for name, ts in network_ts.items()},
            "prediction_summary": prediction.summary(),
            "inference_ms": elapsed_ms,
        }

        return result, renders

    def run_video_url(self, video_url: str) -> tuple[dict, dict[str, bytes]]:
        """Download from URL, run, cleanup. Convenience for production callers."""
        prediction = self.tribe.predict_video_url(video_url)
        # We need the prediction object for renders, but predict_video_url already runs everything;
        # restructure to share state. Simpler: re-call run_video with a downloaded local file.
        # Use the lower-level path: replicate predict_video_url here so we have prediction in scope.
        return self._run_with_prediction(prediction)

    def _run_with_prediction(self, prediction: CorticalPrediction) -> tuple[dict, dict[str, bytes]]:
        t0 = time.perf_counter()
        network_ts = self.atlas.parcellate(prediction)
        metrics = self.metrics_mapper.compute(network_ts)
        composite = composite_engagement_score(metrics)

        renders = {
            "brain": render_cortical_activation(prediction),
            "timecourses": render_network_timecourses(network_ts, prediction),
            "radar": render_metrics_radar(metrics),
        }
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        result = {
            "composite_engagement_score": composite,
            "metrics": {
                name: {"value": m.value, "raw": m.raw, "description": m.description}
                for name, m in metrics.items()
            },
            "network_timeseries": {name: ts.astype(float).tolist() for name, ts in network_ts.items()},
            "prediction_summary": prediction.summary(),
            "inference_ms": elapsed_ms,
        }
        return result, renders


def _cli():
    parser = argparse.ArgumentParser(description="Run NeuroPulse pipeline on a local video")
    parser.add_argument("video_path", type=Path, help="Path to a local video file (mp4, mov, webm)")
    parser.add_argument("--device", default="cuda", help="cuda or cpu")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Where to save the rendered PNGs (default: alongside the video)",
    )
    args = parser.parse_args()

    if not args.video_path.exists():
        print(f"Error: {args.video_path} does not exist", file=sys.stderr)
        sys.exit(1)

    pipeline = Pipeline(device=args.device)
    pipeline.warmup()
    result, renders = pipeline.run_video(args.video_path)

    out_dir = args.out_dir or args.video_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = args.video_path.stem
    for name, png_bytes in renders.items():
        path = out_dir / f"{stem}_{name}.png"
        path.write_bytes(png_bytes)
        print(f"Saved {path}", file=sys.stderr)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    _cli()
