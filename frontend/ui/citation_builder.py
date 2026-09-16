"""Builder for source citation elements in the Chainlit UI."""

from typing import Any

import chainlit as cl

from frontend.models import CitationItem
from frontend.ui.i18n import (
    LANG_FA,
    format_citation_body,
    format_citation_title,
    normalize_language,
)


class CitationBuilder:
    """Builds typed citation models and visual Chainlit Text components from raw search nodes."""

    @staticmethod
    def parse_node(
        node: dict[str, Any], index: int, lang: str = LANG_FA
    ) -> CitationItem:
        """Transforms a raw node dictionary into a validated CitationItem model.

        Args:
            node: Raw extracted node dict containing 'text', 'metadata', and optional 'score'.
            index: 1-based sequential citation index.
            lang: Language code ('fa' or 'en').

        Returns:
            CitationItem: Strongly typed citation object.
        """
        metadata: dict[str, Any] = node.get("metadata") or {}
        default_fname = (
            "Unknown Document" if normalize_language(lang) == "en" else "سند نامشخص"
        )
        filename = str(metadata.get("filename", default_fname))
        raw_score = node.get("score")

        score: float | None = None
        if isinstance(raw_score, (int, float)):
            score = float(raw_score)

        text = str(node.get("text", "")).strip()
        title = format_citation_title(lang=lang, index=index, filename=filename)
        body = format_citation_body(
            lang=lang, text=text, score=score, filename=filename
        )

        return CitationItem(
            index=index,
            filename=filename,
            score=score,
            text=text,
            title=title,
            body=body,
        )

    def build_elements(
        self,
        source_nodes: list[dict[str, Any]],
        thread_id: str | None = None,
        lang: str = LANG_FA,
    ) -> list[Any]:
        """Converts a collection of source nodes into Chainlit Text components.

        Args:
            source_nodes: List of raw node dictionaries from QueryResponse.
            thread_id: Optional thread ID override (useful in unit test contexts).
            lang: Display language ('fa' or 'en').

        Returns:
            list[Any]: List of cl.Text UI components ready to attach to a message.
        """
        elements: list[Any] = []
        for idx, node in enumerate(source_nodes, 1):
            citation = self.parse_node(node, idx, lang=lang)
            kwargs: dict[str, Any] = {
                "name": citation.title,
                "content": citation.body,
                "display": "inline",
            }
            if thread_id is not None:
                kwargs["thread_id"] = thread_id
            elements.append(cl.Text(**kwargs))
        return elements
