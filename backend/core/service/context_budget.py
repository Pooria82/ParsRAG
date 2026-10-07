"""Keep prompts inside the model's context window.

Models silently drop the start of an over-long prompt, which removes the
grounding rules first. Retrieved chunks are therefore trimmed, lowest score
first, until the prompt and a reserved answer fit the context window.
"""

import math
import re
from typing import Any

from backend.core.domain.documents import ExtractedNode

# Conservative characters-per-token ratios: Persian/Arabic script tokenizes
# into more pieces than Latin text in common open-model vocabularies.
_ARABIC_SCRIPT = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
_ARABIC_CHARS_PER_TOKEN = 2.5
_OTHER_CHARS_PER_TOKEN = 3.5
# Source label and separators added around each chunk in the prompt.
_CHUNK_OVERHEAD_TOKENS = 24
UNKNOWN_CONTEXT_WINDOW = 32768


def estimate_tokens(text: str) -> int:
    """Return a conservative token estimate for mixed Persian/Latin text."""
    arabic = len(_ARABIC_SCRIPT.findall(text))
    other = len(text) - arabic
    return math.ceil(arabic / _ARABIC_CHARS_PER_TOKEN + other / _OTHER_CHARS_PER_TOKEN)


def answer_reserve(context_window: int) -> int:
    """Tokens kept free for the answer: a quarter of the window, 256-1024."""
    return max(256, min(1024, context_window // 4))


def model_context_window(llm: Any) -> int:
    """Read an LLM adapter's context window, defaulting when it is unknown."""
    try:
        value = llm.metadata.context_window
    except Exception:  # noqa: BLE001 - adapters without metadata use the default.
        return UNKNOWN_CONTEXT_WINDOW
    return value if isinstance(value, int) and value > 0 else UNKNOWN_CONTEXT_WINDOW


def fit_to_context(
    nodes: list[ExtractedNode], *, context_window: int, fixed_prompt: str
) -> list[ExtractedNode]:
    """Keep the highest-scoring chunks that fit, in their original order.

    ``fixed_prompt`` is the prompt without the context (rules, question).
    At least one chunk is kept; it is shortened when it alone does not fit.
    """
    if not nodes:
        return []
    budget = (
        context_window - answer_reserve(context_window) - estimate_tokens(fixed_prompt)
    )
    by_priority = sorted(
        range(len(nodes)), key=lambda index: nodes[index].score or 0.0, reverse=True
    )
    kept: set[int] = set()
    used = 0
    for index in by_priority:
        cost = estimate_tokens(nodes[index].text) + _CHUNK_OVERHEAD_TOKENS
        if used + cost <= budget:
            kept.add(index)
            used += cost
    if kept:
        return [node for index, node in enumerate(nodes) if index in kept]
    best = nodes[by_priority[0]]
    room = max(64, budget - _CHUNK_OVERHEAD_TOKENS)
    ratio = _ARABIC_CHARS_PER_TOKEN if _ARABIC_SCRIPT.search(best.text) else 3.5
    return [best.model_copy(update={"text": best.text[: int(room * ratio)]})]
