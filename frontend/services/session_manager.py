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
            return self._store.get(key) or default
        if isinstance(self._store, dict):
            return self._store.get(key, default)
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
        default_mode: str = "hybrid",
        default_top_k: int = 15,
    ) -> SessionState:
        """Initializes state for a new chat session.

        Args:
            session_id: Optional explicit session ID; generates one if None.
            default_mode: Initial RAG execution mode.
            default_top_k: Initial retrieval depth.

        Returns:
            SessionState: Initialized session model.
        """
        sid = session_id or f"session_{uuid.uuid4().hex[:12]}"
        self._set("session_id", sid)
        self._set("mode", default_mode)
        self._set("top_k", default_top_k)
        self._set("chat_history", [])
        self._set("uploaded_files", [])

        return self.get_state()

    def get_state(self) -> SessionState:
        """Retrieves the full active SessionState.

        Returns:
            SessionState: Strongly typed state snapshot.
        """
        return SessionState(
            session_id=str(self._get("session_id", "")),
            mode=str(self._get("mode", "hybrid")),
            top_k=int(self._get("top_k", 15)),
            chat_history=list(self._get("chat_history", [])),
            uploaded_files=list(self._get("uploaded_files", [])),
        )

    def get_session_id(self) -> str:
        """Returns the active session ID."""
        return str(self._get("session_id", ""))

    def get_mode(self) -> str:
        """Returns the active RAG mode ('strict', 'hybrid', or 'llm-only')."""
        return str(self._get("mode", "hybrid"))

    def set_mode(self, mode: str) -> None:
        """Sets the active RAG mode."""
        self._set("mode", mode)

    def get_top_k(self) -> int:
        """Returns the current retrieval depth."""
        return int(self._get("top_k", 15))

    def set_top_k(self, top_k: int) -> None:
        """Sets the retrieval depth."""
        self._set("top_k", top_k)

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
