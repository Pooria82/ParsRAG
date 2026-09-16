import { Language } from '../types';

export const translations = {
  fa: {
    appName: 'پارس‌رگ',
    appSubtitle: 'دستیار هوشمند بازیابی اطلاعات و اسناد',
    newChat: 'گفتگوی جدید',
    newChatShortcut: 'Ctrl+N',
    today: 'امروز',
    yesterday: 'دیروز',
    previous: 'روزهای گذشته',
    noChats: 'هنوز گفتگویی ثبت نشده است',
    rename: 'تغییر نام',
    delete: 'حذف',
    deleteConfirmTitle: 'آیا از حذف این گفتگو اطمینان دارید؟',
    deleteConfirmDesc: 'با حذف گفتگو، تمامی پیام‌ها و پیوندهای اسناد این سشن پاک خواهند شد.',
    cancel: 'انصراف',
    confirm: 'تأیید',
    save: 'ذخیره',
    
    // Document Center (Dedicated Knowledge Base)
    docCenterTitle: 'اسناد مرجع سشن',
    docCenterLimit: 'حداکثر ۵ سند',
    docCenterCounter: (current: number, max: number) => `${current} از ${max} سند بارگذاری شده`,
    docDropzonePrompt: 'برای افزودن سند، فایل‌ها را اینجا بکشید یا کلیک کنید',
    docDropzoneSub: 'فرمت‌های مجاز: PDF، DOCX، TXT (حداکثر ۵۰ مگابایت)',
    docLimitReached: 'سقف ۵ سند برای این گفتگو تکمیل شده است.',
    docUploading: 'در حال پردازش و برداری‌سازی...',
    docIndexed: 'آماده استعلام',
    docError: 'خطا در پردازش سند',
    deleteDoc: 'حذف سند',
    
    // RAG Modes
    ragModes: {
      hybrid: {
        label: 'حالت ترکیبی (Hybrid RAG)',
        short: 'ترکیبی',
        desc: 'ترکیب هوشمند اطلاعات بازیابی‌شده از اسناد محلی با پایگاه دانش مدل زبانی.',
      },
      strict: {
        label: 'حالت دقیق (Strict RAG)',
        short: 'دقیق (فقط اسناد)',
        desc: 'پاسخ‌دهی منحصراً بر اساس متون یافت‌شده در اسناد، بدون هیچ‌گونه توهم یا دانش فراتر.',
      },
      'llm-only': {
        label: 'حالت فقط مدل (LLM Only)',
        short: 'فقط مدل',
        desc: 'گفتگوی مستقیم با مدل هوش مصنوعی بدون ارجاع یا جستجو در اسناد بارگذاری‌شده.',
      },
    },
    
    // Chat & Composer
    heroGreeting: 'سلام! چطور می‌توانم کمکتان کنم؟',
    heroDescription: 'اسناد مدنظر خود را در کادر بالای صفحه اضافه کنید و هر سوالی دارید بپرسید.',
    starterPrompts: [
      {
        title: 'خلاصه‌سازی اسناد',
        desc: 'مهم‌ترین نکات و خلاصه اسناد سشن را بنویس',
      },
      {
        title: 'استخراج داده‌های کلیدی',
        desc: 'آمار، ارقام و تاریخ‌های مهم متن را استخراج کن',
      },
      {
        title: 'پرسش و پاسخ تحلیلی',
        desc: 'تضادها و اشتراکات اسناد را با هم مقایسه کن',
      },
    ],
    composerPlaceholder: 'پیام خود را بنویسید... (Enter برای ارسال، Shift+Enter برای خط جدید)',
    send: 'ارسال پیام',
    stop: 'توقف پاسخ',
    thinking: 'در حال تفکر و پردازش...',
    searchingDocs: 'در حال جستجو در میان اسناد سشن...',
    copyCode: 'کپی کد',
    copied: 'کپی شد!',
    citationsTitle: 'منابع و مراجع مورد استفاده',
    similarityScore: 'شباهت محتوایی',
    chunkPreview: 'بخشی از قطعه متنی',
    noCitations: 'پاسخ بدون ارجاع مستقیم به اسناد تولید شده است.',
    
    // Settings Modal
    settingsTitle: 'تنظیمات سامانه',
    tabGeneral: 'عمومی و ظاهر',
    tabRAG: 'تنظیمات RAG',
    tabModel: 'مدل و سرور',
    languageLabel: 'زبان رابط کاربری',
    themeLabel: 'حالت نمایش',
    themeDark: 'تاریک (OLED)',
    themeLight: 'روشن',
    defaultModeLabel: 'حالت پیش‌فرض بازیابی',
    strictThresholdLabel: 'آستانه پذیرش اسناد (Strict Threshold)',
    strictThresholdDesc: 'حداقل درصد شباهت قطعات متنی برای پذیرفته‌شدن در پاسخ‌دهی Strict',
    dynamicDepthLabel: 'بهینه‌سازی خودکار عمق بازیابی (Dynamic Top-K)',
    dynamicDepthDesc: 'تعداد قطعات بازیافتی با توجه به اندازه متن سند به صورت پویا محاسبه شود',
    manualTopKLabel: 'عمق بازیابی دستی (Top-K)',
    manualTopKDesc: 'تعداد قطعات متنی برتر که برای تولید پاسخ فراخوانی می‌شوند',
    selectedModelLabel: 'مدل زبانی محلی (Ollama)',
    backendUrlLabel: 'آدرس سرویس بک‌اند',
    airGappedNotice: 'سیستم به صورت کاملاً ایزوله، محلی و بدون خروج اطلاعات کار می‌کند.',
    clearAllData: 'پاک‌سازی کامل تاریخچه گفتگوها',
    clearAllConfirm: 'آیا مایلید تمام گفتگوها از حافظه محلی مرورگر پاک شوند؟',
    
    // Status
    backendOnline: 'سرویس محلی فعال',
    backendOffline: 'عدم دسترسی به بک‌اند',
    filesTotal: 'تعداد اسناد',
  },
  en: {
    appName: 'ParsRAG',
    appSubtitle: 'Intelligent Air-Gapped Document RAG Assistant',
    newChat: 'New Chat',
    newChatShortcut: 'Ctrl+N',
    today: 'Today',
    yesterday: 'Yesterday',
    previous: 'Previous Days',
    noChats: 'No conversations yet',
    rename: 'Rename',
    delete: 'Delete',
    deleteConfirmTitle: 'Are you sure you want to delete this chat?',
    deleteConfirmDesc: 'Deleting this chat will permanently remove all associated messages and document links in this session.',
    cancel: 'Cancel',
    confirm: 'Confirm',
    save: 'Save',
    
    // Document Center
    docCenterTitle: 'Session Knowledge Base',
    docCenterLimit: 'Max 5 Documents',
    docCenterCounter: (current: number, max: number) => `${current} of ${max} documents uploaded`,
    docDropzonePrompt: 'Drag and drop documents here or click to browse',
    docDropzoneSub: 'Supported formats: PDF, DOCX, TXT (up to 50MB)',
    docLimitReached: 'Session capacity of 5 documents has been reached.',
    docUploading: 'Parsing and indexing into vector database...',
    docIndexed: 'Indexed & Ready',
    docError: 'Failed to process document',
    deleteDoc: 'Remove document',
    
    // RAG Modes
    ragModes: {
      hybrid: {
        label: 'Hybrid RAG',
        short: 'Hybrid',
        desc: 'Combines retrieved local document context with the LLM world knowledge.',
      },
      strict: {
        label: 'Strict RAG (Docs Only)',
        short: 'Strict',
        desc: 'Answers strictly from indexed documents. Refuses to answer if context is absent.',
      },
      'llm-only': {
        label: 'LLM Only',
        short: 'LLM Only',
        desc: 'Direct conversation with the language model without searching vector storage.',
      },
    },
    
    // Chat & Composer
    heroGreeting: 'How can I help you today?',
    heroDescription: 'Attach documents to the session knowledge base above and start asking questions.',
    starterPrompts: [
      {
        title: 'Summarize Documents',
        desc: 'Highlight the key takeaways and summarize the active documents',
      },
      {
        title: 'Extract Key Figures',
        desc: 'List important figures, metrics, and dates found in the texts',
      },
      {
        title: 'Comparative Analysis',
        desc: 'Analyze contrasting viewpoints across the uploaded files',
      },
    ],
    composerPlaceholder: 'Type a message... (Enter to send, Shift+Enter for new line)',
    send: 'Send message',
    stop: 'Stop generating',
    thinking: 'Thinking & retrieving...',
    searchingDocs: 'Searching session knowledge base...',
    copyCode: 'Copy code',
    copied: 'Copied!',
    citationsTitle: 'Retrieved Sources & Citations',
    similarityScore: 'Similarity Score',
    chunkPreview: 'Excerpt Preview',
    noCitations: 'Response generated without direct document citations.',
    
    // Settings Modal
    settingsTitle: 'System Settings',
    tabGeneral: 'General & Display',
    tabRAG: 'RAG Configuration',
    tabModel: 'Model & Server',
    languageLabel: 'Interface Language',
    themeLabel: 'Color Theme',
    themeDark: 'Dark (OLED)',
    themeLight: 'Light',
    defaultModeLabel: 'Default RAG Mode',
    strictThresholdLabel: 'Strict Acceptance Threshold',
    strictThresholdDesc: 'Minimum similarity score required to accept retrieved chunks in Strict mode',
    dynamicDepthLabel: 'Dynamic Retrieval Depth (Auto Top-K)',
    dynamicDepthDesc: 'Automatically scale chunk depth based on document volume',
    manualTopKLabel: 'Manual Retrieval Depth (Top-K)',
    manualTopKDesc: 'Fixed count of top matching chunks provided to the generator',
    selectedModelLabel: 'Local Ollama Model',
    backendUrlLabel: 'Backend API Endpoint',
    airGappedNotice: 'System runs fully local and air-gapped. Zero data leaves your machine.',
    clearAllData: 'Clear All Conversation History',
    clearAllConfirm: 'Are you sure you want to clear all conversation data from browser storage?',
    
    // Status
    backendOnline: 'Local Backend Online',
    backendOffline: 'Backend Offline',
    filesTotal: 'Documents',
  },
};

export const getTranslation = (lang: Language) => translations[lang];
