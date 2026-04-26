"""Zero-shot emotion classifier built on SigLIP.

Apache 2.0 license. We don't fine-tune yet — V1 uses zero-shot text prompts
mapped to Russell's circumplex of affect. V2 will replace with a fine-tuned head
trained on labeled ad-creative + emotional-response data from pilots.
"""
from __future__ import annotations

import torch
from PIL import Image
from transformers import AutoModel, AutoProcessor

VERSION = "siglip-base-patch16-384@zeroshot-v1"

# Russell's circumplex axes condensed to 7 commonly-recognizable emotion categories.
# Prompts are deliberately advertising-flavored — this matters for zero-shot accuracy.
EMOTION_PROMPTS: dict[str, str] = {
    "joy": "an advertisement evoking joy, happiness, or delight",
    "trust": "an advertisement evoking trust, reliability, or confidence",
    "surprise": "an advertisement evoking surprise, wonder, or amazement",
    "calm": "an advertisement evoking calm, peace, or tranquility",
    "anger": "an advertisement evoking frustration, anger, or aggression",
    "fear": "an advertisement evoking fear, anxiety, or threat",
    "sadness": "an advertisement evoking sadness, melancholy, or loss",
}

VALENCE_MAP = {
    "joy": "positive",
    "trust": "positive",
    "surprise": "positive",
    "calm": "positive",
    "anger": "negative",
    "fear": "negative",
    "sadness": "negative",
}


class EmotionModel:
    def __init__(self, device: str = "cuda", model_id: str = "google/siglip-base-patch16-384"):
        self.device = device if torch.cuda.is_available() else "cpu"
        self.model_id = model_id
        self._model = None
        self._processor = None
        self._text_features: torch.Tensor | None = None
        self._labels: list[str] = list(EMOTION_PROMPTS.keys())

    def _load(self):
        if self._model is not None:
            return
        self._processor = AutoProcessor.from_pretrained(self.model_id)
        self._model = AutoModel.from_pretrained(self.model_id).to(self.device).eval()

        prompts = [EMOTION_PROMPTS[label] for label in self._labels]
        with torch.inference_mode():
            text_inputs = self._processor(text=prompts, padding="max_length", return_tensors="pt").to(
                self.device
            )
            text_features = self._model.get_text_features(**text_inputs)
            text_features = text_features / text_features.norm(dim=-1, keepdim=True)
            self._text_features = text_features

    @torch.inference_mode()
    def predict(self, image: Image.Image) -> dict:
        """Return {"valence": ..., "dominant": ..., "confidence": ..., "scores": {label: prob}}."""
        self._load()
        assert self._model is not None and self._processor is not None
        assert self._text_features is not None

        img = image.convert("RGB")
        image_inputs = self._processor(images=img, return_tensors="pt").to(self.device)
        image_features = self._model.get_image_features(**image_inputs)
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)

        # SigLIP uses sigmoid scoring rather than softmax, but we want a probability distribution
        # over the 7 emotions, so we use softmax over cosine similarities.
        logits = (image_features @ self._text_features.T).squeeze(0)  # (n_labels,)
        probs = torch.softmax(logits * 10.0, dim=-1)  # temperature scaling for sharper distribution
        scores = {label: float(p) for label, p in zip(self._labels, probs.tolist())}

        dominant = max(scores, key=scores.get)
        confidence = scores[dominant]
        valence = VALENCE_MAP[dominant]

        # If no emotion exceeds 0.25 confidence, mark as neutral
        if confidence < 0.25:
            valence = "neutral"

        return {
            "valence": valence,
            "dominant": dominant,
            "confidence": confidence,
            "scores": scores,
        }
