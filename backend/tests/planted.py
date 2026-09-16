"""
The planted credential values every vault test submits.

`conftest.py` records every log record, every captured stdout/stderr chunk and
every API response body/header for the whole run, then greps all of it for
these literals at session end. If any shows up anywhere, the run fails.
"""

PLANTED_API_KEY = "autotube-planted-secret-KEY-7f3a9c2e4b1d"
PLANTED_KLING_ACCESS_KEY = "autotube-planted-kling-AK-51e0aa77c3"
PLANTED_KLING_SECRET_KEY = "autotube-planted-kling-SK-9b2f44d1e8"

PLANTED_SECRETS = (PLANTED_API_KEY, PLANTED_KLING_ACCESS_KEY, PLANTED_KLING_SECRET_KEY)


def credentials_for(provider: str) -> dict:
    if provider == "kling":
        return {"access_key": PLANTED_KLING_ACCESS_KEY, "secret_key": PLANTED_KLING_SECRET_KEY}
    return {"api_key": PLANTED_API_KEY}
