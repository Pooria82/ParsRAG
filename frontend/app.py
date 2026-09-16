"""ParsRAG Chainlit Frontend Application.

Provides a modern, Persian-first conversational UI supporting:
- 3 RAG operational modes (Strict RAG, Hybrid RAG, LLM Only) via RadioGroup.
- Dynamic retrieval depth (top_k slider from 5 to 30).
- Multi-document upload handlers (DOCX, PPTX, PDF up to 5 files per session).
- Progressive token streaming with conversational memory.
- Collapsible inline source citations with similarity scores.
"""

import asyncio
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any

# Ensure repository root is on sys.path for chainlit runner
WORKSPACE_ROOT = str(Path(__file__).resolve().parent.parent)
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

import chainlit as cl
import httpx
from chainlit.input_widget import RadioGroup, Slider

from frontend.client import (
    MAX_FILES_PER_BATCH,
    ParsRAGClient,
    format_citation,
    parse_mode,
)

# Backend API Client
BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")
client = ParsRAGClient(base_url=BACKEND_URL)


@cl.on_chat_start
async def on_chat_start() -> None:
    """Initializes the chat session, settings controls, and welcome interface."""
    # 1. Generate unique session ID (scoped document indexing)
    session_id = f"session_{uuid.uuid4().hex[:12]}"
    cl.user_session.set("session_id", session_id)
    cl.user_session.set("chat_history", [])
    cl.user_session.set("mode", "hybrid")
    cl.user_session.set("top_k", 15)
    cl.user_session.set("uploaded_files", [])

    # 2. Configure Interactive Settings (Radio buttons for modes, Slider for top_k)
    settings = cl.ChatSettings(
        [
            RadioGroup(
                id="mode",
                label="🎯 حالت کاری سامانه (RAG Execution Mode)",
                values=["Hybrid RAG", "Strict RAG", "LLM Only"],
                initial_value="Hybrid RAG",
                description="Strict: فقط اسناد بارگذاری‌شده | Hybrid: تلفیق اسناد و مدل | LLM Only: بدون مراجعه به اسناد",
            ),
            Slider(
                id="top_k",
                label="📊 عمق بازیابی قطعات (Retrieval Depth / Top-K)",
                min=5,
                max=30,
                step=5,
                initial=15,
                description="تعداد قطعات متنی و ردیف‌های استخراج‌شده از پایگاه‌داده برداری Qdrant",
            ),
        ]
    )
    await settings.send()

    # 3. Persian Welcome Screen
    welcome_content = (
        "## 👋 به دستیار هوشمند اسناد «پارس‌رگ» (ParsRAG) خوش آمدید!\n\n"
        "این سامانه مجهز به پردازش محلی، دقیق و بدون نشت اطلاعات برای اسناد فارسی است.\n\n"
        "### ⚙️ حالت‌های کاری سامانه:\n"
        "- **Strict RAG (فقط اسناد):** پاسخ‌دهی ۱۰۰٪ مقید به متن اسناد بارگذاری‌شده. در صورت عدم وجود پاسخ در اسناد، درخواست رد می‌شود.\n"
        "- **Hybrid RAG (ترکیبی - پیش‌فرض):** تلفیق هوشمندانه شواهد سند با دانش عمومی مدل زبانی برای پاسخ‌های جامع.\n"
        "- **LLM Only (فقط مدل):** گفتگو و تحلیل مستقیم با مدل بدون مراجعه به اسناد.\n\n"
        "### 📁 نحوه کار با اسناد:\n"
        "- می‌توانید فایل‌های خود را با فرمت‌های **PDF**، **Word (DOCX)** یا **PowerPoint (PPTX)** با دکمه سنجاق پایین پیوست کنید (حداکثر ۵ فایل در هر نشست).\n"
        "- ساختار جدول‌های پیچیده و عناوین تو در تو به صورت خودکار شناسایی و ذخیره می‌شوند.\n"
        "- می‌توانید حالت یا عمق بازیابی را از منوی تنظیمات (⚙️ در گوشه کادر پیام) تغییر دهید.\n\n"
        "💬 *سند خود را بارگذاری کنید یا پرسش خود را مستقیماً بنویسید.*"
    )
    await cl.Message(content=welcome_content).send()


