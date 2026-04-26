"""DeepGaze IIE wrapper.

DeepGaze IIE predicts the spatial distribution of human eye fixations on an image.
It is the SOTA on the MIT/Tuebingen Saliency Benchmark and is trained on real eye-tracking
data, which is what makes the "neuro" framing of NeuroPulse legitimate.

Install: pip install git+https://github.com/matthias-k/DeepGaze.git

The model needs a center-bias prior — humans look more at image centers than edges.
We use a simple Gaussian centered on the image as a default prior.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

import numpy as np
import torch
from PIL import Image

VERSION = "deepgaze_iie@v1"


def _gaussian_centerbias(height: int, width: int, sigma_frac: float = 0.25) -> np.ndarray:
    """Return a log-density center-bias prior shaped (H, W).

    Models the fact that humans fixate the center of an image more often than edges.
    Sigma is `sigma_frac * min(H, W)`.
    """
    sigma = sigma_frac * min(height, width)
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    cy, cx = (height - 1) / 2.0, (width - 1) / 2.0
    log_density = -((xx - cx) ** 2 + (yy - cy) ** 2) / (2.0 * sigma**2)
    # Normalize to log probability
    log_density -= np.log(np.exp(log_density).sum())
    return log_density


class SaliencyModel:
    """Lazy-loaded DeepGaze IIE wrapper."""

    def __init__(self, device: str = "cuda"):
        self.device = device if torch.cuda.is_available() else "cpu"
        self._model = None

    def _load(self):
        if self._model is not None:
            return
        # Imported here to avoid hard dep on deepgaze_pytorch at module-import time
        from deepgaze_pytorch import DeepGazeIIE  # type: ignore

        self._model = DeepGazeIIE(pretrained=True).to(self.device).eval()

    @torch.inference_mode()
    def predict(self, image: Image.Image) -> np.ndarray:
        """Return a saliency map (H, W) normalized to [0, 1]."""
        self._load()
        assert self._model is not None

        img = image.convert("RGB")
        w, h = img.size
        arr = np.asarray(img, dtype=np.float32) / 255.0  # (H, W, 3)
        tensor = torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0).to(self.device)

        cb = _gaussian_centerbias(h, w)
        cb_tensor = torch.from_numpy(cb).unsqueeze(0).to(self.device)

        log_density = self._model(tensor, cb_tensor)  # (1, 1, H, W) log-density
        density = log_density.squeeze().exp().cpu().numpy()
        # Normalize to [0, 1] for visualization
        density = density - density.min()
        if density.max() > 0:
            density = density / density.max()
        return density

    @staticmethod
    def stats(saliency_map: np.ndarray) -> dict[str, float]:
        """Compute summary stats used by the engagement scorer and strengths/weaknesses heuristics."""
        flat = saliency_map.flatten()
        # Normalized entropy: 1.0 = uniform (scattered attention), 0.0 = single peak (focused)
        p = flat / (flat.sum() + 1e-12)
        entropy_raw = -(p * np.log(p + 1e-12)).sum()
        entropy_norm = float(entropy_raw / np.log(len(p)))

        # Peak concentration: fraction of total saliency in top 10% of pixels
        threshold = np.quantile(flat, 0.9)
        peak_concentration = float(flat[flat >= threshold].sum() / (flat.sum() + 1e-12))

        # Center-of-mass offset from image center, in fraction of image diagonal
        h, w = saliency_map.shape
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        total = saliency_map.sum() + 1e-12
        com_y = float((saliency_map * yy).sum() / total)
        com_x = float((saliency_map * xx).sum() / total)
        diag = float(np.sqrt(h**2 + w**2))
        center_offset = float(np.sqrt((com_y - h / 2) ** 2 + (com_x - w / 2) ** 2) / diag)

        return {
            "entropy": entropy_norm,
            "peak_concentration": peak_concentration,
            "center_offset": center_offset,
        }


def render_overlay(image: Image.Image, saliency: np.ndarray, alpha: float = 0.5) -> Image.Image:
    """Overlay a saliency heatmap (red→yellow) on the original image and return as PIL."""
    from matplotlib import cm  # type: ignore

    base = image.convert("RGBA")
    cmap = cm.get_cmap("inferno")
    heat_rgba = (cmap(saliency) * 255).astype(np.uint8)  # (H, W, 4)
    heat_img = Image.fromarray(heat_rgba, mode="RGBA").resize(base.size, Image.BILINEAR)

    # Apply alpha modulation by saliency intensity so low-saliency areas are transparent
    sal_resized = np.asarray(
        Image.fromarray((saliency * 255).astype(np.uint8)).resize(base.size, Image.BILINEAR)
    )
    sal_alpha = (sal_resized.astype(np.float32) / 255.0 * alpha * 255).astype(np.uint8)
    heat_pixels = np.asarray(heat_img).copy()
    heat_pixels[..., 3] = sal_alpha

    overlay = Image.fromarray(heat_pixels, mode="RGBA")
    return Image.alpha_composite(base, overlay).convert("RGB")


def heatmap_to_png_bytes(image: Image.Image, saliency: np.ndarray) -> bytes:
    """Render the overlay and return PNG bytes for upload to Supabase Storage."""
    overlay = render_overlay(image, saliency)
    buf = BytesIO()
    overlay.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
