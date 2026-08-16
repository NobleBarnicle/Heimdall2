from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path


ONTOLOGY_PATH = Path(__file__).resolve().parents[2] / "ONTOLOGY.md"


@lru_cache(maxsize=1)
def load_ontology() -> dict[str, object]:
    """Parse the canonical Markdown ontology instead of duplicating its values in code."""
    text = ONTOLOGY_PATH.read_text(encoding="utf-8")
    version_match = re.search(r"\*\*Version:\*\*\s*([^\s]+)", text)
    if not version_match:
        raise RuntimeError("ONTOLOGY.md must declare a version")

    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        heading = re.match(r"^## ([^\n]+)$", line)
        if heading:
            current = heading.group(1)
            sections.setdefault(current, [])
            continue
        if current and line.startswith("| ") and not line.startswith("| Value ") and not line.startswith("| ---"):
            value = line.split("|", 2)[1].strip()
            if value:
                sections[current].append(value)

    required = [
        "Research Track", "Bail Proceeding", "Bail Issue", "Bail Result", "Bail Factors",
        "Type", "Area", "Authority Weight", "Function", "Relationship", "Boundary", "Trigger",
    ]
    missing = [name for name in required if not sections.get(name)]
    if missing:
        raise RuntimeError(f"ONTOLOGY.md is missing controlled values for: {', '.join(missing)}")
    return {"version": version_match.group(1), "vocabularies": sections}


def validate_values(field: str, values: list[str]) -> None:
    ontology = load_ontology()
    allowed = set(ontology["vocabularies"][field])  # type: ignore[index]
    unknown = sorted(set(values) - allowed)
    if unknown:
        raise ValueError(f"Unknown {field} value(s): {', '.join(unknown)}")


def requires_commentary(values: list[str]) -> bool:
    return any(value.startswith("Other") for value in values)
