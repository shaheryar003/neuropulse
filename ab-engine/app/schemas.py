"""Pydantic schemas for the A/B engine API."""
from typing import Literal

from pydantic import BaseModel, Field


class CampaignData(BaseModel):
    """Real impressions+clicks observed from a live campaign run."""

    impressions: int = Field(..., ge=0)
    clicks: int = Field(..., ge=0)


class CompareRequest(BaseModel):
    """Compare two creative variants. Neuro scores serve as priors; campaign data updates them."""

    score_a: int = Field(..., ge=0, le=100, description="Neuro engagement score for variant A")
    score_b: int = Field(..., ge=0, le=100, description="Neuro engagement score for variant B")
    campaign_a: CampaignData | None = Field(
        None,
        description="Live campaign data for A. If omitted, prediction is from neuro priors only.",
    )
    campaign_b: CampaignData | None = Field(
        None,
        description="Live campaign data for B. If omitted, prediction is from neuro priors only.",
    )
    prior_strength: float = Field(
        20.0,
        gt=0,
        le=200,
        description="How much weight to give the neuro prior, in equivalent-impressions units. "
        "Higher = trust the neuro score more. 20 ≈ 'mild informative prior'.",
    )


class CompareResponse(BaseModel):
    """Posterior comparison between variants A and B."""

    p_a_wins: float = Field(..., ge=0.0, le=1.0)
    p_b_wins: float = Field(..., ge=0.0, le=1.0)
    expected_lift_pct: float = Field(
        ...,
        description="Expected % lift of the winning variant over the loser. Negative if winner uncertain.",
    )
    credible_interval_95: tuple[float, float] = Field(
        ..., description="95% credible interval for the lift % (winner over loser)."
    )
    sample_size_to_significance: int = Field(
        ...,
        ge=0,
        description="Estimated additional impressions PER variant needed before P(winner) > 0.95. "
        "0 means significance already reached.",
    )
    verdict: Literal["a_wins", "b_wins", "uncertain"]
    posterior_a: dict
    posterior_b: dict
