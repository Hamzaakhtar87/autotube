# AutoTube: Zero-Dollar Deployment

Everything runs on free tiers and nothing is a long-running process.

| Component | Provider | Notes | Cost |
| :--- | :--- | :--- | :--- |
| Frontend + API (Next.js) | [Vercel](https://vercel.com) | Project `autotube`, root directory `frontend` | $0 |
| Database / Auth / Realtime | [Supabase](https://supabase.com) | 500 MB Postgres. Auto-pauses after 7 idle days, so a keepalive workflow pings it every 5 days | $0 |
| Job compute | GitHub Actions | One run per job via `repository_dispatch`. Free minutes are capped, fine for portfolio volume | $0 |
| Video / file storage | [Cloudflare R2](https://developers.cloudflare.com/r2/) | 10 GB, zero egress. A 24 h auto-delete sweep keeps it under the cap | $0 |

There is no Docker, Celery, Redis, Render, or Upstash in this stack. The old version of this guide lives on the `legacy/celery-docker-pipeline` branch.

## 1. Supabase

1. Create a project. Copy from **Project Settings → API**: project URL, publishable (anon) key, secret (service role) key.
2. Copy from **Project Settings → Database**: the transaction-pooler URL (port 6543) for the app and the session-pooler URL (port 5432) for migrations. URL-encode special characters in the password.
3. Put them in `.env` as `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`, `DIRECT_URL`.
4. The keepalive workflow reads a one-row table `public._keepalive` with an anon `SELECT` policy. Create it once:

```sql
create table if not exists public._keepalive (
  id smallint primary key default 1,
  pinged_at timestamptz not null default now(),
  constraint _keepalive_single_row check (id = 1)
);
insert into public._keepalive (id) values (1) on conflict (id) do nothing;
alter table public._keepalive enable row level security;
create policy keepalive_anon_select on public._keepalive for select to anon using (true);
grant select on public._keepalive to anon;
notify pgrst, 'reload schema';
```

## 2. GitHub

1. Repo secrets (**Settings → Secrets and variables → Actions**): `SUPABASE_URL`, `SUPABASE_ANON_KEY`. The keepalive workflow needs both.
2. A token that can fire `repository_dispatch`: classic PAT with `repo` scope, or fine-grained with **Contents: read and write**. Put it in `.env` as `GITHUB_DISPATCH_TOKEN`, with `GITHUB_REPO=Hamzaakhtar87/autotube`.
3. Workflows live in `.github/workflows/`. `repository_dispatch` only triggers workflows on the default branch, so they must be merged to `main` to fire.
4. GitHub disables scheduled workflows in a repo with no commits for 60 days. If the project goes quiet, re-enable it under **Actions**.

## 3. Cloudflare R2

1. Create a bucket (currently `autotube-storage`).
2. **R2 → Manage R2 API Tokens** → create a token with Object Read & Write on that bucket.
3. Put in `.env`: `CF_ACCOUNT_ID`, `CF_R2_ACCESS_KEY_ID`, `CF_R2_SECRET_ACCESS_KEY`, `CF_R2_BUCKET_NAME`, `CF_R2_ENDPOINT` (`https://<account-id>.r2.cloudflarestorage.com`).

## 4. Vercel

1. Import the repo, set **Root Directory** to `frontend`. Framework auto-detects as Next.js.
2. Add environment variables: `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, and (server-side only) `SUPABASE_SERVICE_ROLE_KEY`, `GITHUB_REPO`, `GITHUB_DISPATCH_TOKEN`, and the R2 variables as the API moves into Next.js.
3. Locally, `vercel link` in the repo root, then `vercel env pull` writes `.env.local` (gitignored).

## Smoke test

```bash
curl -X POST https://api.github.com/repos/Hamzaakhtar87/autotube/dispatches \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer $GITHUB_DISPATCH_TOKEN" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  -d '{"event_type":"run-job","client_payload":{"job_id":"test-123"}}'

gh run list --workflow run-job.yml --limit 1
gh workflow run supabase-keepalive.yml && gh run list --workflow supabase-keepalive.yml --limit 1
```

Both should show a green run.
