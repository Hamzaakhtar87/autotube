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
- ~~The FastAPI backend (`backend/app/`) is still the API. The plan puts the API in
  Next.js with Supabase auth; that migration isn't scheduled to a phase yet and
  should be decided before Phase 2 (key vault) so the vault isn't built twice.~~
  **Resolved 2026-09-16 (Phase 2): the API stays in FastAPI.** Auth, all routes
  and the test suite are there, and the decrypt side runs in Python inside the
  Actions runner anyway. A Next.js/Supabase-auth migration is not scheduled.
- `backend/core/` (the old pipeline: Gemini/Groq script, Edge TTS, Pexels, FFmpeg)
  is kept but not wired to anything. Phases 3–6 replace it stage by stage.
- GitHub disables cron workflows after 60 days without repo activity. Not a
  problem while phases are landing; worth a calendar note after Phase 10.
- `next@14.0.4` has a published security advisory; upgrade when touching the
  frontend in Phase 7.

---

## Phase 1 — Niche profile system

**Status: done.** 2026-09-14. Data layer only; no pipeline stage reads it yet.

### Decision made this phase

Canonical accessor is **Python**, in the backend. The plan makes the pipeline
stages the primary consumer of the profile and those run in the Actions
runner on the Python engine the plan kept. The Next.js side only needs the
list for the create-job form; a thin TypeScript reader against the same table
lands in Phase 7. The table is the contract between the two.

### What was built

- **Table `niche_profiles`** — Alembic migration `d4e5f6a7b8c9`, applied to
  Supabase (revision now `d4e5f6a7b8c9`). One column per Appendix A field, all
  `NOT NULL`; `pacing` is JSON with the two keys. Check constraints on
  `id` (snake_case), `aspect_default` (`9:16` | `16:9`), and `hook_style`
  (the six values Appendix A uses). RLS on, public `SELECT` for `anon` and
  `authenticated` (the create-job UI needs the list), writes only via the
  service role or migrations.
- **Data file** `backend/app/niches/profiles.json` — the six profiles from
  Appendix A copied verbatim. `true_crime_narration` and
  `whatif_hypothetical` are final. `tech_explainer`, `motivational`,
  `documentary`, `listicle` still carry their `PLACEHOLDER —` prompt text
  exactly as the plan wrote them; nothing was invented to replace it.
- **Seeder** `python -m app.niches.seed` — idempotent upsert from the JSON
  file. Run against Supabase: 6 rows written, verified by SQL and by an
  anonymous PostgREST read.
- **Typed accessor** `app/niches/accessor.py`:
  `get_niche_profile(id, db) -> NicheProfile` and
  `list_niche_profiles(db)`. `NicheProfile` is a frozen Pydantic model with
  `HookStyle` and `AspectRatio` enums and a nested `Pacing`; `extra="forbid"`
  and every field required. Unknown id → `NicheProfileNotFound` (message
  contains the id). Stored row failing validation → `NicheProfileInvalid`.
  Never `None`, never a default, never partial. `profile.is_placeholder`
  flags the four stubs.
- ORM row `NicheProfileRow` in `models.py` (storage only; pipeline code goes
  through the accessor).

### Tests (all green)

`backend/tests/test_niche_profiles.py` — 29 tests:

1. each of the 6 seeded ids returns an object with every schema field present,
   non-null, correctly typed (enums, nested `Pacing`, real `bool`), and equal
   to the data file verbatim; the two finals / four placeholders split is
   asserted; list returns all six; the profile is immutable;
2. four bad ids (unknown, near-miss, wrong case, empty) raise
   `NicheProfileNotFound` with the id in the message and never fall through to
   a value;
3. six corruptions of a raw row (nested key missing, blank, out of range, bad
   enum ×2, blank required string) raise `NicheProfileInvalid` — or, on
   Postgres, are refused by the check constraints before they can be stored;
   the accessor's output has exactly the schema's keys, no more, no fewer.

Run on SQLite (default) → 29 passed. Run against the live Supabase database
(`TEST_DATABASE_URL` = direct URL) → 29 passed, no residue rows. Full backend
suite → 55 passed.

```bash
cd backend && pytest tests/test_niche_profiles.py -v
```

### Still rough / carry-forward

- ~~The four stub profiles need hand-written prompt text.~~ **Done
  2026-09-16.** Hamza supplied final `script_system_prompt`,
  `visual_prompt_modifiers`, `voice_tone`, `music_mood`, and `caption_style`
  for `tech_explainer`, `motivational`, `documentary`, `listicle`; loaded
  verbatim into `profiles.json`, reseeded to Supabase (6 rows updated), no
  PLACEHOLDER text remains anywhere. The two locked profiles are unchanged.
  The placeholder test now asserts that *no* profile carries PLACEHOLDER
  copy, so a regression to stub text fails the suite. Full suite 55 passed;
  niche tests 29 passed on SQLite and on the live Supabase DB.
