# Repository discovery settings

After the local changes are published, set the following in the repository's
**About** panel. These settings are managed by GitHub, so this file is the
reviewable source for the intended public metadata.

- **Description:** `Private Persian/English document RAG with local OCR, cited answers, Ollama and OpenAI-compatible APIs.`
- **Topics:** `rag`, `retrieval-augmented-generation`, `persian`, `farsi`,
  `document-qa`, `offline-first`, `ollama`, `qdrant`, `ocr`, `fastapi`, `react`,
  `local-llm`.
- **Website:** leave blank until a maintained project website exists.
- **Social preview:** upload [the project-owned 1280×640 image](social-preview.png).
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
