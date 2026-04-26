"""Pydantic schemas for the TRIBE-based inference API."""
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class ScoreRequest(BaseModel):
    video_url: HttpUrl = Field(..., description="Public or signed URL to the video creative (mp4, mov, webm, m4v)")
    user_id: str = Field(..., description="Supabase user id; used for storage scoping and quota tracking")
    score_id: str | None = Field(None, description="Optional pre-generated score id; server generates one if omitted")


class MetricValue(BaseModel):
    value: int = Field(..., ge=0, le=100)
    raw: float
    description: str


class PredictionSummary(BaseModel):
    model_version: str
    n_timesteps: int
    n_vertices: int
    duration_sec: float
    sampling_rate_hz: float


class ScoreResponse(BaseModel):
    id: str
    composite_engagement_score: int = Field(..., ge=0, le=100)
    metrics: dict[str, MetricValue]
    brain_image_url: str
    timecourses_image_url: str
    radar_image_url: str
    network_timeseries: dict[str, list[float]] = Field(
        ..., description="Per-network activation timeseries — for client-side custom plotting"
    )
    prediction_summary: PredictionSummary
    inference_ms: int


class HealthResponse(BaseModel):
    status: Literal["ok", "warming"]
    model_versions: dict[str, str]