- Postgres access: both URLs in the repo's `.env` connect (session pooler 5432
  for Alembic/seeding/tests, transaction pooler 6543 for the app). One earlier
  6543 attempt failed psycopg2's startup handshake; it did not reproduce, so
  treat it as transient unless it shows up again. `.env.local` was synced to
  the same corrected `DIRECT_URL`.

---

## Phase 2 — BYOK key vault

**Status: done.** 2026-09-16. A key saved in Settings is validated live against
the provider before it is stored, stored only as ciphertext the API cannot open,
and no route outside job execution can read it back.

### Decisions made this phase

- **API stays in FastAPI** (closes the Phase 0 carry-forward above).
- **Encryption: libsodium sealed box (X25519 + XSalsa20-Poly1305) via PyNaCl,
  not the existing Fernet helper.** The API holds only the *public* key
  (`VAULT_PUBLIC_KEY`); the private key lives only in the GitHub Actions secret
  `VAULT_PRIVATE_KEY`. So "no code path outside job execution can decrypt" is a
  property of where the key material is, not a promise about who calls which
  function. Rejected: Fernet-from-`SECRET_KEY` (whoever can encrypt can decrypt,
  and it is the login-signing secret), Supabase Vault (secrets and the means to
  open them in the same DB, readable by the service role), cloud KMS (paid).
  Trade-off accepted: lose the private key → every stored key is unreadable and
  users re-enter them.
- Each ciphertext is a JSON envelope `{v, user_id, provider, secret}`; the
  decrypt side refuses an envelope whose binding doesn't match the row it came
  from, so copying a ciphertext onto another user/provider row is useless.
- A key whose test comes back **rate limited is saved with a warning**; every
  other non-`ok` result (invalid, no credit, no permission, timeout, network,
  unexpected) is refused with a 400 and nothing is written.
- Provider assumptions (confirmed): Veo = a Gemini API (AI Studio) key that
  lists a `veo-*` model; Kling = access key + secret key pair signed into a
  30-minute HS256 JWT; Seedance = international BytePlus ModelArk endpoint.

### What was built

- **Table `provider_keys`** — migration `e5f6a7b8c9d0`, applied to Supabase
  (revision now `e5f6a7b8c9d0`). `(user_id, provider)` unique, check constraint
  on the 7 provider names, `ciphertext`, `key_version`, `last_tested_at`,
  `last_test_status`. RLS on with **no policies** and `REVOKE ALL … FROM anon,
  authenticated`, so the public anon key gets nothing through PostgREST.
- **`backend/app/vault/`** (API side, encrypt-only): `providers.py` (enum,
  labels, credential fields per provider), `seal.py` (`seal_provider_secret`;
  imports `PublicKey`/`SealedBox` only), `testers.py` (one minimal real call per
  provider, 10 s timeout, results mapped to our own wording — provider error
  text is never passed through because some providers echo the key).
- **Test calls per provider:** Anthropic `GET /v1/models`; OpenAI `GET
  /v1/models`; Groq `GET /openai/v1/models`; Gemini `GET /v1beta/models` with
  the key in the `x-goog-api-key` header, never the URL; Veo = same + requires a
  `veo-*` model; Kling `GET api-singapore.klingai.com/account/costs`
  (documented free, QPS ≤ 1) with service codes 1000–1004 → invalid,
  1100–1102 → no credit, 1103 → no permission, 1302/1303 → rate limited;
  Seedance `GET ark.ap-southeast.bytepluses.com/api/v3/contents/generations/tasks?page_num=1&page_size=1`.
- **Routes** (`backend/app/api/keys.py`, all require login):
  `GET /keys` (configured / last test status+time per provider — never the
  value, never the ciphertext, no prefix or last-4), `POST /keys/{provider}/test`
  (stores nothing), `PUT /keys/{provider}` (re-tests server-side — the browser's
  "test passed" is not trusted — then seals and upserts), `DELETE /keys/{provider}`.
  Keys are `pydantic.SecretStr` in the request model.
- **`POST /config/keys` deleted.** It took no auth and wrote submitted keys
  into `os.environ`. Its test now asserts the route is gone.
- **Custom 422 handler** in `main.py`: FastAPI's stock validation error echoes
  the offending `input` back in the response body; ours returns only
  `loc/msg/type`.
- **Decrypt path** — `backend/runner/vault_decrypt.py`, outside the `app`
  package. `open_provider_secret(ciphertext, expected_user_id,
  expected_provider)` reads `VAULT_PRIVATE_KEY` and raises
  `VaultPrivateKeyUnavailable` / `VaultCiphertextInvalid` /
  `VaultBindingMismatch` (messages carry no key material). Its only importer is
  `runner/provider_keys.py::load_provider_key(user_id, provider, db)`, which
  Phase 6 wires into the pipeline. Nothing under `app/` imports `runner`.
- **Settings UI** — `frontend/components/api-keys-card.tsx`, mounted on the
  Settings page: seven rows (Kling has two inputs), status badge with last test
  result and date, password inputs that are never pre-filled, **Test key**,
  **Test & save** / **Test & replace**, **Delete** (with confirm), inline
  result line with our wording. `npm run build` clean.
