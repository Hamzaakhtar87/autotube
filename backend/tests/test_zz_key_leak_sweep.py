"""
Phase 2 test (2), visible half.

`conftest.pytest_sessionfinish` runs the same sweep over the *entire* session
(including anything after this file) and fails the run on a hit. This test
runs last alphabetically and reports the sweep as a normal test item so it is
visible in the pass/fail list too.
"""
from tests.conftest import COLLECTED, leak_report
from tests.planted import PLANTED_SECRETS


def test_planted_secrets_were_actually_used():
    """Guard against a vacuous sweep: the keys tests must have sent the secrets."""
    assert COLLECTED.responses, "no API responses were recorded — RecordingTestClient not in use?"
    assert any("/keys/" in r[1] for r in COLLECTED.responses), "no /keys requests were made this run"
    assert COLLECTED.logs, "no log records captured"


def test_no_planted_secret_anywhere():
    hits, counts = leak_report()
    assert counts["api_responses"] > 50 and counts["log_records"] > 0
    assert hits == [], f"planted secret found: {hits}"
    assert len(PLANTED_SECRETS) == 3
