# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project context (read this first)

**NeuroPulse is a Meta-pitch project, not an agency SaaS.** The codebase originally targeted a B2B SaaS for ad agencies (saliency + CLIP + heuristic scoring) but pivoted to demo Meta's TRIBE v2 brain-encoding model applied to advertising. The product is "the neuroscience-translation layer for TRIBE v2."

- **TRIBE v2** (license: CC-BY-NC-4.0) is the model. CC-BY-NC permits internal R&D and demoing to the model's authors (Meta) — what we're doing — but NOT commercial SaaS to third parties. If the project pivots back to commercial SaaS, the model layer must change.
- The hardware constraint is real: TRIBE needs ~16-24GB VRAM. Local dev on consumer GPUs (e.g., 8GB) cannot run it. Use cloud GPU (Lightning AI Studios for dev, Modal for production).
- The CC-BY-NC blocker means **don't add commercial-licensing features (Stripe checkout, plans, quotas)** unless someone explicitly says Meta has opened the license. Existing Stripe code remains for that contingency but is not the active product.

## Architecture

Three independently-deployable components:

1. **`inference-api/`** — FastAPI on Modal (GPU). Pipeline: `video URL → TRIBE v2 → Yeo7 cortical parcellation → 6 advertiser metrics → composite engagement score` plus 3 server-rendered PNGs (cortical brain plot, network timecourses, metrics radar). The pipeline is composed in `app/pipeline.py`; the data flow goes one direction with no shared mutable state.

2. **`ab-engine/`** — Stateless FastAPI service. Bayesian A/B math (Beta-Binomial conjugate updating). Takes the composite engagement score as a prior and updates with real campaign impressions/clicks. No persistence. No model weights. Pure NumPy/SciPy. Deployable independently.

3. **`web/`** — Next.js 14 frontend on Vercel. Holds the API keys for both backend services and proxies user requests through `app/api/score/route.ts` and `app/api/compare/route.ts`. Auth via Supabase magic link; data via Supabase tables (RLS enforced per-user). Storage buckets: `creatives` (uploaded videos) and `heatmaps` (rendered PNGs from inference-api).

### The IP layer — `inference-api/app/models/atlas.py`

This file is the substantive proprietary value of the project. It does two things:

- **Yeo7 parcellation** — loads vertex→network labels for the fsaverage5 cortical mesh and aggregates TRIBE's `(T, ~20484)` activation tensor to per-network timeseries.
- **Advertiser metrics mapper** — projects 7 network timeseries → 6 advertiser metrics (`attention_sustainment`, `emotional_arousal`, `memorability`, `reward_anticipation`, `social_processing`, `thumb_stop_power`). The network→metric mapping (which networks contribute to which metric, with what weight, and which temporal aggregation) is a documented hypothesis. The numeric weights and `normalization_center`/`normalization_scale` constants are heuristics calibrated against ground truth ad performance, not derived from first principles.

When tuning metrics, change `ADVERTISER_METRICS` at the top of the file. The structure is data; the pipeline picks them up automatically. The `composite_engagement_score` weights at the bottom of the file are the higher-level aggregation that feeds the Bayesian A/B engine.

### Auth model

- **Frontend ↔ Next.js routes**: Supabase JWT (cookie-based session, set by middleware).
- **Next.js routes ↔ inference-api / ab-engine**: shared `X-API-Key` header. Server-side only. Frontend never sees this key.
- **inference-api ↔ Supabase Storage**: Supabase service role key (bypasses RLS to write heatmaps).

When adding a new endpoint to either Python service, protect it with `Depends(get_api_key)`. The pattern is in `inference-api/app/main.py` and `ab-engine/app/main.py`.

### Modal deployment pattern

`inference-api/modal_deploy.py` bakes the Yeo7 atlas labels into the image so cold starts don't pay the atlas-fetch latency. The atlas download itself (`download_yeo_atlas` in `app/models/atlas.py`) pulls `.annot` files from the Yeo lab's CBIG GitHub and parses them with nibabel. If those URLs ever break, the function raises a clear error with manual-fallback instructions.

`min_containers` is currently 0 (cold starts each idle period). Set to 1 during pitch days to eliminate cold-start latency at the cost of ~$1.10/hr keep-warm.

### Dead code (do not extend)

