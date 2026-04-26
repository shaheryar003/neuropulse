"""Modal deployment for the TRIBE-based NeuroPulse inference API.

Deploy:
    modal deploy modal_deploy.py

Live develop:
    modal serve modal_deploy.py

License: TRIBE v2 is CC-BY-NC-4.0. This deployment is for internal R&D and Meta-pitch demos only.
"""
from __future__ import annotations

import modal

# ============================================================
# Image bake — pre-installs deps AND downloads the Yeo7 atlas labels
# so the first request doesn't pay the atlas-fetch latency.
# ============================================================

inference_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        "git",
        "ffmpeg",        # video decoding for TRIBE inputs
        "libgl1-mesa-glx",
        "libglib2.0-0",
    )
    .pip_install(
        "fastapi>=0.110",
        "pydantic>=2.6",
        "torch>=2.2",
        "torchvision>=0.17",
        "transformers>=4.40",
        "Pillow>=10.2",
        "numpy>=1.26",
        "scipy>=1.12",
        "matplotlib>=3.8",
        "httpx>=0.27",
        "python-multipart>=0.0.9",
        "supabase>=2.4",
        "nibabel>=5.2",
        "nilearn>=0.10.4",
        "pandas>=2.2",
    )
    .pip_install("git+https://github.com/facebookresearch/tribev2.git")
    .run_commands(
        # Pre-fetch Yeo7 atlas labels at image-build time
        "mkdir -p /weights && cd /tmp && python -c \"import os; os.environ.setdefault('MODEL_WEIGHTS_DIR', '/weights')\" || true",
    )
    .add_local_python_source("app")
    .env({"MODEL_WEIGHTS_DIR": "/weights"})
)


app = modal.App("neuropulse-inference", image=inference_image)


@app.function(
    gpu="A10G",                     # 24GB VRAM — minimum for TRIBE v2 (LLaMA + V-JEPA2 + Wav2Vec-BERT)
    secrets=[modal.Secret.from_name("neuropulse-secrets")],
    timeout=900,                    # Long-form videos can take a few minutes
    scaledown_window=600,           # Keep warm 10 min after last request
    min_containers=0,               # Set to 1 during pitch days to remove cold starts
)
@modal.asgi_app()
def fastapi_app():
    """ASGI wrapper exposing app.main:app as a Modal web endpoint."""
    # Ensure atlas labels exist on the worker — download on first cold start if not baked
    from pathlib import Path

    from app.models.atlas import _default_labels_path, download_yeo_atlas

    if not _default_labels_path().exists():
        download_yeo_atlas()

    from app.main import app as fastapi_app

    return fastapi_app


@app.function(image=inference_image, gpu="A10G", timeout=900)
def warmup_and_test(video_url: str) -> dict:
    """One-shot smoke test against a real video URL.

    Invoke:
        modal run modal_deploy.py::warmup_and_test --video-url "https://.../sample.mp4"
    """
    from app.models.atlas import _default_labels_path, download_yeo_atlas
    from app.pipeline import Pipeline

    if not _default_labels_path().exists():
        download_yeo_atlas()

    pipe = Pipeline(device="cuda")
    pipe.warmup()
    prediction = pipe.tribe.predict_video_url(video_url)
    result, _renders = pipe._run_with_prediction(prediction)
    return {
        "composite_engagement_score": result["composite_engagement_score"],
        "metrics": result["metrics"],
        "prediction_summary": result["prediction_summary"],
        "inference_ms": result["inference_ms"],
    }
