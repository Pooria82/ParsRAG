# Repository discovery settings

GitHub and search engines index the **default branch (`main`)**: its README,
the repository About panel, releases, and pages linked from elsewhere. Content
that only exists on `develop` is not what visitors or crawlers see, so publish
documentation changes through a release.

## In-repository metadata

These files carry the project's search keywords (Persian, Farsi, RAG, document
chat, OCR, local LLM, Ollama, LlamaIndex, Qdrant) and should stay aligned with
the released version:

| File | Discovery role |
| --- | --- |
| `README.md`, `README.fa.md` | Tagline and first paragraph are shown in search snippets; both link to each other |
| `CITATION.cff` | Abstract, keywords, and license URL for "Cite this repository" and scholarly indexers |
| `pyproject.toml` | Description, keywords, classifiers, and project URLs |
| `frontend/package.json` | Description, keywords, and repository links for GitHub's dependency views |
| `docs/social-preview.png` | 1280×640 card used when the repository is shared |

Regenerate the social preview with
`node frontend/scripts/generate-social-preview.mjs` after `npm ci` if the
branding changes.

## Repository settings (owner only)

GitHub stores these outside the repository; change them under **About → ⚙** or
with `gh repo edit`.

- **Description** (put the main keywords in the first ~45 characters, because
  Google titles results as `GitHub - Pooria82/ParsRAG: <description>`):

  > Offline-first Persian (Farsi) & English RAG: chat with PDF, Word, PowerPoint
  > and scanned documents using local LLMs via Ollama or OpenAI-compatible APIs.
  > Local OCR, LlamaIndex + Qdrant retrieval, strict cited answers.
  > گفت‌وگو با اسناد فارسی، آفلاین و خصوصی.

- **Topics** (20 maximum): `rag`, `retrieval-augmented-generation`, `persian`,
  `farsi`, `persian-nlp`, `document-qa`, `chat-with-pdf`, `local-llm`,
  `ollama`, `llamaindex`, `qdrant`, `ocr`, `tesseract`, `offline-first`,
  `self-hosted`, `fastapi`, `react`, `bilingual`, `rtl`, `source-available`.
- **Website:** set it once a project page exists (for example GitHub Pages).
- **Social preview:** already uploaded; replace it only if the image changes.
- **Releases:** publish each version as a GitHub Release with keyword-rich
  English and Persian notes. `CITATION.cff` and `pyproject.toml` declare the
  released version, so the matching tag must exist.

## Search engines

Google does not guarantee indexing or ranking, and Search Console cannot verify
a `github.com` repository URL. To influence discovery:

1. Keep the repository public and its README on `main` current.
2. Link to the repository from pages you control — a project website, an
   academic profile, or articles (for example on Virgool and dev.to).
3. If you publish a site you control (such as GitHub Pages), verify it in
   Google Search Console, submit its sitemap, and set it as the repository
   website.
4. Submit the project to relevant curated lists (Persian NLP, RAG, local LLM)
   so that other indexed pages link to it.

See GitHub's guidance on
[repository topics](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/classifying-your-repository-with-topics)
and [README content](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes),
and Google's [indexing FAQ](https://developers.google.com/search/help/crawling-index-faq).
