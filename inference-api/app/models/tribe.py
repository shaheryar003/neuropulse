"""TRIBE v2 wrapper — Meta's Trimodal Brain Encoder.

Predicts fMRI cortical responses to video / audio / text stimuli.
Output: (n_timesteps, ~20484 vertices) on the fsaverage5 cortical mesh.

License: CC-BY-NC-4.0. Allowed: internal R&D, demos to Meta authors. Disallowed: commercial SaaS.

Install (one-time):
    pip install git+https://github.com/facebookresearch/tribev2.git

Weights: facebook/tribev2 on HuggingFace (auto-downloaded on first instantiation).
Hardware: ~24GB VRAM. A10G or larger.
"""
from __future__ import annotations

import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import httpx
import numpy as np
import torch

VERSION = "facebook/tribev2"


@dataclass
class CorticalPrediction:
    """A TRIBE v2 prediction over time on the fsaverage5 cortical mesh."""

    activations: np.ndarray  # shape (n_timesteps, n_vertices) — fMRI prediction
    timestamps_sec: np.ndarray  # (n_timesteps,) wall-clock seconds from stimulus start
    duration_sec: float
    sampling_rate_hz: float
    n_vertices: int
    model_version: str = VERSION

    @property
    def n_timesteps(self) -> int:
        return int(self.activations.shape[0])

    def summary(self) -> dict:
        return {
            "model_version": self.model_version,
            "n_timesteps": self.n_timesteps,
            "n_vertices": self.n_vertices,
            "duration_sec": round(self.duration_sec, 2),
            "sampling_rate_hz": round(self.sampling_rate_hz, 3),
        }


class TribeModel:
    """Lazy-loaded TRIBE v2 from HuggingFace."""

    def __init__(self, device: str = "cuda", model_id: str = "facebook/tribev2"):
        self.device = device if torch.cuda.is_available() else "cpu"
        self.model_id = model_id
        self._model = None

    def _load(self):
        if self._model is not None:
            return
        # Imported lazily to avoid hard dep at module-import time
        from tribev2 import TribeModel as _TribeModel  # type: ignore

        self._model = _TribeModel.from_pretrained(self.model_id).to(self.device).eval()

    def warmup(self, sample_video_path: str | Path | None = None) -> None:
        """Pre-load the model. If a sample video is provided, also runs one prediction
        to JIT-compile any kernels and resolve cold-start path."""
        self._load()
        if sample_video_path is not None:
            self.predict_video(sample_video_path)

    @torch.inference_mode()
    def predict_video(self, video_path: str | Path) -> CorticalPrediction:
        """Run TRIBE v2 on a local video file."""
        self._load()
        assert self._model is not None

        events_df = self._model.get_events_dataframe(video_path=str(video_path))
        preds, segments = self._model.predict(events=events_df)

        # Convert to numpy
        if isinstance(preds, torch.Tensor):
            preds_np = preds.detach().cpu().numpy()
        else:
            preds_np = np.asarray(preds)

        # Extract timing from segments. Schema: dataframe with 'onset' / 'duration' / 'offset' columns.
        timestamps, duration = _extract_timing(segments, n_steps=preds_np.shape[0])
        sampling_rate = preds_np.shape[0] / duration if duration > 0 else 1.0

        return CorticalPrediction(
            activations=preds_np.astype(np.float32, copy=False),
            timestamps_sec=timestamps,
            duration_sec=float(duration),
            sampling_rate_hz=float(sampling_rate),
            n_vertices=int(preds_np.shape[1]),
        )

    def predict_video_url(self, url: str) -> CorticalPrediction:
        """Download a video from URL, run inference, clean up."""
        suffix = _suffix_from_url(url)
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            with httpx.Client(timeout=600, follow_redirects=True) as client, tmp_path.open("wb") as f:
                with client.stream("GET", url) as resp:
                    resp.raise_for_status()
                    for chunk in resp.iter_bytes():
                        f.write(chunk)
            return self.predict_video(tmp_path)
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass


def _suffix_from_url(url: str) -> str:
    """Pull a file extension out of a URL, defaulting to .mp4."""
    path_part = url.split("?")[0].split("#")[0]
    suffix = Path(path_part).suffix
    return suffix if suffix in (".mp4", ".mov", ".webm", ".m4v", ".mkv") else ".mp4"


def _extract_timing(segments, n_steps: int) -> tuple[np.ndarray, float]:
    """Return (timestamps_sec[n_steps], duration_sec) from TRIBE's segments dataframe.

    TRIBE returns a pandas DataFrame with 'onset' and 'duration' (or 'offset') columns
    per timestep. We're defensive about the exact schema.
    """
    onsets: np.ndarray | None = None
    duration: float = float("nan")

    try:
        if hasattr(segments, "columns"):
            cols = set(segments.columns)
            if "onset" in cols:
                onsets = segments["onset"].to_numpy(dtype=np.float32)
            if "offset" in cols:
                offsets = segments["offset"].to_numpy(dtype=np.float32)
                if onsets is None:
                    onsets = np.maximum(0, offsets - segments["duration"].to_numpy(dtype=np.float32))
                duration = float(offsets[-1])
            elif "duration" in cols and onsets is not None:
                duration = float(onsets[-1] + segments["duration"].to_numpy(dtype=np.float32)[-1])
    except Exception:
        pass

    if onsets is None or len(onsets) != n_steps:
        # Fallback: assume uniform fMRI TR of 1.5 s — adjust if TRIBE's true TR differs
        tr = 1.5
        onsets = np.arange(n_steps, dtype=np.float32) * tr
        duration = n_steps * tr

    if not np.isfinite(duration) or duration <= 0:
        duration = float(onsets[-1] + 1.5) if len(onsets) > 0 else 1.5

    return onsets, duration