- `requirements.txt`: `pynacl==1.5.0`, `respx==0.21.1` (tests).
  `.env.example`: `VAULT_PUBLIC_KEY` with generation instructions.

### Tests (all green)

Full backend suite: **256 passed, 0 skipped** (was 55). Frontend build clean.

1. **Encryption round-trip** — `tests/test_vault_crypto.py` (9 tests): seal →
   open returns the original for single-key and Kling two-field credentials;
   ciphertext is randomised and contains no plaintext; wrong private key,
   user/provider binding mismatch, tampered byte, non-base64 all raise; open
   refuses when `VAULT_PRIVATE_KEY` is absent; error messages contain no key
   material; the envelope shape is exactly `{v, user_id, provider, secret}`.
2. **Nothing leaks** — `tests/conftest.py` records, for the *entire* run, every
   log record at DEBUG level, every captured stdout/stderr chunk, every API
   response body and header, and the raw `provider_keys` column, then greps all
   of it for the three planted credential values (`tests/planted.py`) in
   `pytest_sessionfinish`; a hit fails the session with a `KEY LEAK DETECTED`
   banner. All provider HTTP is mocked with respx and every mocked error body
   deliberately echoes the planted key. `tests/test_zz_key_leak_sweep.py` runs
   last and reports the same sweep as a visible test. Last run: 1,647 log
   records, 434 API responses, 0 hits. **Mutation check:** a temporary test that
   logged the planted key made the run exit 1 with the banner — the sweep is
   not vacuous.
3. **Every route** — `tests/test_vault_route_sweep.py`: enumerates the app's
   routes from `app.routes` and pins them to a hard-coded list (a new route
   fails the test until added). A user saves all 7 planted keys; then each of
   the 60 registered (method, path) entries — 47 pre-existing routes, the 4 new
   `/keys` routes, the 8 auto-generated docs routes (`/docs`, `/redoc`,
   `/openapi.json`, `/docs/oauth2-redirect`, GET+HEAD) and the static `/output`
   mount — is called as the key's owner and as an admin (120 calls); no
   response body or header may contain a planted key or a stored ciphertext,
   and none may 500. Plus: `GET /keys` has no secret-shaped fields; no
   response schema in `openapi.json` has a key-shaped property; only
   `runner/provider_keys.py` imports `runner.vault_decrypt`; nothing under
   `app/` imports `runner` or contains `PrivateKey`/`SecretBox`;
   `load_provider_key` refuses in the API process and round-trips all 7 with
   the runner's key; and a **live** PostgREST request to Supabase with the anon
   key gets nothing from `provider_keys`.

Also run against the live Supabase Postgres (`TEST_DATABASE_URL=$DIRECT_URL`,
crypto + keys API + sweep): 72 passed, 0 residue rows, 0 test users left.

```bash
cd backend
rm -f test_autotube.db && python -m pytest -q -p no:cacheprovider -W ignore          # all 256
python -m pytest -q tests/test_vault_crypto.py                                        # (1) round-trip
python -m pytest -q tests/test_keys_api.py tests/test_zz_key_leak_sweep.py            # (2) leak sweep (banner at end)
python -m pytest -q tests/test_vault_route_sweep.py -v                                # (3) every route
cd ../frontend && npm run build
```

### Still rough / carry-forward

- **The production vault keypair has not been generated.** The API needs
  `VAULT_PUBLIC_KEY` in `.env` (and later in Vercel), and the runner needs the
  GitHub secret `VAULT_PRIVATE_KEY`. Until the public key is set, `PUT /keys/…`
  returns 503 ("Key vault is not configured") and stores nothing; tests use a
  throwaway per-run keypair. Generation one-liner is in `.env.example`.
  Hamza does this by hand so the private key never passes through a tool.
- The runner has nothing reading `VAULT_PRIVATE_KEY` yet; `run-job.yml` gets
  `env: VAULT_PRIVATE_KEY: ${{ secrets.VAULT_PRIVATE_KEY }}` when Phase 6
  wires `load_provider_key` into the pipeline.
- `backend/app/core/config.py` calls `load_dotenv(...parent.parent.parent /
  ".env")`, which resolves to `backend/.env` — a file that doesn't exist — not
  the repo's `autotube/.env`. So the API only sees variables exported in the
  shell. Pre-existing; noticed because the Supabase live check had to read the
  repo `.env` itself. Fix when the API's env handling is next touched (Phase 6
  or 9), deliberately, since it changes what the local API picks up.
- The live-key check (real funded keys against all 7 providers) was skipped
  this phase by decision; the testers were verified against mocked responses
  shaped from each provider's documented error format. Run by hand once keys
  are funded: save each in Settings and watch the result line.
- `GET /config/status` still reports `gemini_key_configured` /
  `pexels_key_configured` from env vars for the legacy pipeline; harmless,
  goes away with `backend/core` in Phases 3–6.
