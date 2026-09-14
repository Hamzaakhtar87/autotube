# PROGRESS

Running log of what has actually shipped per phase of
[AUTOTUBE_CLAUDE_CODE_PLAN.md](../AUTOTUBE_CLAUDE_CODE_PLAN.md). Written after the
work, not before. If it isn't here, it isn't done.

---

## Phase 0 — Repo reset & scaffolding

**Status: done.** 2026-09-14. Commit `da5129d` on `main` (+ this file).

### What was removed from `main`

The old pipeline is preserved unchanged on branch
[`legacy/celery-docker-pipeline`](https://github.com/Hamzaakhtar87/autotube/tree/legacy/celery-docker-pipeline)
(cut from `main` at `75b397f` before any deletion). On `main`:

- Deleted: `docker-compose.yml`, `docker-compose.prod.yml`, `backend/Dockerfile`,
  `backend/Dockerfile.worker`, `frontend/Dockerfile`, both `.dockerignore` files,
  `backend/start.sh`, `backend/celerybeat-schedule` (a committed binary),
  `backend/app/worker.py` (the Celery app and `run_batch_task`).
- `celery` and `redis` dropped from `backend/requirements.txt`.
- `jobs.celery_task_id` column dropped: model field removed, new Alembic
  migration `c1d2e3f4a5b6` (the old `add_celery_task_id` migration file stays
  because later revisions chain off it). Applied to the Supabase DB, which now
  reports revision `c1d2e3f4a5b6`.
- Docker-only filesystem paths removed from active code: `/app/core` output dir
  in `main.py`, `/app/core` detection in `settings.py`, and a bare
  `from config import OUTPUT_DIR` in `videos.py` that only worked because the
  container put `core/` on `sys.path`. `OUTPUT_DIR` now lives in
  `app/core/config.py` (env `OUTPUT_DIR`, default `backend/core/output_v2`).
- Admin health check no longer pings Celery; it reports `job_runner:
  configured|unconfigured` based on dispatch credentials. Frontend admin page's
  "Redis (Celery)" card replaced by "Job Runner (GitHub Actions)".
- `next.config.js` no longer sets `output: 'standalone'` (container-only).
- Comment-level mentions in `auth.py`, `webhooks.py`, `stats.py`, both
  `config.py` files reworded.
- `readme.md`, `DEPLOYMENT_GUIDE.md`, `.env.example` rewritten for the new stack.
  `GTM_PLAYBOOK.md` had one Celery line, reworded.

Verification: no `docker|celery|redis` matches remain in any file reachable from
the app entrypoints. The only remaining matches are prose in `readme.md`,
`DEPLOYMENT_GUIDE.md`, and the `dispatch.py` docstring explaining what replaced
what, plus the untouched historical Alembic migration.

### What was stood up

- **Job dispatch.** `backend/app/services/dispatch.py` — `dispatch_job(job_id,
  payload)` POSTs `repository_dispatch` with `event_type: "run-job"`. Needs
  `GITHUB_REPO` + `GITHUB_DISPATCH_TOKEN`. `POST /jobs` calls it after inserting
  the row; on `DispatchError` the job is marked `FAILED` with a log line and the
  API returns 503. `POST /jobs/{id}/stop` just flips status (nothing to revoke;
  the Actions run is expected to check `job.status` between stages, Phase 6).
- **`.github/workflows/run-job.yml`** — triggers on `repository_dispatch`
  `types: [run-job]`, one job, echoes `client_payload` and exits 0. No pipeline
  logic.
- **`.github/workflows/supabase-keepalive.yml`** — cron `0 9 */5 * *` (days
  1,6,11,16,21,26,31 → max gap 5 days across month boundaries) plus
  `workflow_dispatch`. Does a real `SELECT` through PostgREST on
  `public._keepalive` using repo secrets `SUPABASE_URL` and `SUPABASE_ANON_KEY`.
- **Supabase** — project `Autotube` (`yscqegzuxxzqasnoadcv`, ap-southeast-1)
  was already created; verified `ACTIVE_HEALTHY` via the management API. Added
  table `public._keepalive` (single row, RLS on, `anon` SELECT policy) and
  reloaded the PostgREST schema cache. Existing tables from the old backend are
  untouched.
- **Vercel** — project `autotube` (root directory `frontend`, Next.js preset,
  production URL autotube-beta.vercel.app) already existed. Linked at the repo
  root via `.vercel/project.json` (gitignored). No env vars were added to Vercel
  yet; that happens when the API moves into Next.js.
- **Cloudflare R2** — bucket `autotube-storage` already existed; verified the
  access key pair can list it (SigV4 `ListObjects` → 200). Nothing written to it.
- **GitHub repo secrets** set: `SUPABASE_URL`, `SUPABASE_ANON_KEY`.
- **Local `.env`** written from the values you supplied (gitignored, not
  committed). `GITHUB_DISPATCH_TOKEN` is currently the `gh` CLI OAuth token.

### Tests (all green)

- Backend: `cd backend && pytest` → **26 passed**. Runs against a throwaway
  SQLite file by default (`TEST_DATABASE_URL` overrides). Two test-infra fixes
  were needed that had nothing to do with the strip: the in-memory auth rate
  limiter (10/min per IP) tripped mid-suite, so `conftest.py` now resets the
  limiters per test; and the job tests reused one user, which the "1 active job
  on free tier" rule rejects, so each job test now registers its own user. New
  test: dispatch failure → 503 and job `FAILED`.
- Frontend: `npm run build` → clean (14 routes).
- **Phase gate — CI smoke test.** Three real Actions runs, all `success`:
  - `repository_dispatch` from the raw API call (same call as the curl below),
    payload `{"job_id":"test-123","source":"curl-smoke"}` echoed:
    https://github.com/Hamzaakhtar87/autotube/actions/runs/34872854273
  - `repository_dispatch` from `dispatch_job()` in the API code, payload
    `{"job_id":9001,"test_mode":true,...}` echoed:
    https://github.com/Hamzaakhtar87/autotube/actions/runs/34872868466
  - Keepalive via `workflow_dispatch`, `HTTP 200` from Supabase:
    https://github.com/Hamzaakhtar87/autotube/actions/runs/34872871197

### Still rough / carry-forward

- **The Postgres password in `.env.local` is rejected by the Supabase pooler**
  (`password authentication failed for user "postgres"`). Everything DB-side in
  this phase went through the management API instead, including the column drop
  and Alembic stamp. Reset the DB password in the Supabase dashboard and update
  `DATABASE_URL` / `DIRECT_URL` in `.env` before Phase 1 needs `alembic upgrade`.
- The FastAPI backend (`backend/app/`) is still the API. The plan puts the API in
  Next.js with Supabase auth; that migration isn't scheduled to a phase yet and
  should be decided before Phase 2 (key vault) so the vault isn't built twice.
- `backend/core/` (the old pipeline: Gemini/Groq script, Edge TTS, Pexels, FFmpeg)
  is kept but not wired to anything. Phases 3–6 replace it stage by stage.
- GitHub disables cron workflows after 60 days without repo activity. Not a
  problem while phases are landing; worth a calendar note after Phase 10.
- `next@14.0.4` has a published security advisory; upgrade when touching the
  frontend in Phase 7.
