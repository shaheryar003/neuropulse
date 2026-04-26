"""LAION Aesthetic V2 wrapper.

Uses CLIP ViT-L/14 features → small MLP regressor trained on AVA aesthetic ratings.
Public weights: https://github.com/LAION-AI/aesthetic-predictor

The MLP weights file (`sac+logos+ava1-l14-linearMSE.pth`) is downloaded once on first run.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import open_clip
import torch
import torch.nn as nn
from PIL import Image

VERSION = "laion_aesthetic_v2@sac+logos+ava1-l14-linearMSE"

WEIGHTS_URL = (
    "https://github.com/LAION-AI/aesthetic-predictor/raw/main/sac%2Blogos%2Bava1-l14-linearMSE.pth"
)
WEIGHTS_FILE = "sac+logos+ava1-l14-linearMSE.pth"


class AestheticMLP(nn.Module):
    """The exact architecture used to train LAION's public aesthetic predictor."""

    def __init__(self, input_size: int = 768):
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(input_size, 1024),
            nn.Dropout(0.2),
            nn.Linear(1024, 128),
            nn.Dropout(0.2),
            nn.Linear(128, 64),
            nn.Dropout(0.1),
            nn.Linear(64, 16),
            nn.Linear(16, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.layers(x)


class AestheticModel:
    def __init__(self, device: str = "cuda", weights_dir: Path | None = None):
        self.device = device if torch.cuda.is_available() else "cpu"
        self.weights_dir = weights_dir or Path(os.environ.get("MODEL_WEIGHTS_DIR", "weights"))
        self.weights_dir.mkdir(parents=True, exist_ok=True)
        self._clip = None
        self._preprocess = None
        self._mlp = None

    def _ensure_weights(self) -> Path:
        path = self.weights_dir / WEIGHTS_FILE
        if not path.exists():
            import httpx

            with httpx.stream("GET", WEIGHTS_URL, follow_redirects=True, timeout=120) as r:
                r.raise_for_status()
                with open(path, "wb") as f:
                    for chunk in r.iter_bytes():
                        f.write(chunk)
        return path

    def _load(self):
        if self._mlp is not None:
            return
        clip_model, _, preprocess = open_clip.create_model_and_transforms(
            "ViT-L-14", pretrained="openai"
        )
        clip_model.to(self.device).eval()
        self._clip = clip_model
        self._preprocess = preprocess

        mlp = AestheticMLP(input_size=768)
        weights_path = self._ensure_weights()
        state = torch.load(weights_path, map_location=self.device)
        mlp.load_state_dict(state)
        mlp.to(self.device).eval()
        self._mlp = mlp

    @torch.inference_mode()
    def predict(self, image: Image.Image) -> float:
        """Return aesthetic score in [1, 10]."""
        self._load()
        assert self._clip is not None and self._preprocess is not None and self._mlp is not None

        img = image.convert("RGB")
        x = self._preprocess(img).unsqueeze(0).to(self.device)

        feats = self._clip.encode_image(x)
        feats = feats / feats.norm(dim=-1, keepdim=True)
        score = self._mlp(feats.float()).item()

        # Clamp to expected range
        return float(np.clip(score, 1.0, 10.0))