`inference-api/app/models/saliency.py`, `aesthetic.py`, `emotion.py`, `scorer.py`, and `app/strengths.py` are remnants from the pre-pivot architecture. Nothing imports them. Do not extend or maintain them. They can be deleted at the user's discretion. If new feature work needs an open-source alternative to TRIBE, build it fresh; don't resuscitate this code.

## Commands

### Python services

Both services use `pyproject.toml` with editable installs.

```bash
# inference-api
cd inference-api
python -m venv .venv && source .venv/Scripts/activate    # Windows bash
pip install -e ".[dev]"
pip install git+https://github.com/facebookresearch/tribev2.git    # TRIBE itself
python -m app.models.atlas download                       # Fetch Yeo7 labels (one-time)

# Run the full pipeline locally on a video (needs ~24GB VRAM)
python -m app.pipeline path/to/ad.mp4

# Tests — atlas/metrics tests run on CPU; full TRIBE pipeline test is gated
PYTHONPATH=. python -m pytest tests/ -v
PYTHONPATH=. python -m pytest tests/test_pipeline.py::test_metrics_mapper_outputs_in_zero_hundred -v

# Modal deploy
modal token new                       # one-time
modal secret create neuropulse-secrets API_KEY=... SUPABASE_URL=... SUPABASE_SERVICE_KEY=...
modal deploy modal_deploy.py
modal run modal_deploy.py::warmup_and_test --video-url "https://..."
```

```bash
# ab-engine
cd ab-engine
python -m venv .venv && source .venv/Scripts/activate
pip install -e ".[dev]"

# Local dev server
API_KEY=local python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --log-level warning

# Tests — pure Python, no GPU
python -m pytest tests/ -v
```

### Web

```bash
cd web
cp .env.local.example .env.local            # then fill in Supabase, Stripe, INFERENCE_API_URL, etc.
npm install
npm run dev                                  # http://localhost:3000
npm run build
npm run lint
npm run type-check
```

### Supabase migrations

```bash
psql $SUPABASE_DB_URL -f supabase/migrations/001_initial_schema.sql
```

The migration also wires triggers: auto-create profile on signup, increment `scores_used_this_period` on score insert, auto-bump `updated_at` on profile update. After running, in the Supabase console, manually create two **public** Storage buckets: `creatives` and `heatmaps`.

## Important patterns

- **Adding a new advertiser metric**: append an entry to `ADVERTISER_METRICS` in `inference-api/app/models/atlas.py`. Update `composite_engagement_score` weights to include it. Update tests in `inference-api/tests/test_pipeline.py`. Update the schema's expected metric set if hard-coded anywhere (currently just the test).

- **Schema evolution between inference-api and web**: the API contract is `inference-api/app/schemas.py` (Pydantic) ↔ `web/lib/types.ts` (TypeScript). When changing one, change the other in the same commit. The web frontend is currently mismatched with the post-pivot inference schema (it expects images and emotion/aesthetic; inference returns videos and 6 cortical metrics) — this gap is known and intentional, to be fixed when the web frontend is updated.

- **Metric calibration loop**: real calibration uses ground-truth ad performance (Meta Ads Library impressions/likes/dwell). Synthetic-data tests in `tests/test_pipeline.py` only verify the pipeline is *sensitive* to input variation, not that the metric values are correct. Don't over-fit tests to specific values.

- **Modal image cold-start**: the first deploy bakes a ~5GB image with TRIBE + nilearn + matplotlib + atlas labels. Subsequent deploys (code-only changes) reuse the layers and complete in ~30s. Avoid changing `pip_install` calls casually.

- **Heatmap rendering uses matplotlib `Agg` backend** (set explicitly in `app/models/visualization.py`). Don't import pyplot before the backend is set.

## Out-of-band context

The repo's parent folder (`C:\Users\Shaheryar\Desktop\Personal\Neuro\`) holds the original strategy document (`NeuroPulse-Strategy-v2.html`) and a `mvp/` folder with planning artifacts (`ARCHITECTURE.md`, `BUILD_PLAN.md`, `MODEL_LICENSES.md`). Those documents predate the post-pivot model-stack rewrite — treat them as historical context, not authoritative spec. The authoritative spec is this CLAUDE.md plus the code itself.
