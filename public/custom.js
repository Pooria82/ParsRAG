/**
 * ParsRAG Modern Chatbot UI Controller
 * - Adaptive upward/downward mode selection dropdown matching premier conversational bots (ChatGPT/Claude).
 * - Instant bilingual language switching (Persian RTL <-> English LTR).
 * - Seamless synchronization with backend session state.
 */

(function () {
    "use strict";

    const SVG_ICONS = {
        hybrid: `<svg class="parsrag-svg-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`,
        strict: `<svg class="parsrag-svg-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>`,
        llmOnly: `<svg class="parsrag-svg-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v4"/><path d="M12 18v4"/><path d="m4.93 4.93 2.83 2.83"/><path d="m16.24 16.24 2.83 2.83"/><path d="M2 12h4"/><path d="M18 12h4"/><path d="m4.93 19.07 2.83-2.83"/><path d="m16.24 7.76 2.83-2.83"/></svg>`,
        globe: `<svg class="parsrag-svg-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20"/><path d="M2 12h20"/></svg>`,
        check: `<svg class="parsrag-svg-icon parsrag-check-svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`
    };

    const DICTIONARY = {
        "Light Theme": "قالب روشن",
        "Dark Theme": "قالب تاریک",
        "Follow System": "پیروی از سیستم",
        "Create New Chat": "ایجاد گفتگوی جدید",
        "This will clear your current chat history. Are you sure you want to continue?": "این کار تاریخچه گفتگوی فعلی شما را پاک می‌کند. آیا مطمئن هستید؟",
        "Confirm": "تایید",
        "Cancel": "انصراف",
        "LLMs can make mistakes. Check important info.": "مدل‌های زبانی ممکن است اشتباه کنند. اطلاعات مهم را بررسی کنید.",
        "Settings": "تنظیمات",
        "Settings panel": "پنل تنظیمات",
        "Reset": "بازنشانی",
        "Readme": "راهنما"
    };

    function translateDOMNodes(node) {
        if (!node) return;
        if (node.nodeType === 3) {
            const text = node.nodeValue.trim();
            if (!text) return;
            
            // Skip elements that contain generated output (to avoid translating user's chat)
            const parent = node.parentElement;
            if (parent && (parent.closest('.cl-message') || parent.closest('.parsrag-dropdown-menu'))) return;
            
            let original = parent.getAttribute("data-original-text");
            if (!original) {
                // If it's the first time and we are currently rendering English text
                if (DICTIONARY[text] || currentLang === "en") {
                    original = text;
                    parent.setAttribute("data-original-text", original);
                }
            }
            
            if (original) {
                if (currentLang === "fa" && DICTIONARY[original]) {
                    node.nodeValue = node.nodeValue.replace(text, DICTIONARY[original]);
                } else if (currentLang === "en" && original !== text) {
                    node.nodeValue = node.nodeValue.replace(text, original);
                }
            }
        } else if (node.nodeType === 1 && node.tagName !== "SCRIPT" && node.tagName !== "STYLE") {
            if (node.placeholder) {
                let original = node.getAttribute("data-original-placeholder") || node.placeholder;
                node.setAttribute("data-original-placeholder", original);
                if (currentLang === "fa" && DICTIONARY[original]) {
                    node.placeholder = DICTIONARY[original];
                } else if (currentLang === "en") {
                    node.placeholder = original;
                }
            }
            node.childNodes.forEach(translateDOMNodes);
        }
    }

    const MODES = {
        hybrid: {
            id: "hybrid",
            iconSvg: SVG_ICONS.hybrid,
            label: { fa: "ترکیبی (Hybrid RAG)", en: "Hybrid RAG" },
            desc: {
                fa: "تلفیق هوشمند شواهد سند با مدل زبانی",
                en: "Synthesizes document facts with LLM reasoning",
            },
        },
        strict: {
            id: "strict",
            iconSvg: SVG_ICONS.strict,
            label: { fa: "فقط اسناد (Strict RAG)", en: "Strict RAG" },
            desc: {
                fa: "پاسخ‌دهی ۱۰۰٪ مقید به متن اسناد بدون توهم",
                en: "100% grounded in documents, zero hallucination",
            },
        },
        "llm-only": {
            id: "llm-only",
            iconSvg: SVG_ICONS.llmOnly,
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
            pillIcon.innerHTML = modeData.iconSvg;
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
        const rect = triggerBtn.getBoundingClientRect();
        const viewportHeight = window.innerHeight;
        const spaceBelow = viewportHeight - rect.bottom;

        // Since it's inside the composer, open upward by default
        const openUpward = true;

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
                    <span id="parsrag-mode-icon" class="parsrag-icon">${currentModeData.iconSvg}</span>
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
                                <span class="parsrag-item-icon">${m.iconSvg}</span>
                                <div class="parsrag-item-text">
                                    <div class="parsrag-item-title">${m.label[currentLang]}</div>
                                    <div class="parsrag-item-desc">${m.desc[currentLang]}</div>
                                </div>
                            </div>
                            <span class="parsrag-check-icon" style="visibility: ${m.id === currentMode ? "visible" : "hidden"};">${SVG_ICONS.check}</span>
                        </div>
                    `
                        )
                        .join("")}
                </div>
            </div>
        `;

        // Insert inside the composer at the top
        const targetContainer = composer.querySelector('textarea')?.parentElement || composer;
        if (!targetContainer.querySelector('#parsrag-bottom-bar')) {
            targetContainer.insertBefore(container, targetContainer.firstChild);
        }

        // Bind click events
        document.getElementById("parsrag-mode-pill")?.addEventListener("click", toggleModeDropdown);

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

    // Global document click closes dropdown and handles language selection
    document.addEventListener("click", (e) => {
        const text = e.target.textContent;
        if (text === "فارسی" || text === "Persian") {
            applyDirectionAndLocale("fa");
        } else if (text === "انگلیسی" || text === "English") {
            applyDirectionAndLocale("en");
        }

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
    const observer = new MutationObserver((mutations) => {
        buildChatbotModeBar();
        updateInputPlaceholder();

        // Check dynamic depth toggle to disable manual depth
        const autoSwitch = document.querySelector('input[name="dynamic_depth"]');
        if (autoSwitch) {
            // Wait, chainlit renders settings with IDs based on widget id
            const manualSlider = document.getElementById('manual_top_k');
            if (manualSlider) {
                const manualContainer = manualSlider.closest('.MuiBox-root') || manualSlider.parentElement;
                if (manualContainer) {
                    if (autoSwitch.checked) {
                        manualContainer.style.pointerEvents = "none";
                        manualContainer.style.opacity = "0.4";
                    } else {
                        manualContainer.style.pointerEvents = "auto";
                        manualContainer.style.opacity = "1";
                    }
                }
            }
        }
        
        let languageChanged = false;
        mutations.forEach(mutation => {
            if (mutation.type === "childList") {
                mutation.addedNodes.forEach(node => {
                    if (node.nodeType === 1) {
                        const text = node.textContent || "";
                        if (text.includes("Layout direction is now Left-to-Right")) {
                            if (currentLang !== "en") applyDirectionAndLocale("en");
                        } else if (text.includes("چیدمان صفحه راست‌به‌چپ (RTL) شد")) {
                            if (currentLang !== "fa") applyDirectionAndLocale("fa");
                        }
                    }
                });
            }
        });
        
        // Translate nodes inside modal or other new elements if they are added
        if (!languageChanged) {
             mutations.forEach(mutation => {
                mutation.addedNodes.forEach(node => {
                   if (node.nodeType === 1) translateDOMNodes(node);
                });
             });
        }
    });

    // Start on DOM ready
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => {
            applyDirectionAndLocale(currentLang);
            translateDOMNodes(document.body);
            buildChatbotModeBar();
            observer.observe(document.body, { childList: true, subtree: true });
        });
    } else {
        applyDirectionAndLocale(currentLang);
        translateDOMNodes(document.body);
        buildChatbotModeBar();
        observer.observe(document.body, { childList: true, subtree: true });
    }
})();
