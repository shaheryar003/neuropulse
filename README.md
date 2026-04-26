# NeuroPulse

Neuro-predictive intelligence for advertising creative. Upload an ad image, get a predicted engagement score, attention heatmap, aesthetic rating, and emotional valence in ~5 seconds. Run two variants through the Bayesian A/B engine to predict the winner before launch and update with real campaign data after.

## Repo layout

```
neuropulse/
├── inference-api/     FastAPI + Modal — saliency, aesthetic, emotion, scorer pipeline
├── ab-engine/         FastAPI — Bayesian A/B (Beta-Binomial)
├── web/               Next.js 14 — auth, upload, dashboard, billing
└── supabase/          DB schema + migrations
```

## Local setup

### Prerequisites

- Python 3.11+
- Node 20+
- A [Supabase](https://supabase.com) project
- A [Modal](https://modal.com) account
- A [Stripe](https://stripe.com) test account
- A [Resend](https://resend.com) account

### 1. Supabase

Create a new project. Run the migration:

```bash
psql $SUPABASE_DB_URL -f supabase/migrations/001_initial_schema.sql
```

Enable Storage. Create two public buckets: `creatives` and `heatmaps`.

In Auth → enable Email provider, configure magic link.

### 2. Inference API (Modal)

```bash
cd inference-api
pip install -e .
modal token new       # one-time
modal secret create neuropulse-secrets \
  SUPABASE_URL=... \
  SUPABASE_SERVICE_KEY=... \
  API_KEY=$(openssl rand -hex 32)
modal deploy modal_deploy.py
```

This prints the deployed URL. Save it as `INFERENCE_API_URL` in your web `.env.local`.

### 3. A/B Engine

```bash
cd ab-engine
pip install -e .
modal deploy app/main.py    # OR run locally: uvicorn app.main:app
```

### 4. Web

```bash
cd web
cp .env.local.example .env.local
# fill in Supabase, Stripe, Modal URLs, API keys
npm install
npm run dev
```

Visit `http://localhost:3000`.

### 5. Stripe

Create one product: **Entry — $299/mo**. Set the price ID in your `.env.local` as `STRIPE_PRICE_ID_ENTRY`.

For local webhook testing:
```bash
stripe listen --forward-to localhost:3000/api/stripe-webhook
```

## Running the pipeline locally (no Modal)

```bash
cd inference-api
python -m app.pipeline path/to/ad.jpg
```

Prints the JSON result and saves the heatmap PNG next to the input.

## Phase 1 Scope (MVP)

Image-only scoring · single-tenant dashboard · Bayesian A/B for two variants · Stripe Entry tier.

**Not in MVP**: video, audio, multi-client agency view, white-label, ad-platform integrations, RL layer, fine-tuned scorer, PDF generation.

See `docs/ARCHITECTURE.md` and `docs/MODEL_LICENSES.md` (in the parent `mvp/` folder) for the full architectural decisions and license audit.

## License

Proprietary. Not for redistribution.
