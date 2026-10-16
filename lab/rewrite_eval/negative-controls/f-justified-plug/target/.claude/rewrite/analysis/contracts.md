# Contracts — S-01

- C-01 (wire, keep): GET /health publicly returns HTTP 200, JSON media type, and `{"status":"ok"}`. This is process liveness, not dependency readiness.
- C-02 (wire, keep): unknown paths and POST /health return 404.

Source: `SOURCE/service.py:1-4`. No accounts, storage, scheduled work, websocket protocol, browser UI, or durable effects are in scope.
