"""Model reasoning never reaches answers, titles, or suggested questions."""

from collections.abc import Iterator
from unittest.mock import MagicMock, patch

import httpx
import openai
import pytest
from llama_index.core.base.llms.types import CompletionResponse
from llama_index.llms.openai_like import OpenAILike  # type: ignore[import-untyped]

from backend.infrastructure.llm.factory import api_model_name
from backend.infrastructure.llm.reasoning import (
    ReasoningFilter,
    ReasoningFreeOpenAILike,
    strip_reasoning,
)

GOOGLE = "<thought>*   Input: Persian\n    *   Draft: عدد ۵ یک‌رقمی است.</thought>عدد ۵ یک‌رقمی است."


def test_reasoning_blocks_are_removed_from_complete_answers() -> None:
    assert strip_reasoning(GOOGLE) == "عدد ۵ یک‌رقمی است."
    assert strip_reasoning("<think>plan</think>\n\nپاسخ") == "پاسخ"
    assert strip_reasoning("پاسخ بدون فکر") == "پاسخ بدون فکر"
    # Cut off while still reasoning: no answer text yet.
    assert strip_reasoning("<thought>still thinking") == ""
    # Ordinary angle brackets in answers are kept.
    assert strip_reasoning("a < b and <b>bold</b>") == "a < b and <b>bold</b>"


@pytest.mark.parametrize("size", [1, 2, 3, 7, 50])
def test_streamed_reasoning_is_hidden_at_any_chunk_size(size: int) -> None:
    reasoning = ReasoningFilter()
    shown = "".join(
        reasoning.feed(GOOGLE[i : i + size]) for i in range(0, len(GOOGLE), size)
    )
    shown += reasoning.flush()
    assert shown == "عدد ۵ یک‌رقمی است."


def test_streams_without_reasoning_pass_through_unchanged() -> None:
    reasoning = ReasoningFilter()
    text = "x < 3 then <b>bold</b> and <t"
    shown = "".join(reasoning.feed(ch) for ch in text) + reasoning.flush()
    assert shown == text


def test_google_ai_studio_models_get_their_prefix() -> None:
    google = "https://generativelanguage.googleapis.com/v1beta/openai"
    assert api_model_name(google, "gemma-4-26b-a4b-it") == "models/gemma-4-26b-a4b-it"
    assert (
        api_model_name(google, "models/gemma-4-26b-a4b-it")
        == "models/gemma-4-26b-a4b-it"
    )
    assert (
        api_model_name("https://openrouter.ai/api/v1", "google/gemma") == "google/gemma"
    )


def _status_error(
    cls: type[openai.APIStatusError], status: int
) -> openai.APIStatusError:
    request = httpx.Request("POST", "https://example.test")
    return cls("boom", response=httpx.Response(status, request=request), body=None)


def _client(retries: int = 3) -> ReasoningFreeOpenAILike:
    return ReasoningFreeOpenAILike(
        model="m",
        api_key="k",
        api_base="https://example.test/v1",
        is_chat_model=True,
        status_retries=retries,
    )


def test_server_errors_are_retried_and_reasoning_removed() -> None:
    client = _client()
    replies = [
        _status_error(openai.InternalServerError, 500),
        _status_error(openai.RateLimitError, 429),
        CompletionResponse(text=GOOGLE),
    ]

    def complete(
        self: object, prompt: str, formatted: bool = False, **kwargs: object
    ) -> CompletionResponse:
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        assert isinstance(reply, CompletionResponse)
        return reply

    with patch.object(OpenAILike, "complete", complete), patch("time.sleep") as sleep:
        assert client.complete("q").text == "عدد ۵ یک‌رقمی است."
    assert sleep.call_count == 2


def test_retries_stop_after_the_configured_count() -> None:
    client = _client(retries=1)
    failing = MagicMock(side_effect=_status_error(openai.InternalServerError, 500))
    with (
        patch.object(OpenAILike, "complete", failing),
        patch("time.sleep"),
        pytest.raises(openai.InternalServerError),
    ):
        client.complete("q")
    assert failing.call_count == 2


def test_streams_retry_before_the_first_chunk_and_hide_reasoning() -> None:
    client = _client()
    attempts = {"n": 0}

    def stream(
        self: object, prompt: str, formatted: bool = False, **kwargs: object
    ) -> Iterator[CompletionResponse]:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise _status_error(openai.InternalServerError, 500)
        text = ""
        for piece in ("<thought>plan", "</thought>جو", "اب"):
            text += piece
            yield CompletionResponse(text=text, delta=piece)

    with patch.object(OpenAILike, "stream_complete", stream), patch("time.sleep"):
        deltas = [r.delta for r in client.stream_complete("q")]
    assert "".join(d or "" for d in deltas) == "جواب"
    assert attempts["n"] == 2
