"""Centralized Persian UI strings, message templates, and markdown constants."""

WELCOME_MARKDOWN: str = (
    "## 👋 به دستیار هوشمند اسناد «پارس‌رگ» (ParsRAG) خوش آمدید!\n\n"
    "این سامانه مجهز به پردازش محلی، دقیق و بدون نشت اطلاعات برای اسناد فارسی است.\n\n"
    "### ⚙️ حالت‌های کاری سامانه:\n"
    "- **Strict RAG (فقط اسناد):** پاسخ‌دهی ۱۰۰٪ مقید به متن اسناد بارگذاری‌شده. در صورت عدم وجود پاسخ در اسناد، درخواست رد می‌شود.\n"
    "- **Hybrid RAG (ترکیبی - پیش‌فرض):** تلفیق هوشمندانه شواهد سند با دانش عمومی مدل زبانی برای پاسخ‌های جامع.\n"
    "- **LLM Only (فقط مدل):** گفتگو و تحلیل مستقیم با مدل بدون مراجعه به اسناد.\n\n"
    "### 📁 نحوه کار با اسناد:\n"
    "- می‌توانید فایل‌های خود را با فرمت‌های **PDF**، **Word (DOCX)** یا **PowerPoint (PPTX)** با دکمه سنجاق پایین پیوست کنید (حداکثر ۵ فایل در هر نشست).\n"
    "- ساختار جدول‌های پیچیده، سوابق ردیف‌ها و عناوین چندسطحی به صورت ساختاریافته ذخیره می‌شوند.\n"
    "- **عمق بازیابی و تجمیع قطعات (Top-K):** به صورت کاملاً خودکار و پویا (Dynamic Optimization) متناسب با نوع پرسش محاسبه می‌شود.\n"
    "- می‌توانید حالت کاری را از منوی تنظیمات (⚙️ در گوشه کادر پیام) انتخاب فرمایید.\n\n"
    "💬 *سند خود را بارگذاری کنید یا پرسش خود را مستقیماً بنویسید.*"
)

# Settings Strings
SETTINGS_MODE_LABEL: str = "🎯 حالت کاری سامانه (RAG Execution Mode)"
SETTINGS_MODE_DESC: str = (
    "Strict: فقط اسناد | Hybrid: تلفیق اسناد و مدل | LLM Only: بدون مراجعه به اسناد"
)

MODE_OPTION_HYBRID: str = "Hybrid RAG"
MODE_OPTION_STRICT: str = "Strict RAG"
MODE_OPTION_LLM_ONLY: str = "LLM Only"
AVAILABLE_MODE_OPTIONS: list[str] = [
    MODE_OPTION_HYBRID,
    MODE_OPTION_STRICT,
    MODE_OPTION_LLM_ONLY,
]


# Notifications & Status Templates
def format_settings_updated(
    raw_mode: str, normalized_mode: str, top_k: int | None = None
) -> str:
    """Formats the confirmation message when chat settings change."""
    depth_label = (
        f"{top_k} (سفارشی)" if top_k is not None else "محاسبه خودکار و پویا (Dynamic)"
    )
    return (
        f"⚙️ **تنظیمات به‌روزرسانی شد:**\n"
        f"- **حالت فعال:** `{raw_mode}` (`{normalized_mode}`)\n"
        f"- **عمق بازیابی:** `{depth_label}`"
    )


def format_file_limit_exceeded(
    current_count: int, new_count: int, max_limit: int
) -> str:
    """Formats the error message when uploaded files exceed the batch limit."""
    return (
        f"⚠️ **محدودیت تعداد اسناد:** سقف مجاز فایل در هر نشست حداکثر {max_limit} فایل است.\n"
        f"تعداد فایل‌های قبلی: {current_count} | فایل‌های جدید: {new_count}"
    )


def format_ingest_progress(count: int) -> str:
    """Formats the in-progress message during document chunking & ingestion."""
    return f"⏳ در حال پردازش و نمایه‌سازی {count} فایل در پایگاه برداری..."


def format_ingest_success(backend_message: str, active_files: list[str]) -> str:
    """Formats the completion message after documents are ingested into Qdrant."""
    files_list_md = "\n".join([f"- 📄 `{f}`" for f in active_files])
    return (
        f"✅ **نمایه‌سازی با موفقیت انجام شد!**\n\n"
        f"{backend_message}\n\n"
        f"**اسناد فعال در این نشست:**\n{files_list_md}"
    )


def format_ingest_error(error_detail: str) -> str:
    """Formats the error message when document ingestion fails."""
    return f"❌ **خطا در بارگذاری سند:** {error_detail}"


def format_query_error(error_detail: str) -> str:
    """Formats the error message when a RAG query fails."""
    return (
        f"⚠️ **خطا در پردازش پرسش:**\n\n"
        f"> {error_detail}\n\n"
        f"لطفاً مطمئن شوید سرویس بک‌اند فعال است یا تنظیمات RAG را بررسی فرمایید."
    )
