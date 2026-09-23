"""Shared test environment configuration."""

import os

os.environ["PARSRAG_SKIP_MODEL_SETUP"] = "1"

from backend.core.runtime import runtime_state

runtime_state.mark_ready()
