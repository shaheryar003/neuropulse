"""Heuristic strengths/weaknesses generator from feature stats.

V0 maps feature stats to plain-language bullets. V2 will swap to a small LLM call
for richer phrasing once we know which copy converts pilots best.
"""
from __future__ import annotations

from .models.scorer import ScorerInput


def generate(features: ScorerInput) -> tuple[list[str], list[str]]:
    """Return (strengths, weaknesses) bullet lists."""
    strengths: list[str] = []
    weaknesses: list[str] = []

    # Saliency focus
    if features.saliency_entropy < 0.45 and features.saliency_peak_concentration > 0.45:
        strengths.append("Strong focal point — viewers' attention concentrates on a clear primary subject.")
    elif features.saliency_entropy > 0.75:
        weaknesses.append("Attention is scattered across the creative — consider a stronger focal element.")
    elif features.saliency_peak_concentration < 0.25:
        weaknesses.append("No dominant attention peak — the creative lacks a clear visual anchor.")

    # Aesthetic
    if features.aesthetic_score >= 7.0:
        strengths.append(
            f"High aesthetic quality ({features.aesthetic_score:.1f}/10) — visually polished against benchmark ad creative."
        )
    elif features.aesthetic_score >= 5.0:
        # Neither praise nor critique — silent
        pass
    elif features.aesthetic_score < 4.0:
        weaknesses.append(
            f"Aesthetic score is below benchmark ({features.aesthetic_score:.1f}/10) — production quality may need lifting."
        )

    # Emotion
    if features.emotion_confidence > 0.45 and features.emotion_valence == "positive":
        strengths.append(f"Clear positive emotional signal ({features.emotion_confidence:.0%} confidence) — strong affective alignment.")
    elif features.emotion_confidence > 0.45 and features.emotion_valence == "negative":
        weaknesses.append(
            "Dominant emotional signal is negative — verify this aligns with your campaign intent (urgency / fear-appeal can work, but check)."
        )
    elif features.emotion_confidence < 0.20:
        weaknesses.append("Emotional signal is ambiguous — the creative does not strongly evoke any specific feeling.")

    # Focal placement
    offset = features.saliency_center_offset
    if 0.10 <= offset <= 0.22:
        strengths.append("Focal placement near rule-of-thirds zones — composition is cinematically strong.")
    elif offset < 0.05:
        weaknesses.append("Focal point is dead-center — slightly off-center placement typically increases engagement.")
    elif offset > 0.35:
        weaknesses.append("Focal point is far off-center — risk of feeling unbalanced on small mobile viewports.")

    # Edge cases
    if not strengths:
        strengths.append("No standout strengths detected — creative performs at baseline across measured dimensions.")
    if not weaknesses:
        weaknesses.append("No major weaknesses detected — strong baseline; consider testing variants for incremental lift.")

    return strengths, weaknesses
