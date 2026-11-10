"""Turn the campaign .docx into chunks ready to embed.

A chunk is plain text whose first line is the section it came from ("Chapter 6: Arrival in
Ksenrae"), so both the embedding and the model reading it know where it sits in the story.
"""

import zipfile
from pathlib import Path
from xml.etree import ElementTree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
# This document's own paragraph styles: chapter-level and sub-section headings.
HEADING, SUBHEADING = "SamKop", "Samkop2"
TOC_PREFIX = "Inhopg"  # table-of-contents entries repeat every heading; skip them
CHUNK_WORDS = 300


def paragraphs(path: str | Path) -> list[tuple[str, str]]:
    """(style, text) for every non-empty paragraph, in document order."""
    with zipfile.ZipFile(path) as docx:
        root = ElementTree.fromstring(docx.read("word/document.xml"))
    result = []
    for paragraph in root.iter(f"{W}p"):
        style = paragraph.find(f"{W}pPr/{W}pStyle")
        text = "".join(node.text or "" for node in paragraph.iter(f"{W}t")).strip()
        if text:
            result.append((style.get(f"{W}val", "") if style is not None else "", text))
    return result


def chunks(path: str | Path, max_words: int = CHUNK_WORDS) -> list[str]:
    """Pack each section's paragraphs into chunks of about `max_words`, never across sections.

    Paragraphs are kept whole, so a chunk can run over when one paragraph is long.
    """
    result: list[str] = []
    title, chapter, body, words = "", "", [], 0

    def flush() -> None:
        nonlocal body, words
        if body:
            result.append("\n".join([title, *body]))
        body, words = [], 0

    for style, text in paragraphs(path):
        if style.startswith(TOC_PREFIX):
            continue
        if style in (HEADING, SUBHEADING):
            flush()
            if style == HEADING:
                chapter = text
            title = text if style == HEADING else f"{chapter} > {text}"
            continue
        if not title:  # title page, before the first heading
            continue
        count = len(text.split())
        if body and words + count > max_words:
            flush()
        body.append(text)
        words += count
    flush()
    return result
