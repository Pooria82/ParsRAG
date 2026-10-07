"""Shared test environment configuration."""

import os

os.environ["PARSRAG_SKIP_MODEL_SETUP"] = "1"
# Unit tests mock the Qdrant client; keyword fusion is tested explicitly.
os.environ.setdefault("KEYWORD_SEARCH", "0")
# Starlette's TestClient addresses the app as http://testserver.
os.environ["PARSRAG_ALLOWED_HOSTS"] = "localhost,127.0.0.1,::1,testserver"

from backend.core.runtime.readiness import runtime_state

runtime_state.mark_ready()
