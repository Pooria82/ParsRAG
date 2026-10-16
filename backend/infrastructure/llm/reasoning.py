"""Remove model reasoning ("thinking") from answers before they reach users.

Some OpenAI-compatible services return a model's reasoning inside the answer
text. Google AI Studio sends Gemma 4 output as ``<thought>...</thought>``
followed by the answer; other servers use ``<think>...</think>``. The app
shows answers verbatim and parses titles and suggested questions from them,
so the reasoning is removed from complete responses and from streams.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable, Generator, Sequence
from typing import Any, TypeVar

import openai
from llama_index.core.base.llms.types import (
    ChatMessage,
    ChatResponse,
    ChatResponseGen,
    CompletionResponse,
    CompletionResponseGen,
)
from llama_index.llms.openai_like import OpenAILike  # type: ignore[import-untyped]
from pydantic import Field

_T = TypeVar("_T")

_TAGS = ("thought", "think", "thinking")
_BLOCK = re.compile(r"<(" + "|".join(_TAGS) + r")>.*?</\1>", re.DOTALL | re.IGNORECASE)
_OPEN = re.compile(r"<(" + "|".join(_TAGS) + r")>", re.IGNORECASE)


def strip_reasoning(text: str) -> str:
    """Return ``text`` without reasoning blocks.

    An opening tag that is never closed means the answer was cut off while the
    model was still reasoning, so nothing after it is part of the answer.
    """
    cleaned = _BLOCK.sub("", text)
    unclosed = _OPEN.search(cleaned)
    if unclosed:
        cleaned = cleaned[: unclosed.start()]
    return cleaned.strip() if cleaned != text else text


class ReasoningFilter:
    """Incremental version of :func:`strip_reasoning` for streamed answers.

    Text is held back only while it may still be the start of a tag, so
    visible words stream without delay.
    """

    def __init__(self) -> None:
        """Start outside any reasoning block, with nothing shown yet."""
        self._buffer = ""
        self._closing: str | None = None
        self._started = False

    def feed(self, delta: str) -> str:
        """Add streamed text; return the part that is safe to show."""
        self._buffer += delta
        visible: list[str] = []
        while self._buffer:
            if self._closing is not None:
                end = self._buffer.lower().find(self._closing)
                if end < 0:
                    # Keep only what could be the start of the closing tag.
                    self._buffer = self._buffer[-(len(self._closing) - 1) :]
                    break
                self._buffer = self._buffer[end + len(self._closing) :]
                self._closing = None
                continue
            match = _OPEN.search(self._buffer)
            if match:
                visible.append(self._buffer[: match.start()])
                self._closing = f"</{match.group(1).lower()}>"
                self._buffer = self._buffer[match.end() :]
                continue
            cut = self._buffer.rfind("<")
            if cut >= 0 and _could_open(self._buffer[cut:]):
                visible.append(self._buffer[:cut])
                self._buffer = self._buffer[cut:]
                break
            visible.append(self._buffer)
            self._buffer = ""
        text = "".join(visible)
        if not self._started:
            # Answers often start right after a reasoning block's newline.
            text = text.lstrip()
            self._started = bool(text)
        return text

    def flush(self) -> str:
        """Return held-back text at the end of the stream (never reasoning)."""
        rest = "" if self._closing is not None else self._buffer
        self._buffer = ""
        return rest if self._started else rest.lstrip()


def _could_open(fragment: str) -> bool:
    """Whether ``fragment`` (starting with "<") may grow into an opening tag."""
    lowered = fragment.lower()
    return any(f"<{tag}>".startswith(lowered) for tag in _TAGS)


def _filtered_stream(stream: CompletionResponseGen) -> CompletionResponseGen:
    reasoning = ReasoningFilter()
    text = ""
    last: CompletionResponse | None = None
    for response in stream:
        last = response
        visible = reasoning.feed(response.delta or "")
        if visible:
            text += visible
            yield CompletionResponse(text=text, delta=visible, raw=response.raw)
    tail = reasoning.flush()
    if tail:
        text += tail
        yield CompletionResponse(
            text=text, delta=tail, raw=last.raw if last is not None else None
        )


def _filtered_chat_stream(stream: ChatResponseGen) -> ChatResponseGen:
    reasoning = ReasoningFilter()
    text = ""
    for response in stream:
        visible = reasoning.feed(response.delta or "")
        if visible:
            text += visible
            message = response.message.model_copy(update={"content": text})
            yield ChatResponse(message=message, delta=visible, raw=response.raw)
    tail = reasoning.flush()
    if tail:
        text += tail
        yield ChatResponse(
            message=ChatMessage(role="assistant", content=text), delta=tail
        )


class ReasoningFreeOpenAILike(OpenAILike):  # type: ignore[misc]
    """``OpenAILike`` client whose answers never include reasoning blocks.

    It also retries fast server-side failures (HTTP 5xx and 429) beyond the
    client's single retry. Timeouts are not retried here, so a slow request
    still fits the browser's wait.
    """

    status_retries: int = Field(default=4, ge=0, le=8)

    def _with_status_retries(self, call: Callable[[], _T]) -> _T:
        for attempt in range(self.status_retries + 1):
            try:
                return call()
            except (openai.InternalServerError, openai.RateLimitError):
                if attempt == self.status_retries:
                    raise
                # Failures come in short bursts: wait 2, 4, 8, then 16 seconds.
                time.sleep(min(16.0, 2.0 * 2**attempt))
        raise AssertionError("unreachable")

    def complete(
        self, prompt: str, formatted: bool = False, **kwargs: Any
    ) -> CompletionResponse:
        """Complete ``prompt`` and remove reasoning from the answer."""
        response = self._with_status_retries(
            lambda: super(ReasoningFreeOpenAILike, self).complete(
                prompt, formatted=formatted, **kwargs
            )
        )
        return CompletionResponse(
            text=strip_reasoning(response.text),
            raw=response.raw,
            additional_kwargs=response.additional_kwargs,
        )

    def stream_complete(
        self, prompt: str, formatted: bool = False, **kwargs: Any
    ) -> CompletionResponseGen:
        """Stream ``prompt``'s answer without its reasoning.

        A failed stream is retried only before its first chunk: once text was
        shown, starting over would repeat it.
        """

        def start() -> tuple[CompletionResponse | None, CompletionResponseGen]:
            stream = super(ReasoningFreeOpenAILike, self).stream_complete(
                prompt, formatted=formatted, **kwargs
            )
            return next(stream, None), stream

        first, stream = self._with_status_retries(start)

        def chained() -> CompletionResponseGen:
            if first is not None:
                yield first
            yield from stream

        return _filtered_stream(chained())

    def chat(self, messages: Sequence[ChatMessage], **kwargs: Any) -> ChatResponse:
        """Chat and remove reasoning from the reply."""
        response = self._with_status_retries(
            lambda: super(ReasoningFreeOpenAILike, self).chat(messages, **kwargs)
        )
        content = strip_reasoning(str(response.message.content or ""))
        message = response.message.model_copy(update={"content": content})
        return ChatResponse(message=message, raw=response.raw)

    def stream_chat(
        self, messages: Sequence[ChatMessage], **kwargs: Any
    ) -> Generator[ChatResponse, None, None]:
        """Stream a chat reply without its reasoning."""
        return _filtered_chat_stream(super().stream_chat(messages, **kwargs))
