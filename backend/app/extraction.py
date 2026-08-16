from __future__ import annotations

import re
from statistics import median
from pathlib import Path

import pdfplumber


BRACKETED_PARAGRAPH_START = re.compile(r"^\s*\[(\d+)\]\s+(.+)$")
PLAIN_PARAGRAPH_START = re.compile(r"^\s*(\d+)[.)]\s+(.+)$")
BRACKETED_FIRST_PARAGRAPH = re.compile(r"(?m)^\s*\[1\]\s+")
PLAIN_FIRST_PARAGRAPH = re.compile(r"(?m)^\s*1[.)]\s+")
RUNNING_HEADER_PATTERNS = (
    re.compile(r"^.+?\s+Page\s+\d+\s*$", re.IGNORECASE),
    re.compile(r"^Page\s+\d+\s*$", re.IGNORECASE),
    re.compile(r"^-?\s*\d+\s*-?$"),
)
CANLII_FOOTER = re.compile(r"^\d{4}\s+[A-Z]{2,8}\s+\d+\s+\(CanLII\)\s*$", re.IGNORECASE)
SOLICITOR_LINE = re.compile(r"^Solicitors? for\s+", re.IGNORECASE)
JUDICIAL_SIGNATURE = re.compile(r"^[\"“]The Honourable .+[\"”]$")
DISPOSITION_LINE = re.compile(r"^Appeal (?:allowed|dismissed)\.?$", re.IGNORECASE)


def _is_running_matter(line: str) -> bool:
    return CANLII_FOOTER.fullmatch(line) is not None or any(pattern.fullmatch(line) for pattern in RUNNING_HEADER_PATTERNS)


def _looks_like_heading(line: str) -> bool:
    if line.lower().startswith("the following are the reasons for judgment"):
        return False
    if "[" in line or "]" in line:
        return False
    if len(line) > 100 or len(line.split()) > 12 or line.endswith((".", ",", ";", ":", "?", "!", "…")):
        return False
    return bool(line) and line[0].isupper()


def _is_heading(
    line: str,
    following_lines: list[str],
    paragraph_start: re.Pattern[str],
    expected_label: int,
) -> bool:
    """Recognize one or more short headings immediately before the next paragraph."""
    if not _looks_like_heading(line):
        return False
    for following in following_lines[:3]:
        paragraph_match = paragraph_start.match(following)
        if paragraph_match:
            return int(paragraph_match.group(1)) == expected_label
        if not _looks_like_heading(following):
            return False
    return False


def _join_lines(lines: list[str]) -> str:
    text = ""
    for line in lines:
        clean = line.strip()
        if not clean:
            continue
        if text.endswith("-"):
            text += clean
        else:
            text = f"{text} {clean}".strip()
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s*\((?:ORAL )?REASONS FOR JUDGMENT CONCLUDED\)\s*$", "", text, flags=re.IGNORECASE)


def _is_trailing_matter(line: str, next_line: str | None) -> bool:
    return bool(
        SOLICITOR_LINE.match(line)
        or JUDICIAL_SIGNATURE.match(line)
        or line == "I AGREE:"
        or (DISPOSITION_LINE.match(line) and next_line and SOLICITOR_LINE.match(next_line))
    )


