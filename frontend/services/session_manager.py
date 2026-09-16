"""Session management service for ParsRAG frontend."""

import uuid
from typing import Any

import chainlit as cl

from frontend.models import SessionState


class SessionManager:
    """Encapsulates user session storage and state mutations with strong typing.

    Accepts an optional storage backend (defaults to Chainlit's cl.user_session)
    allowing frictionless unit testing without live Chainlit context.
    """

    def __init__(self, store: Any = None) -> None:
        """Initializes the session manager.

        Args:
            store: Storage backend with get/set methods (defaults to cl.user_session).
        """
        self._store = store if store is not None else cl.user_session

    def _get(self, key: str, default: Any = None) -> Any:
        """Internal helper to safely retrieve a value from the store."""
        if hasattr(self._store, "get"):
            val = self._store.get(key)
            return val if val is not None else default
        if isinstance(self._store, dict):
            val = self._store.get(key)
            return val if val is not None else default
        return default

    def _set(self, key: str, value: Any) -> None:
        """Internal helper to safely assign a value in the store."""
        if hasattr(self._store, "set"):
            self._store.set(key, value)
        elif isinstance(self._store, dict):
            self._store[key] = value

    def initialize_session(
        self,
        session_id: str | None = None,
        default_language: str = "fa",
        default_mode: str = "hybrid",
        default_strict_rag_threshold: float = 0.80,
        default_dynamic_top_k: bool = True,
        default_manual_top_k: int = 15,
        default_top_k: int | None = None,
        default_max_chat_history_turns: int = 10,
        default_backend_url: str = "http://localhost:8000",
    ) -> SessionState:
        """Initializes state for a new chat session.

        Args:
            session_id: Optional explicit session ID; generates one if None.
            default_language: Initial interface language ('fa' or 'en').
            default_mode: Initial RAG execution mode.
            default_strict_rag_threshold: Initial strict RAG similarity threshold.
            default_dynamic_top_k: Whether dynamic depth optimization is enabled.
            default_manual_top_k: Fallback manual retrieval depth.
            default_top_k: Initial retrieval depth override (None = automated).
            default_max_chat_history_turns: Conversational memory turn limit.
            default_backend_url: FastAPI backend service URL.

        Returns:
            SessionState: Initialized session model.
        """
        sid = session_id or f"session_{uuid.uuid4().hex[:12]}"
        self._set("session_id", sid)
        self._set("language", default_language)
        self._set("mode", default_mode)
        self._set("strict_rag_threshold", default_strict_rag_threshold)
        self._set("dynamic_top_k", default_dynamic_top_k)
        self._set("manual_top_k", default_manual_top_k)
        self._set("top_k", default_top_k)
        self._set("max_chat_history_turns", default_max_chat_history_turns)
        self._set("backend_url", default_backend_url)
        self._set("chat_history", [])
        self._set("uploaded_files", [])

        return self.get_state()

    def get_state(self) -> SessionState:
        """Retrieves the full active SessionState.

        Returns:
            SessionState: Strongly typed state snapshot.
        """
        raw_top_k = self._get("top_k", None)
        top_k_val = int(raw_top_k) if raw_top_k is not None else None
        return SessionState(
            session_id=str(self._get("session_id", "")),
            language=str(self._get("language", "fa")),
            mode=str(self._get("mode", "hybrid")),
            strict_rag_threshold=float(self._get("strict_rag_threshold", 0.80)),
            dynamic_top_k=bool(self._get("dynamic_top_k", True)),
            manual_top_k=int(self._get("manual_top_k", 15)),
            top_k=top_k_val,
            max_chat_history_turns=int(self._get("max_chat_history_turns", 10)),
            backend_url=str(self._get("backend_url", "http://localhost:8000")),
            chat_history=list(self._get("chat_history", [])),
            uploaded_files=list(self._get("uploaded_files", [])),
        )

    def get_session_id(self) -> str:
        """Returns the active session ID."""
        return str(self._get("session_id", ""))

    def get_language(self) -> str:
        """Returns active language ('fa' or 'en')."""
        return str(self._get("language", "fa"))

    def set_language(self, language: str) -> None:
        """Sets active language."""
        self._set("language", language)

    def get_mode(self) -> str:
        """Returns the active RAG mode ('strict', 'hybrid', or 'llm-only')."""
        return str(self._get("mode", "hybrid"))

    def set_mode(self, mode: str) -> None:
        """Sets the active RAG mode."""
        self._set("mode", mode)

    def get_strict_rag_threshold(self) -> float:
        """Returns strict RAG similarity threshold."""
        return float(self._get("strict_rag_threshold", 0.80))

    def set_strict_rag_threshold(self, threshold: float) -> None:
        """Sets strict RAG similarity threshold."""
        self._set("strict_rag_threshold", threshold)

    def get_dynamic_top_k(self) -> bool:
        """Returns whether dynamic retrieval depth is enabled."""
        return bool(self._get("dynamic_top_k", True))

    def set_dynamic_top_k(self, dynamic: bool) -> None:
        """Sets whether dynamic retrieval depth is enabled."""
        self._set("dynamic_top_k", dynamic)

    def get_manual_top_k(self) -> int:
        """Returns manual retrieval depth override."""
        return int(self._get("manual_top_k", 15))

    def set_manual_top_k(self, top_k: int) -> None:
        """Sets manual retrieval depth override."""
        self._set("manual_top_k", top_k)

    def get_top_k(self) -> int | None:
        """Returns the effective retrieval depth (None if dynamic)."""
        val = self._get("top_k", None)
        return int(val) if val is not None else None

    def set_top_k(self, top_k: int | None) -> None:
        """Sets effective retrieval depth."""
        self._set("top_k", top_k)

    def get_backend_url(self) -> str:
        """Returns backend service URL."""
        return str(self._get("backend_url", "http://localhost:8000"))

    def set_backend_url(self, url: str) -> None:
        """Sets backend service URL."""
        self._set("backend_url", url)

    def get_max_chat_history_turns(self) -> int:
        """Returns maximum conversation turns preserved in context."""
        return int(self._get("max_chat_history_turns", 10))

    def set_max_chat_history_turns(self, turns: int) -> None:
        """Sets maximum conversation turns preserved in context."""
        self._set("max_chat_history_turns", turns)

    def get_uploaded_files(self) -> list[str]:
        """Returns the list of ingested document filenames."""
        return list(self._get("uploaded_files", []))

    def add_uploaded_files(self, new_filenames: list[str]) -> list[str]:
        """Appends new filenames to the session's active document list.

        Args:
            new_filenames: List of newly ingested filenames.

        Returns:
            list[str]: Updated cumulative list of filenames.
        """
        current = self.get_uploaded_files()
        for fname in new_filenames:
            if fname not in current:
                current.append(fname)
        self._set("uploaded_files", current)
        return current

    def get_chat_history(self) -> list[dict[str, str]]:
        """Returns the conversation message history."""
        return list(self._get("chat_history", []))

    def append_chat_turn(
        self, prompt: str, answer: str, max_turns: int = 10
    ) -> list[dict[str, str]]:
        """Records a user prompt and assistant answer pair in history.

        Args:
            prompt: User question text.
            answer: Assistant answer text.
            max_turns: Maximum number of messages preserved in context.

        Returns:
            list[dict[str, str]]: Updated conversation history.
        """
        history = self.get_chat_history()
        history.append({"role": "user", "content": prompt})
        history.append({"role": "assistant", "content": answer})
        if len(history) > max_turns:
            history = history[-max_turns:]
        self._set("chat_history", history)
        return history
