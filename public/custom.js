/**
 * ParsRAG Modern Chatbot UI Controller
 * - Adaptive upward/downward mode selection dropdown matching premier conversational bots (ChatGPT/Claude).
 * - Instant bilingual language switching (Persian RTL <-> English LTR).
 * - Seamless synchronization with backend session state.
 */

(function () {
    "use strict";

    const MODES = {
        hybrid: {
            id: "hybrid",
            icon: "⚡",
            label: { fa: "ترکیبی (Hybrid RAG)", en: "Hybrid RAG" },
            desc: {
                fa: "تلفیق هوشمند شواهد سند با مدل زبانی",
                en: "Synthesizes document facts with LLM reasoning",
            },
        },
        strict: {
            id: "strict",
            icon: "🔒",
            label: { fa: "فقط اسناد (Strict RAG)", en: "Strict RAG" },
            desc: {
                fa: "پاسخ‌دهی ۱۰۰٪ مقید به متن اسناد بدون توهم",
                en: "100% grounded in documents, zero hallucination",
            },
        },
        "llm-only": {
            id: "llm-only",
            icon: "💡",
            label: { fa: "فقط مدل (LLM Only)", en: "LLM Only" },
            desc: {
                fa: "گفتگو و استدلال مستقیم بدون جستجوی اسناد",
                en: "Direct conversational reasoning without search",
            },
        },
    };

    let currentLang = localStorage.getItem("parsrag_lang") || "fa";
    let currentMode = localStorage.getItem("parsrag_mode") || "hybrid";

    function applyDirectionAndLocale(lang) {
        currentLang = lang;
        localStorage.setItem("parsrag_lang", lang);

        const isFa = lang === "fa";
        document.documentElement.setAttribute("dir", isFa ? "rtl" : "ltr");
        document.documentElement.setAttribute("lang", isFa ? "fa" : "en");
        document.body.setAttribute("data-lang", isFa ? "fa" : "en");

        if (isFa) {
            document.body.classList.add("parsrag-rtl");
            document.body.classList.remove("parsrag-ltr");
        } else {
            document.body.classList.add("parsrag-ltr");
            document.body.classList.remove("parsrag-rtl");
        }

        // Update Chat Input Placeholder
        updateInputPlaceholder();

        // Update UI Button Texts
        updatePillButtonUI();
    }

    function updateInputPlaceholder() {
        const textarea = document.querySelector("textarea") || document.querySelector("input[type='text']");
        if (textarea) {
            const isFa = currentLang === "fa";
            textarea.placeholder = isFa
                ? "پیام یا پرسش خود را اینجا بنویسید (Shift+Enter برای خط جدید)..."
                : "Type your message or question here (Shift+Enter for new line)...";
            textarea.style.direction = isFa ? "rtl" : "ltr";
            textarea.style.textAlign = isFa ? "right" : "left";
        }
    }

    function sendSystemCommand(commandText) {
        const textarea = document.querySelector("textarea") || document.querySelector("input[type='text']");
        if (!textarea) return;

        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
            window.HTMLTextAreaElement.prototype,
            "value"
        ).set;
        nativeInputValueSetter.call(textarea, commandText);

        textarea.dispatchEvent(new Event("input", { bubbles: true }));

        setTimeout(() => {
            // Find send button or trigger Enter
            const submitBtn = document.querySelector("button[type='submit']") ||
                              document.querySelector("button#submit-button") ||
                              document.querySelector("button:has(svg)");
            if (submitBtn && !submitBtn.disabled) {
                submitBtn.click();
            } else {
                textarea.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", code: "Enter", bubbles: true }));
            }
        }, 80);
    }

    function updatePillButtonUI() {
        const pillText = document.getElementById("parsrag-mode-label");
        const pillIcon = document.getElementById("parsrag-mode-icon");
        const langBtn = document.getElementById("parsrag-lang-toggle");

        const modeData = MODES[currentMode] || MODES.hybrid;
        if (pillText) {
            pillText.textContent = modeData.label[currentLang] || modeData.label.en;
        }
        if (pillIcon) {
            pillIcon.textContent = modeData.icon;
        }
        if (langBtn) {
            langBtn.textContent = currentLang === "fa" ? "🌐 EN" : "🌐 FA";
            langBtn.title = currentLang === "fa" ? "Switch to English (LTR)" : "تغییر به فارسی (RTL)";
        }

        // Update active checkmarks in menu
        document.querySelectorAll(".parsrag-mode-item").forEach((item) => {
            const modeId = item.getAttribute("data-mode");
            const checkIcon = item.querySelector(".parsrag-check-icon");
            if (modeId === currentMode) {
                item.classList.add("active");
                if (checkIcon) checkIcon.style.visibility = "visible";
            } else {
                item.classList.remove("active");
                if (checkIcon) checkIcon.style.visibility = "hidden";
            }
        });
    }

    function toggleModeDropdown(e) {
        if (e) e.stopPropagation();
        const menu = document.getElementById("parsrag-mode-dropdown");
        const triggerBtn = document.getElementById("parsrag-mode-pill");
        if (!menu || !triggerBtn) return;

        const isExpanded = menu.classList.contains("show");
        if (isExpanded) {
            closeModeDropdown();
            return;
        }

        // Adaptive Direction Detection:
        // Measure viewport coordinates
        const rect = triggerBtn.getBoundingClientRect();
        const viewportHeight = window.innerHeight;
        const spaceBelow = viewportHeight - rect.bottom;

        // If positioned at bottom of screen (< 270px below or rect in lower 65% of viewport), open UPWARD
        const openUpward = spaceBelow < 270 || rect.bottom > viewportHeight * 0.65;

        if (openUpward) {
            menu.classList.remove("open-down");
            menu.classList.add("open-up");
        } else {
            menu.classList.remove("open-up");
            menu.classList.add("open-down");
        }

        menu.classList.add("show");
        triggerBtn.setAttribute("aria-expanded", "true");
    }

    function closeModeDropdown() {
        const menu = document.getElementById("parsrag-mode-dropdown");
        const triggerBtn = document.getElementById("parsrag-mode-pill");
        if (menu) {
            menu.classList.remove("show");
            menu.classList.remove("open-up");
            menu.classList.remove("open-down");
        }
        if (triggerBtn) {
            triggerBtn.setAttribute("aria-expanded", "false");
        }
    }

    function selectMode(modeId) {
        if (!MODES[modeId]) return;
        currentMode = modeId;
        localStorage.setItem("parsrag_mode", modeId);

        updatePillButtonUI();
        closeModeDropdown();

        // Send silent control sync to session
        sendSystemCommand(`/mode ${modeId}`);
    }

    function toggleLanguage() {
        const nextLang = currentLang === "fa" ? "en" : "fa";
        applyDirectionAndLocale(nextLang);
        sendSystemCommand(`/lang ${nextLang}`);
    }

    function buildChatbotModeBar() {
        if (document.getElementById("parsrag-bottom-bar")) return;

        // Find the composer container
        const composer =
            document.querySelector("[data-testid='chat-input']")?.closest("div") ||
            document.querySelector("textarea")?.closest("form") ||
            document.querySelector("textarea")?.parentElement?.parentElement ||
            document.querySelector(".cl-composer");

        if (!composer) return;

        const container = document.createElement("div");
        container.id = "parsrag-bottom-bar";
        container.className = "parsrag-bottom-bar";

        const currentModeData = MODES[currentMode] || MODES.hybrid;

        container.innerHTML = `
            <div class="parsrag-selector-wrapper">
                <button type="button" id="parsrag-mode-pill" class="parsrag-pill-btn" aria-haspopup="true" aria-expanded="false">
                    <span id="parsrag-mode-icon" class="parsrag-icon">${currentModeData.icon}</span>
                    <span id="parsrag-mode-label" class="parsrag-mode-label">${currentModeData.label[currentLang]}</span>
                    <svg class="parsrag-chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <path d="m6 9 6 6 6-6"/>
                    </svg>
                </button>

                <div id="parsrag-mode-dropdown" class="parsrag-dropdown-menu" role="menu">
                    <div class="parsrag-dropdown-header">
                        ${currentLang === "fa" ? "انتخاب حالت کاری" : "Select RAG Mode"}
                    </div>
                    ${Object.values(MODES)
                        .map(
                            (m) => `
                        <div class="parsrag-mode-item ${m.id === currentMode ? "active" : ""}" data-mode="${m.id}" role="menuitem" tabindex="0">
                            <div class="parsrag-mode-item-left">
                                <span class="parsrag-item-icon">${m.icon}</span>
                                <div class="parsrag-item-text">
                                    <div class="parsrag-item-title">${m.label[currentLang]}</div>
                                    <div class="parsrag-item-desc">${m.desc[currentLang]}</div>
                                </div>
                            </div>
                            <span class="parsrag-check-icon" style="visibility: ${m.id === currentMode ? "visible" : "hidden"};">✓</span>
                        </div>
                    `
                        )
                        .join("")}
                </div>
            </div>

            <div class="parsrag-actions-wrapper">
                <button type="button" id="parsrag-lang-toggle" class="parsrag-lang-btn" title="Toggle Language">
                    ${currentLang === "fa" ? "🌐 EN" : "🌐 FA"}
                </button>
            </div>
        `;

        // Insert before or at the start of composer
        composer.parentElement.insertBefore(container, composer);

        // Bind click events
        document.getElementById("parsrag-mode-pill")?.addEventListener("click", toggleModeDropdown);
        document.getElementById("parsrag-lang-toggle")?.addEventListener("click", toggleLanguage);

        document.querySelectorAll(".parsrag-mode-item").forEach((item) => {
            item.addEventListener("click", (e) => {
                const modeId = item.getAttribute("data-mode");
                selectMode(modeId);
            });
            item.addEventListener("keydown", (e) => {
                if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    const modeId = item.getAttribute("data-mode");
                    selectMode(modeId);
                }
            });
        });
    }

    // Global document click closes dropdown
    document.addEventListener("click", (e) => {
        const dropdown = document.getElementById("parsrag-mode-dropdown");
        const trigger = document.getElementById("parsrag-mode-pill");
        if (dropdown && trigger && !trigger.contains(e.target) && !dropdown.contains(e.target)) {
            closeModeDropdown();
        }
    });

    // Keyboard ESC closes dropdown
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            closeModeDropdown();
        }
    });

    // Window resize / scroll updates orientation if open
    window.addEventListener("resize", () => {
        const menu = document.getElementById("parsrag-mode-dropdown");
        if (menu && menu.classList.contains("show")) {
            closeModeDropdown();
        }
    });

    // Initialize observer to mount UI components and maintain direction
    const observer = new MutationObserver(() => {
        buildChatbotModeBar();
        updateInputPlaceholder();
    });

    // Start on DOM ready
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => {
            applyDirectionAndLocale(currentLang);
            buildChatbotModeBar();
            observer.observe(document.body, { childList: true, subtree: true });
        });
    } else {
        applyDirectionAndLocale(currentLang);
        buildChatbotModeBar();
        observer.observe(document.body, { childList: true, subtree: true });
    }
})();