def extract_paragraphs_from_pages(page_texts: list[str]) -> list[dict[str, object]]:
    """Extract numbered judgment paragraphs from already extracted PDF page text.

    Cover pages before paragraph 1 are excluded. Physical page numbering is translated
    to judgment-page numbering, and numbered paragraphs may span several pages.
    """
    first_judgment_page = next((index for index, text in enumerate(page_texts) if BRACKETED_FIRST_PARAGRAPH.search(text)), None)
    paragraph_start = BRACKETED_PARAGRAPH_START
    if first_judgment_page is None:
        first_judgment_page = next((index for index, text in enumerate(page_texts) if PLAIN_FIRST_PARAGRAPH.search(text)), None)
        paragraph_start = PLAIN_PARAGRAPH_START
    if first_judgment_page is None:
        return _extract_unnumbered_pages(page_texts)

    records: list[dict[str, object]] = []
    pending_lines: list[str] = []
    pending_label: str | None = None
    pending_page_start = 1
    pending_page_end = 1
    expected_label = 1

    def flush() -> None:
        nonlocal pending_lines, pending_label
        text = _join_lines(pending_lines)
        if pending_label and text:
            records.append(
                {
                    "label": pending_label,
                    "text": text,
                    "source_page_start": pending_page_start,
                    "source_page_end": pending_page_end,
                }
            )
        pending_lines = []
        pending_label = None

    extraction_complete = False
    for physical_index in range(first_judgment_page, len(page_texts)):
        judgment_page = physical_index - first_judgment_page + 1
        raw_lines = [line.strip() for line in page_texts[physical_index].splitlines() if line.strip()]
        lines = [line for line in raw_lines if not _is_running_matter(line)]
        for index, line in enumerate(lines):
            next_line = lines[index + 1] if index + 1 < len(lines) else None
            if pending_label and _is_trailing_matter(line, next_line):
                flush()
                extraction_complete = True
                break
            paragraph_match = paragraph_start.match(line)
            if paragraph_match and int(paragraph_match.group(1)) == expected_label:
                flush()
                pending_label = paragraph_match.group(1)
                expected_label += 1
                pending_page_start = judgment_page
                pending_page_end = judgment_page
                pending_lines = [paragraph_match.group(2)]
                continue
            if _is_heading(line, lines[index + 1 :], paragraph_start, expected_label):
                flush()
                records.append(
                    {
                        "label": "heading",
                        "text": line,
                        "source_page_start": judgment_page,
                        "source_page_end": judgment_page,
                    }
                )
                continue
            if pending_label:
                pending_lines.append(line)
                pending_page_end = judgment_page
        # Do not flush here: numbered paragraphs commonly continue on the next PDF page.
        if extraction_complete:
            break
    flush()
    return records


def _extract_unnumbered_pages(page_texts: list[str]) -> list[dict[str, object]]:
    """Fallback for text PDFs that do not use bracketed judgment paragraph numbers."""
    records: list[dict[str, object]] = []
    for page_number, raw_text in enumerate(page_texts, start=1):
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        text = _join_lines([line for line in lines if not _is_running_matter(line)])
        if text:
            records.append(
                {
                    "label": f"p. {page_number}",
                    "text": text,
                    "source_page_start": page_number,
                    "source_page_end": page_number,
                }
            )
    return records


def extract_paragraphs(pdf_path: Path) -> list[dict[str, object]]:
    """Extract judgment text while preserving judgment-page provenance."""
    with pdfplumber.open(pdf_path) as document:
        page_lines = [page.extract_text_lines() or [] for page in document.pages]

    # Court PDFs often set footnotes and running matter in distinctly smaller type.
    # Infer the judgment's body size from numbered-paragraph lines, then omit only
    # clearly smaller lines. This preserves indented quotations while preventing
    # footnotes from being merged into the nearest judgment paragraph.
    paragraph_font_sizes = [
        median(character["size"] for character in line["chars"])
        for lines in page_lines
        for line in lines
        if BRACKETED_PARAGRAPH_START.match(line["text"]) and line["chars"]
    ]
    body_font_size = median(paragraph_font_sizes) if paragraph_font_sizes else None
    minimum_font_size = body_font_size * 0.85 if body_font_size else None
    page_texts = [
        "\n".join(
            line["text"]
            for line in lines
            if not minimum_font_size
            or not line["chars"]
            or median(character["size"] for character in line["chars"]) >= minimum_font_size
        )
        for lines in page_lines
    ]
    return extract_paragraphs_from_pages(page_texts)
