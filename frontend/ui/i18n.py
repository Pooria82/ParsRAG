"""Centralized Internationalization (i18n) catalog for Persian (fa) and English (en).

Provides localized UI text, markdown templates, notifications, and settings descriptions
supporting full bidirectional (RTL / LTR) switching.
"""

from typing import Final

# Language Codes
LANG_FA: Final[str] = "fa"
LANG_EN: Final[str] = "en"
SUPPORTED_LANGUAGES: Final[list[str]] = [LANG_FA, LANG_EN]

# Mode Labels
MODE_LABEL_HYBRID: Final[dict[str, str]] = {
    LANG_FA: "ترکیبی (Hybrid RAG)",
    LANG_EN: "Hybrid RAG",
}

MODE_LABEL_STRICT: Final[dict[str, str]] = {
    LANG_FA: "فقط اسناد (Strict RAG)",
    LANG_EN: "Strict RAG",
}

MODE_LABEL_LLM_ONLY: Final[dict[str, str]] = {
    LANG_FA: "فقط مدل (LLM Only)",
    LANG_EN: "LLM Only",
}

MODE_OPTIONS: Final[dict[str, list[str]]] = {
    LANG_FA: [
        MODE_LABEL_HYBRID[LANG_FA],
        MODE_LABEL_STRICT[LANG_FA],
        MODE_LABEL_LLM_ONLY[LANG_FA],
    ],
    LANG_EN: [
        MODE_LABEL_HYBRID[LANG_EN],
        MODE_LABEL_STRICT[LANG_EN],
        MODE_LABEL_LLM_ONLY[LANG_EN],
    ],
}

# Mode Descriptions
MODE_DESCRIPTIONS: Final[dict[str, dict[str, str]]] = {
    LANG_FA: {
        "hybrid": "ترکیبی هوشمند: تلفیق شواهد اسناد با دانش مدل زبانی برای تحلیل‌های جامع.",
        "strict": "فقط اسناد: پاسخ‌دهی ۱۰۰٪ مقید به اسناد بارگذاری‌شده بدون توهم (رد در صورت نبود پاسخ).",
        "llm-only": "فقط مدل: گفتگو و تحلیل مستقیم با مدل بدون جستجو در پایگاه اسناد.",
    },
    LANG_EN: {
        "hybrid": "Hybrid RAG: Synthesizes document facts with LLM intelligence for comprehensive answers.",
        "strict": "Strict RAG: 100% grounded in uploaded documents; refuses if context is missing.",
        "llm-only": "LLM Only: Direct model reasoning without querying the document database.",
    },
}

# Welcome Markdown
WELCOME_MARKDOWN: Final[dict[str, str]] = {
    LANG_FA: (
        "## به دستیار هوشمند اسناد «پارس‌رگ» (ParsRAG) خوش آمدید!\n\n"
        "این سامانه مجهز به پردازش محلی، دقیق و بدون نشت اطلاعات برای اسناد فارسی و انگلیسی است.\n\n"
        "### حالت‌های کاری سامانه:\n"
        "- **Hybrid RAG (ترکیبی - پیش‌فرض):** تلفیق هوشمندانه شواهد سند با دانش عمومی مدل زبانی.\n"
        "- **Strict RAG (فقط اسناد):** پاسخ‌دهی ۱۰۰٪ مقید به متن اسناد؛ در صورت عدم وجود پاسخ در اسناد، درخواست صریحاً رد می‌شود.\n"
        "- **LLM Only (فقط مدل):** گفتگو و تحلیل مستقیم با مدل بدون مراجعه به اسناد.\n\n"
        "### نحوه کار با اسناد:\n"
        "- می‌توانید فایل‌های خود را با فرمت‌های **PDF**، **Word (DOCX)** یا **PowerPoint (PPTX)** با دکمه سنجاق پایین پیوست کنید (حداکثر ۵ فایل در هر نشست).\n"
        "- **عمق بازیابی (Top-K):** به صورت کاملاً خودکار و پویا (Dynamic Optimization) متناسب با نوع پرسش محاسبه می‌شود.\n"
        "- برای تغییر حالت، زبان (فارسی/انگلیسی) و سایر پارامترها می‌توانید از دکمه انتخاب‌گر حالت در نوار پایین یا منوی تنظیمات استفاده فرمایید.\n\n"
        "*سند خود را بارگذاری کنید یا پرسش خود را مستقیماً بنویسید.*"
    ),
    LANG_EN: (
        "## Welcome to ParsRAG Document Assistant!\n\n"
        "A secure, air-gapped Retrieval-Augmented Generation assistant designed for accurate document analysis.\n\n"
        "### Operational RAG Modes:\n"
        "- **Hybrid RAG (Default):** Synthesizes retrieved document context with general LLM intelligence.\n"
        "- **Strict RAG (Document-Grounded):** 100% strictly bound to documents with zero external hallucination. Rejects missing answers.\n"
        "- **LLM Only:** Direct conversational reasoning with the model without retrieving documents.\n\n"
        "### Working with Documents:\n"
        "- Attach **PDF**, **Word (DOCX)**, or **PowerPoint (PPTX)** files using the attachment pin below (up to 5 files per session).\n"
        "- **Retrieval Depth (Top-K):** Dynamically optimized per query based on semantic intent and document count.\n"
        "- Switch modes, language (English/Persian), or operational thresholds anytime using the mode pill in the bottom composer or the Settings drawer.\n\n"
        "*Upload your documents or type your question directly below.*"
    ),
}

