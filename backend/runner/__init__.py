"""
Job-execution-only code. Runs inside the GitHub Actions runner, not the API.

`vault_decrypt` is the single place a stored provider key can be turned back
into plaintext. Nothing under `backend/app` may import anything from here —
`tests/test_vault_route_sweep.py` enforces that.
"""
