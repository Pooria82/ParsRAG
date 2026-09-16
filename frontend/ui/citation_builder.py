"""Builder for source citation elements in the Chainlit UI."""

from typing import Any

import chainlit as cl

from frontend.models import CitationItem


class CitationBuilder:
    """Builds typed citation models and visual Chainlit Text components from raw search nodes."""

    @staticmethod
    def parse_node(node: dict[str, Any], index: int) -> CitationItem:
        """Transforms a raw node dictionary into a validated CitationItem model.

        Args:
            node: Raw extracted node dict containing 'text', 'metadata', and optional 'score'.
            index: 1-based sequential citation index.

        Returns:
            CitationItem: Strongly typed citation object.
        """
        metadata: dict[str, Any] = node.get("metadata") or {}
        filename = str(metadata.get("filename", "سند نامشخص"))
        raw_score = node.get("score")

        score: float | None = None
        if isinstance(raw_score, (int, float)):
            score = float(raw_score)
            score_label = f"امتیاز شباهت: {score:.3f}"
        else:
            score_label = "بدون امتیاز عددی"

        text = str(node.get("text", "")).strip()
        title = f"📄 منبع {index}: {filename}"
        body = (
            f"### 📑 مشخصات استناد {index}\n"
            f"- **سند منبع:** `{filename}`\n"
            f"- **میزان تطابق:** {score_label}\n\n"
            f"**متن استخراج‌شده:**\n"
            f"```text\n{text}\n```"
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
    ) -> list[Any]:
        """Converts a collection of source nodes into Chainlit Text components.

        Args:
            source_nodes: List of raw node dictionaries from QueryResponse.
            thread_id: Optional thread ID override (useful in unit test contexts).

        Returns:
            list[Any]: List of cl.Text UI components ready to attach to a message.
        """
        elements: list[Any] = []
        for idx, node in enumerate(source_nodes, 1):
            citation = self.parse_node(node, idx)
            kwargs: dict[str, Any] = {
                "name": citation.title,
                "content": citation.body,
                "display": "inline",
            }
            if thread_id is not None:
                kwargs["thread_id"] = thread_id
            elements.append(cl.Text(**kwargs))
        return elements