# Settings Labels & Descriptions
SETTINGS_LABELS: Final[dict[str, dict[str, str]]] = {
    LANG_FA: {
        "language_label": "زبان سامانه",
        "language_desc": "انتخاب زبان واسط کاربری و جهت نوشتاری",
        "mode_label": "حالت کاری سامانه",
        "mode_desc": "انتخاب نحوه پاسخ‌دهی و پردازش اسناد",
        "threshold_label": "آستانه شباهت مقید",
        "threshold_desc": "حداقل نمره شباهت مورد نیاز برای پذیرش شواهد سند در حالت مقید",
        "dynamic_depth_label": "بهینه‌سازی خودکار عمق بازیابی",
        "dynamic_depth_desc": "محاسبه خودکار تعداد بهینه قطعات متناسب با پیچیدگی پرسش",
        "manual_top_k_label": "عمق بازیابی دستی",
        "manual_top_k_desc": "تعداد قطعات بازیابی‌شده از پایگاه برداری در صورت غیرفعال بودن عمق خودکار",
        "history_window_label": "پنجره حافظه گفتگو",
        "history_window_desc": "حداکثر تعداد پیام‌های قبلی نگه‌داری‌شده در حافظه تعاملی",
        "backend_url_label": "آدرس سرویس بک‌اند",
        "backend_url_desc": "آدرس ریشه سرویس پاسخ‌گویی",
    },
    LANG_EN: {
        "language_label": "Interface Language",
        "language_desc": "Select display language and layout direction (RTL/LTR)",
        "mode_label": "RAG Execution Mode",
        "mode_desc": "Select how queries are answered against documents",
        "threshold_label": "Strict RAG Similarity Threshold",
        "threshold_desc": "Minimum similarity score required to accept document evidence in strict mode",
        "dynamic_depth_label": "Dynamic Retrieval Depth (Dynamic Top-K)",
        "dynamic_depth_desc": "Automatically optimizes chunk depth based on query intent and document cardinality",
        "manual_top_k_label": "Manual Retrieval Depth (Manual Top-K)",
        "manual_top_k_desc": "Number of chunks retrieved from Qdrant when dynamic depth is disabled",
        "history_window_label": "Chat History Memory Window (Turns)",
        "history_window_desc": "Maximum past messages preserved in conversational context",
        "backend_url_label": "Backend Service URL",
        "backend_url_desc": "Root API URL for the ParsRAG FastAPI backend",
    },
}


def normalize_language(lang_code: str | None) -> str:
    """Normalizes language string to 'fa' or 'en'."""
    if not lang_code:
        return LANG_FA
    clean = lang_code.strip().lower()
    if clean.startswith("en") or "english" in clean or "انگلیسی" in clean:
        return LANG_EN
    return LANG_FA


def get_welcome_markdown(lang: str = LANG_FA) -> str:
    """Returns the welcome markdown in the requested language."""
    return WELCOME_MARKDOWN.get(normalize_language(lang), WELCOME_MARKDOWN[LANG_FA])


def get_mode_options(lang: str = LANG_FA) -> list[str]:
    """Returns list of mode labels for settings dropdown."""
    return MODE_OPTIONS.get(normalize_language(lang), MODE_OPTIONS[LANG_FA])


def get_settings_labels(lang: str = LANG_FA) -> dict[str, str]:
    """Returns settings labels and descriptions in the requested language."""
    return SETTINGS_LABELS.get(normalize_language(lang), SETTINGS_LABELS[LANG_FA])