@cl.on_settings_update
async def on_settings_update(settings: dict[str, Any]) -> None:
    """Updates user session parameters when settings widgets are modified.

    Args:
        settings: Dictionary containing changed widget values.
    """
    raw_mode = str(settings.get("mode", "Hybrid RAG"))
    mode = parse_mode(raw_mode)
    cl.user_session.set("mode", mode)

    top_k = int(settings.get("top_k", 15))
    cl.user_session.set("top_k", top_k)

    status_text = (
        f"⚙️ **تنظیمات به‌روزرسانی شد:**\n"
        f"- **حالت فعال:** `{raw_mode}` (`{mode}`)\n"
        f"- **عمق بازیابی (Top-K):** `{top_k}`"
    )
    await cl.Message(content=status_text).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Handles incoming user messages, file uploads, RAG queries, and streaming.

    Args:
        message: The Chainlit incoming message object.
    """
    session_id: str = str(cl.user_session.get("session_id", ""))
    mode: str = str(cl.user_session.get("mode", "hybrid"))
    top_k: int = int(cl.user_session.get("top_k", 15))
    chat_history: list[dict[str, str]] = cl.user_session.get("chat_history", [])
    uploaded_files: list[str] = cl.user_session.get("uploaded_files", [])

    # 1. Process Attached Files (if any)
    attached_elements = message.elements or []
    files_to_upload: list[tuple[str, bytes]] = []

    for elem in attached_elements:
        file_path = getattr(elem, "path", None)
        file_name = getattr(elem, "name", "document")
        file_bytes: bytes | None = None

        if file_path and os.path.exists(file_path):
            file_bytes = await asyncio.to_thread(Path(file_path).read_bytes)
        elif getattr(elem, "content", None):
            raw_content = elem.content
            if isinstance(raw_content, bytes):
                file_bytes = raw_content

        if file_bytes is not None:
            files_to_upload.append((file_name, file_bytes))

    if files_to_upload:
        # Check cumulative file count limit (max 5)
        total_future_files = len(uploaded_files) + len(files_to_upload)
        if total_future_files > MAX_FILES_PER_BATCH:
            await cl.Message(
                content=(
                    f"⚠️ **محدودیت تعداد اسناد:** سقف مجاز فایل در هر نشست حداکثر {MAX_FILES_PER_BATCH} فایل است.\n"
                    f"تعداد فایل‌های قبلی: {len(uploaded_files)} | فایل‌های جدید: {len(files_to_upload)}"
                )
            ).send()
            return

        ingest_msg = cl.Message(
            content=f"⏳ در حال پردازش و نمایه‌سازی {len(files_to_upload)} فایل در پایگاه برداری..."
        )
        await ingest_msg.send()

        try:
            res = await client.ingest_files(files_to_upload, session_id=session_id)
            for fname, _ in files_to_upload:
                if fname not in uploaded_files:
                    uploaded_files.append(fname)
            cl.user_session.set("uploaded_files", uploaded_files)

            files_list_md = "\n".join([f"- 📄 `{f}`" for f in uploaded_files])
            ingest_msg.content = (
                f"✅ **نمایه‌سازی با موفقیت انجام شد!**\n\n"
                f"{res.get('message', '')}\n\n"
                f"**اسناد فعال در این نشست:**\n{files_list_md}"
            )
            await ingest_msg.update()
        except (ValueError, RuntimeError, httpx.RequestError) as exc:
            ingest_msg.content = f"❌ **خطا در بارگذاری سند:** {exc}"
            await ingest_msg.update()
            return

    # 2. Check if user provided a text prompt to query
    prompt_text = (message.content or "").strip()
    if not prompt_text:
        # Message was solely for file upload
        return

    # 3. Prepare Streaming Response Message
    response_msg = cl.Message(content="")
    await response_msg.send()

    try:
        query_res = await client.query(
            prompt=prompt_text,
            chat_history=chat_history,
            mode=mode,
            session_id=session_id,
            top_k=top_k,
        )

        answer_text = query_res.get("answer", "")
        source_nodes: list[dict[str, Any]] = query_res.get("source_nodes", [])

        # Stream response progressively to give a smooth typing effect
        # Split tokens preserving Persian spacing and line breaks
        tokens = re.findall(r"\S+|\s+", answer_text)
        for token in tokens:
            await response_msg.stream_token(token)
            await asyncio.sleep(0.008)

        # Build inline source citations if present (Chainlit ElementBased TypeVar)
        citation_elements: list[Any] = []
        if source_nodes:
            for idx, node in enumerate(source_nodes, 1):
                cit_title, cit_body = format_citation(node, idx)
                citation_elements.append(
                    cl.Text(
                        name=cit_title,
                        content=cit_body,
                        display="inline",
                    )
                )

        if citation_elements:
            response_msg.elements = citation_elements
            await response_msg.update()

        # Update conversational memory (keep last 10 messages)
        chat_history.append({"role": "user", "content": prompt_text})
        chat_history.append({"role": "assistant", "content": answer_text})
        if len(chat_history) > 10:
            chat_history = chat_history[-10:]
        cl.user_session.set("chat_history", chat_history)

    except (RuntimeError, ValueError, httpx.RequestError) as exc:
        error_md = (
            f"⚠️ **خطا در پردازش پرسش:**\n\n"
            f"> {exc}\n\n"
            f"لطفاً مطمئن شوید سرویس بک‌اند فعال است یا تنظیمات RAG را بررسی فرمایید."
        )
        await response_msg.stream_token(error_md)
        await response_msg.update()
