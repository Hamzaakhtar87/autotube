"""
Job dispatch — fires a GitHub Actions run for a job via repository_dispatch.

This replaces the old Celery + Redis queue. There is no worker process to keep
alive: the `jobs` table row is the queue, and each job triggers one Actions run
(.github/workflows/run-job.yml) which does the heavy compute.

Required environment:
  GITHUB_REPO            e.g. "Hamzaakhtar87/autotube"
  GITHUB_DISPATCH_TOKEN  a token with `repo` (classic) or Contents: write
                         (fine-grained) permission on that repo.
"""

import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)

DISPATCH_EVENT_TYPE = "run-job"
GITHUB_API = "https://api.github.com"


class DispatchError(Exception):
    """Raised when a job could not be handed to GitHub Actions."""


def is_configured() -> bool:
    return bool(os.getenv("GITHUB_REPO")) and bool(os.getenv("GITHUB_DISPATCH_TOKEN"))


def dispatch_job(job_id: int, payload: dict[str, Any] | None = None, timeout: float = 10.0) -> None:
    """
    POST /repos/{owner}/{repo}/dispatches with event_type="run-job".

    GitHub returns 204 with no run id; the Actions run picks the job up by
    `client_payload.job_id`. Raises DispatchError on any failure so the caller
    can mark the job FAILED and surface a clear message.
    """
    repo = os.getenv("GITHUB_REPO")
    token = os.getenv("GITHUB_DISPATCH_TOKEN")
    if not repo or not token:
        raise DispatchError("GITHUB_REPO / GITHUB_DISPATCH_TOKEN are not configured")

    body = {
        "event_type": DISPATCH_EVENT_TYPE,
        "client_payload": {"job_id": job_id, **(payload or {})},
    }
    try:
        resp = requests.post(
            f"{GITHUB_API}/repos/{repo}/dispatches",
            json=body,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise DispatchError(f"GitHub API unreachable: {exc}") from exc

    if resp.status_code != 204:
        raise DispatchError(f"GitHub dispatch failed: HTTP {resp.status_code} {resp.text[:200]}")

    logger.info("Dispatched job %s to GitHub Actions (%s)", job_id, repo)
