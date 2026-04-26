"""FastAPI app — wraps the TRIBE pipeline with auth + Supabase storage for renders.

Auth: shared API key in `X-API-Key`. Held only by the Next.js server-side code.
Storage: brain/timecourses/radar PNGs uploaded to Supabase `heatmaps/` bucket. Public URLs returned.
"""
from __future__ import annotations

import os
import secrets
import uuid

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security.api_key import APIKeyHeader

from .pipeline import Pipeline
from .schemas import (
    HealthResponse,
    MetricValue,
    PredictionSummary,
    ScoreRequest,
    ScoreResponse,
)


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def get_api_key(provided: str | None = Depends(api_key_header)) -> str:
    expected = os.environ.get("API_KEY")
    if not expected:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "API_KEY env var not configured on server"
        )
    if not provided or not secrets.compare_digest(provided, expected):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing API key")
    return provided


_pipeline: Pipeline | None = None


def get_pipeline() -> Pipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = Pipeline(device="cuda")
        _pipeline.warmup()
    return _pipeline


app = FastAPI(title="NeuroPulse Inference API (TRIBE v2)", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten before any non-internal use
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    pipe = get_pipeline()
    return HealthResponse(status="ok", model_versions=pipe.model_versions())


@app.post(
    "/score",
    response_model=ScoreResponse,
    dependencies=[Depends(get_api_key)],
)
async def score(req: ScoreRequest) -> ScoreResponse:
    pipe = get_pipeline()
    score_id = req.score_id or f"score_{uuid.uuid4().hex[:16]}"

    try:
        prediction = pipe.tribe.predict_video_url(str(req.video_url))
    except Exception as e:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"TRIBE inference failed: {e}"
        ) from e

    result, renders = pipe._run_with_prediction(prediction)

    urls = await _upload_renders(score_id, req.user_id, renders)

    metrics_typed = {
        name: MetricValue(**m) for name, m in result["metrics"].items()
    }

    return ScoreResponse(
        id=score_id,
        composite_engagement_score=result["composite_engagement_score"],
        metrics=metrics_typed,
        brain_image_url=urls["brain"],
        timecourses_image_url=urls["timecourses"],
        radar_image_url=urls["radar"],
        network_timeseries=result["network_timeseries"],
        prediction_summary=PredictionSummary(**result["prediction_summary"]),
        inference_ms=result["inference_ms"],
    )


async def _upload_renders(score_id: str, user_id: str, renders: dict[str, bytes]) -> dict[str, str]:
    """Upload all 3 PNGs to Supabase Storage `heatmaps/` bucket. Return public URLs."""
    from supabase import create_client

    supabase_url = os.environ["SUPABASE_URL"]
    supabase_key = os.environ["SUPABASE_SERVICE_KEY"]
    client = create_client(supabase_url, supabase_key)

    urls: dict[str, str] = {}
    for name, png_bytes in renders.items():
        path = f"{user_id}/{score_id}_{name}.png"
        client.storage.from_("heatmaps").upload(
            path,
            png_bytes,
            file_options={"content-type": "image/png", "upsert": "true"},
        )
        urls[name] = client.storage.from_("heatmaps").get_public_url(path)
    return urls
