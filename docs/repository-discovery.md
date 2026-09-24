# Repository discovery settings

The public repository's **About** panel already contains a relevant description
and topics (checked September 24, 2026). Recheck them after publishing the
next version; GitHub manages these fields separately from repository files.

- **Current description:** `A private, offline-first RAG workspace for Persian
  and English documents. Features native extraction, local OCR, strict
  evidence-based answers, and flexible support for Ollama or OpenAI-compatible
  APIs.`
- **Current topics:** `bilingual`, `document-chat`, `document-qa`, `farsi`,
  `fastapi`, `local-ai`, `ocr`, `offline-first`, `ollama`, `persian`, `qdrant`,
  `rag`, `react`, `retrieval-augmented-generation`, `source-available`.
- **Website:** leave blank until a maintained project website exists.
- **Social preview:** check the GitHub repository settings and upload
  [the project-owned 1280×640 image](social-preview.png) if it is not already set.
  It contains only the ParsRAG mark, name, and feature summary. Regenerate it
  with `node frontend/scripts/generate-social-preview.mjs` after `npm ci` if the
  branding changes.

The English and Persian READMEs already describe the product, supported input
types, deployment, source citations, license, and contributor process. Keep
their screenshots and feature claims aligned with the released version.

GitHub topics and README content improve discovery within GitHub. Search-engine
indexing and ranking are controlled by the search provider and cannot be
guaranteed by a repository setting. See GitHub's guidance on
[repository topics](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics)
and [README content](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes).

For Google discovery, keep the repository public and linked from a maintained
page you control (for example, a project website or an academic profile). If
you create a website on your own domain, verify that domain in Google Search
Console and submit its sitemap. Search Console cannot be used to request
indexing for a GitHub repository URL unless you control the verified property.
Google explicitly does not guarantee indexing or search ranking.
See [Google's indexing FAQ](https://developers.google.com/search/help/crawling-index-faq)
and [URL Inspection guidance](https://developers.google.com/search/docs/crawling-indexing/ask-google-to-recrawl).
