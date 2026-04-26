"""Engagement scorer.

V0 (this file): heuristic weighted combination of saliency stats, aesthetic, and emotion.
Documented openly so pilots understand it's a heuristic. Once we have pilot CTR data we
replace this with a trained regressor (`scorer_v1.pt`) — same interface, same outputs.

Why heuristic-first: it's transparent, debuggable, and ships immediately. A learned model
trained on irrelevant public data would not be more accurate than a thoughtful heuristic
on advertising creative — and would obscure what's driving the score.
"""
from __future__ import annotations

from dataclasses import dataclass

VERSION = "engagement_scorer@v0-heuristic"


@dataclass
class ScorerInput:
    saliency_entropy: float       # [0, 1] — 1.0 = scattered, 0.0 = focused
    saliency_peak_concentration: float  # [0, 1] — fraction of saliency mass in top 10% pixels
    saliency_center_offset: float       # [0, 1] — distance of CoM from center, in image-diagonal units
    aesthetic_score: float        # [1, 10]
    emotion_confidence: float     # [0, 1]
    emotion_valence: str          # "positive" | "neutral" | "negative"


def score(features: ScorerInput) -> int:
    """Return engagement score 0-100.

    Components (weights sum to 100):
    - 35 pts: saliency focus quality (concentrated peak + low entropy)
    - 30 pts: aesthetic quality (linear scale 1-10 -> 0-30)
    - 25 pts: emotional clarity (high confidence positive valence)
    - 10 pts: focal placement (slight off-center is better than dead-center)
    """
    # Saliency focus: reward focused attention (low entropy, high peak concentration)
    focus_score = (1.0 - features.saliency_entropy) * 0.5 + features.saliency_peak_concentration * 0.5
    focus_pts = focus_score * 35

    # Aesthetic: 1-10 -> 0-30
    aesthetic_pts = (features.aesthetic_score - 1.0) / 9.0 * 30

    # Emotional clarity
    valence_multiplier = {
        "positive": 1.0,
        "neutral": 0.5,
        "negative": 0.7,  # Negative emotion can still be effective (fear, urgency) — partial credit
    }[features.emotion_valence]
    emotion_pts = features.emotion_confidence * valence_multiplier * 25

    # Focal placement: slight off-center (rule of thirds) is better than dead-center.
    # Offset of ~0.15 (slight off-center) gets full marks; 0 or > 0.4 gets less.
    offset = features.saliency_center_offset
    if offset < 0.05:
        placement_score = 0.6  # Dead center — boring
    elif offset < 0.20:
        placement_score = 1.0  # Rule of thirds zone
    elif offset < 0.35:
        placement_score = 0.7  # Off-center but acceptable
    else:
        placement_score = 0.4  # Far off-center — poor composition
    placement_pts = placement_score * 10

    total = focus_pts + aesthetic_pts + emotion_pts + placement_pts
    return int(round(max(0, min(100, total))))
