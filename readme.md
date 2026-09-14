# AutoTube

A free, bring-your-own-key automation tool that turns a topic + niche choice into a finished, niche-styled YouTube video: script, visuals, voice, music, captions. You supply the model API keys; AutoTube supplies the orchestration.

The thing that has to shine: a "true crime" video and a "what-if" video don't just have different words, they *look, cut, and sound* like different productions. Style lives in a niche profile object, not in `if` branches.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Next.js](https://img.shields.io/badge/Next.js-14-black)
![Supabase](https://img.shields.io/badge/Supabase-Postgres-3ECF8E)
![GitHub Actions](https://img.shields.io/badge/Compute-GitHub%20Actions-2088FF)
![License](https://img.shields.io/badge/License-MIT-yellow)

## Architecture

Zero-dollar stack. Every piece is a free tier, and there is no always-on worker process anywhere.

| Concern | Decision |
|---|---|
| Frontend + API | Next.js on Vercel |
| DB / Auth / Realtime | Supabase (free tier) |
| Heavy compute (script → video → assemble) | GitHub Actions, one run per job, triggered via `repository_dispatch` |
| Video / file storage | Cloudflare R2 (zero egress) |
| Queue / task runner | **None.** A `jobs` row is the queue; the Actions run is the worker |
| Containers | **None in production** |
| Video generation | Kling / Veo / Seedance via the user's own key |
| TTS | Only for niches where the video model's native narration isn't enough |

The full build plan, locked-in decisions, and phase gates are in [AUTOTUBE_CLAUDE_CODE_PLAN.md](../AUTOTUBE_CLAUDE_CODE_PLAN.md). What has actually shipped per phase is in [PROGRESS.md](PROGRESS.md).

The previous Celery + Redis + Docker Compose pipeline is preserved on the [`legacy/celery-docker-pipeline`](https://github.com/Hamzaakhtar87/autotube/tree/legacy/celery-docker-pipeline) branch for reference. Nothing on `main` depends on it.

## How a job runs

1. The API inserts a `jobs` row with status `pending`.
2. The API POSTs to GitHub's `repository_dispatch` endpoint with `event_type: "run-job"` and the job id in `client_payload`.
3. [`.github/workflows/run-job.yml`](.github/workflows/run-job.yml) picks it up. (Phase 0: it echoes the payload and exits. Phase 6: it runs the pipeline, streams `job_logs` rows to Supabase, uploads the result to R2, and marks the job complete.)
4. The frontend watches `job_logs` over Supabase Realtime.

A second workflow, [`.github/workflows/supabase-keepalive.yml`](.github/workflows/supabase-keepalive.yml), queries the database every 5 days so the free-tier project never auto-pauses.

## Project structure

```
autotube/
├── .github/workflows/
│   ├── run-job.yml               # repository_dispatch "run-job" → the job runner
│   └── supabase-keepalive.yml    # cron ping so Supabase doesn't pause
├── backend/
│   ├── app/                      # FastAPI application (being migrated into Next.js)
│   │   ├── api/                  # REST endpoints
│   │   ├── models/               # SQLAlchemy models
│   │   └── services/
│   │       └── dispatch.py       # fires repository_dispatch for a job
│   ├── core/                     # Video generation engine (runs inside Actions)
│   └── requirements.txt
├── frontend/                     # Next.js app (Vercel, root directory = frontend)
├── .env.example
└── PROGRESS.md
```

## Setup

### Prerequisites

- Node 20+ and Python 3.12
- A Supabase project, a Vercel project, a Cloudflare R2 bucket, and a GitHub token with `repo` scope
- Model API keys of your own (Gemini / Groq today; Kling / Veo / Seedance from Phase 4)

### 1. Configure

```bash
git clone https://github.com/Hamzaakhtar87/autotube.git
cd autotube
cp .env.example .env
# fill in Supabase, R2, and GitHub values
```

### 2. Run the frontend

```bash
cd frontend
npm ci
npm run dev
```

### 3. Run the backend (until the API moves into Next.js)

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### 4. Fire a job run by hand

```bash
curl -X POST https://api.github.com/repos/Hamzaakhtar87/autotube/dispatches \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_DISPATCH_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  -d '{"event_type":"run-job","client_payload":{"job_id":"test-123"}}'
```

Then watch it under the repo's **Actions** tab, or with `gh run list --workflow run-job.yml`.

## Tests

```bash
cd backend
pytest            # uses a throwaway SQLite file by default
TEST_DATABASE_URL=postgresql://... pytest   # or point at a Postgres instance
```

## License

MIT