def format_settings_updated(
    lang: str,
    raw_mode: str,
    normalized_mode: str,
    dynamic_depth: bool = True,
    top_k: int | None = None,
    threshold: float = 0.80,
) -> str:
    """Formats the confirmation message when chat settings are modified."""
    norm_lang = normalize_language(lang)
    if norm_lang == LANG_EN:
        depth_str = "Automated (Dynamic)" if dynamic_depth else f"{top_k} chunks"
        return (
            f"**Settings Updated:**\n"
            f"- **Active Mode:** `{raw_mode}` (`{normalized_mode}`)\n"
            f"- **Retrieval Depth:** `{depth_str}`\n"
            f"- **Strict Threshold:** `{threshold:.2f}`"
        )
    depth_str = "محاسبه خودکار و پویا" if dynamic_depth else f"{top_k} قطعه (دستی)"
    return (
        f"**تنظیمات به‌روزرسانی شد:**\n"
        f"- **حالت فعال:** `{raw_mode}` (`{normalized_mode}`)\n"
        f"- **عمق بازیابی:** `{depth_str}`\n"
        f"- **آستانه شباهت Strict:** `{threshold:.2f}`"
    )


def format_language_switched(lang: str) -> str:
    """Formats notice when user changes language."""
    norm_lang = normalize_language(lang)
    if norm_lang == LANG_EN:
        return "**Language switched to English.** Layout direction is now Left-to-Right (LTR)."
    return "**زبان سامانه به فارسی تغییر یافت.** چیدمان صفحه راست‌به‌چپ (RTL) شد."


def format_file_limit_exceeded(
    lang: str, current_count: int, new_count: int, max_limit: int
) -> str:
    """Formats the error message when uploaded files exceed session capacity."""
    norm_lang = normalize_language(lang)
    if norm_lang == LANG_EN:
        return (
            f"**Document Limit Exceeded:** A maximum of {max_limit} files is allowed per session.\n"
            f"Existing files: {current_count} | New files: {new_count}"
        )
    return (
        f"**محدودیت تعداد اسناد:** سقف مجاز فایل در هر نشست حداکثر {max_limit} فایل است.\n"
        f"تعداد فایل‌های قبلی: {current_count} | فایل‌های جدید: {new_count}"
    )


def format_ingest_progress(lang: str, count: int) -> str:
    """Formats in-progress message during document ingestion."""
    norm_lang = normalize_language(lang)
    if norm_lang == LANG_EN:
        return (
            f"Processing and indexing {count} document(s) in local vector database..."
        )
    return f"در حال پردازش و نمایه‌سازی {count} فایل در پایگاه برداری..."


def format_ingest_success(
    lang: str, backend_message: str, active_files: list[str]
) -> str:
    """Formats success message after documents are ingested into Qdrant."""
    norm_lang = normalize_language(lang)
    files_list_md = "\n".join([f"- `{f}`" for f in active_files])
    if norm_lang == LANG_EN:
        return (
            f"**Indexing Completed Successfully!**\n\n"
            f"{backend_message}\n\n"
            f"**Active Documents in Session:**\n{files_list_md}"
        )
    return (
        f"**نمایه‌سازی با موفقیت انجام شد!**\n\n"
        f"{backend_message}\n\n"
        f"**اسناد فعال در این نشست:**\n{files_list_md}"
    )


def format_ingest_error(lang: str, error_detail: str) -> str:
    """Formats error message when document ingestion fails."""
    norm_lang = normalize_language(lang)
    if norm_lang == LANG_EN:
        return f"**Document Upload Error:** {error_detail}"
    return f"**خطا در بارگذاری سند:** {error_detail}"


def format_query_error(lang: str, error_detail: str) -> str:
    """Formats error message when a RAG query fails."""
    norm_lang = normalize_language(lang)
    if norm_lang == LANG_EN:
        return (
            f"**Query Processing Error:**\n\n"
            f"> {error_detail}\n\n"
            f"Please ensure the backend service is running or check your RAG settings."
        )
    return (
        f"**خطا در پردازش پرسش:**\n\n"
        f"> {error_detail}\n\n"
        f"لطفاً مطمئن شوید سرویس بک‌اند فعال است یا تنظیمات RAG را بررسی فرمایید."
    )


def format_citation_title(lang: str, index: int, filename: str) -> str:
    """Formats the citation element title."""
    norm_lang = normalize_language(lang)
    if norm_lang == LANG_EN:
        return f"Source {index}: {filename}"
    return f"منبع {index}: {filename}"


def format_citation_body(
    lang: str, text: str, score: float | None, filename: str
) -> str:
    """Formats citation element markdown body."""
    norm_lang = normalize_language(lang)
    if norm_lang == LANG_EN:
        score_text = (
            f"**Similarity Score:** `{score:.4f}`"
            if score is not None
            else "**Score:** `N/A`"
        )
        return (
            f"### `{filename}`\n{score_text}\n\n---\n\n**Extracted Text:**\n\n> {text}"
        )
    score_text = (
        f"**امتیاز شباهت:** `{score:.4f}`"
        if score is not None
        else "**امتیاز:** `بدون امتیاز عددی`"
    )
    return f"### `{filename}`\n{score_text}\n\n---\n\n**متن استخراج‌شده:**\n\n> {text}"
