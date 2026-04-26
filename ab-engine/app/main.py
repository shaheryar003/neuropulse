"""FastAPI app for the Bayesian A/B engine.

Stateless service. Exposes one endpoint: POST /compare.

Deployment options:
- Modal: `modal serve app/main.py` (requires a Modal-aware wrapper, see README)
- Vercel serverless: works as-is via FastAPI -> Mangum or Vercel's Python runtime
- Self-hosted: `uvicorn app.main:app --host 0.0.0.0 --port 8001`
"""
from __future__ import annotations

import os
import secrets

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader

from .bayesian import (
    build_posterior,
    estimate_sample_size_to_significance,
    lift_distribution,
    p_a_beats_b,
    verdict,
)
from .schemas import CompareRequest, CompareResponse


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_api_key(provided: str | None = Depends(api_key_header)) -> str:
    expected = os.environ.get("API_KEY")
    if not expected:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "API_KEY env var not configured"
        )
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing API key")
    return provided


app = FastAPI(title="NeuroPulse A/B Engine", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post(
    "/compare",
    response_model=CompareResponse,
    dependencies=[Depends(get_api_key)],
)
async def compare(req: CompareRequest) -> CompareResponse:
    post_a = build_posterior(
        score=req.score_a,
        impressions=req.campaign_a.impressions if req.campaign_a else 0,
        clicks=req.campaign_a.clicks if req.campaign_a else 0,
        prior_strength=req.prior_strength,
    )
    post_b = build_posterior(
        score=req.score_b,
        impressions=req.campaign_b.impressions if req.campaign_b else 0,
        clicks=req.campaign_b.clicks if req.campaign_b else 0,
        prior_strength=req.prior_strength,
    )

    p_a = p_a_beats_b(post_a, post_b)
    lift_med, lift_ci = lift_distribution(post_a, post_b)
    n_extra = estimate_sample_size_to_significance(post_a, post_b)
    v = verdict(p_a)

    # Express lift as winner-over-loser, regardless of which side won
    if v == "b_wins":
        lift_med = -lift_med
        lift_ci = (-lift_ci[1], -lift_ci[0])

    return CompareResponse(
        p_a_wins=p_a,
        p_b_wins=1.0 - p_a,
        expected_lift_pct=round(lift_med, 2),
        credible_interval_95=(round(lift_ci[0], 2), round(lift_ci[1], 2)),
        sample_size_to_significance=n_extra,
        verdict=v,
        posterior_a={
            "alpha": round(post_a.alpha, 3),
            "beta": round(post_a.beta, 3),
            "mean_ctr": round(post_a.mean, 5),
            "ci_95": [round(x, 5) for x in post_a.credible_interval()],
        },
        posterior_b={
            "alpha": round(post_b.alpha, 3),
            "beta": round(post_b.beta, 3),
            "mean_ctr": round(post_b.mean, 5),
            "ci_95": [round(x, 5) for x in post_b.credible_interval()],
        },
    )
