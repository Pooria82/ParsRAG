"""Prompt rules shared by every answer strategy.

Keeping language, formatting, and citation rules in one place means the three
modes cannot drift apart, and every mode emits math the frontend can render.
LlamaIndex leaves unknown ``{...}`` placeholders untouched, so LaTeX braces
are written literally.
"""

LANGUAGE_RULES = """\
LANGUAGE RULES:
1. Answer in the natural language of the user's question: Persian (فارسی) questions get a Persian answer, English questions an English answer.
2. Code, commands, function names, and technical terms are usually English. Do not treat them as a sign that the question is in English; decide from the surrounding sentences.
3. Never answer in Chinese or any other unintended language."""

FORMATTING_RULES = """\
FORMATTING RULES:
1. Use Markdown for structure (short paragraphs, lists, tables when they help).
2. Write every mathematical expression in LaTeX inside math delimiters: $...$ inline and $$...$$ on its own line for display. Never leave LaTeX commands such as \\sin or \\frac outside delimiters, and always close every delimiter you open.
3. Keep Persian words outside math delimiters. Inside math use only symbols, numbers, Latin variables, and \\text{...} for short labels."""

CITATION_RULES = """\
CITATION RULES:
- When a source label includes a page, slide, paragraph, or section, append that exact label at the end of the paragraph it supports. Never invent a location.
- A page-boundary excerpt joins the end of one page to the start of the next. Read both labeled parts together and cite the page range when both support the answer.
- If the user asks about a specific document, focus on that document and name it when relevant."""

CODE_VERIFICATION_RULES = """\
CODE AND CONCEPT CHECKS:
If the user asks whether a code snippet, function, command, library, or concept appears in the documents, compare it by meaning and structure, ignoring formatting differences (whitespace, parentheses, omitted declarations, reworded comments). If it is present, confirm it ("بله، این اطلاعات/کد در سند وجود دارد" or "Yes, this information/code is present in the document") and quote the relevant part with its location."""
