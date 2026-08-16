from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path


ONTOLOGY_PATH = Path(__file__).resolve().parents[2] / "ONTOLOGY.md"
VOCABULARY_FIELDS = (
    "Research Track", "Bail Proceeding", "Bail Issue", "Bail Result", "Bail Factors",
    "Type", "Area", "Authority Weight", "Function", "Relationship", "Boundary", "Trigger",
)


def _section_table_rows(markdown: str, section_name: str) -> list[list[str]]:
    """Read a simple Markdown table belonging to one named level-two heading."""
    match = re.search(rf"^## {re.escape(section_name)}\s*$([\s\S]*?)(?=^## |\Z)", markdown, flags=re.MULTILINE)
    if not match:
        return []
    rows: list[list[str]] = []
    lines = match.group(1).splitlines()
    for index, line in enumerate(lines):
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        following = lines[index + 1].strip() if index + 1 < len(lines) else ""
        if not cells or following.startswith("| ---") or all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        rows.append(cells)
    return rows


@lru_cache(maxsize=1)
def load_ontology() -> dict[str, object]:
    """Parse the canonical Markdown ontology instead of duplicating values in code."""
    markdown = ONTOLOGY_PATH.read_text(encoding="utf-8")
    version_match = re.search(r"\*\*Version:\*\*\s*([^\s]+)", markdown)
    if not version_match:
        raise RuntimeError("ONTOLOGY.md must declare a version")

    vocabularies: dict[str, list[str]] = {}
    vocabulary_definitions: dict[str, list[dict[str, str]]] = {}
    for field in VOCABULARY_FIELDS:
        rows = _section_table_rows(markdown, field)
        values = [row[0] for row in rows if len(row) >= 2 and row[0]]
        if len(values) != len(rows) or not values:
            raise RuntimeError(f"ONTOLOGY.md is missing controlled values for: {field}")
        vocabularies[field] = values
        vocabulary_definitions[field] = [{"value": row[0], "meaning": row[1]} for row in rows]

    annotation_field_rows = _section_table_rows(markdown, "Annotation Fields")
    if not annotation_field_rows or any(len(row) != 4 for row in annotation_field_rows):
        raise RuntimeError("ONTOLOGY.md must contain a complete Annotation Fields table")
    annotation_fields = [
        {"field": row[0], "required": row[1], "cardinality": row[2], "rule": row[3]}
        for row in annotation_field_rows
    ]

    version = version_match.group(1)
    version_notes = {row[0]: row[1] for row in _section_table_rows(markdown, "Version History") if len(row) >= 2}
    if version not in version_notes:
        raise RuntimeError(f"ONTOLOGY.md must include {version} in its Version History table")

    value_migrations = []
    for row in _section_table_rows(markdown, "Value Migrations"):
        if len(row) != 6:
            raise RuntimeError("Every Value Migrations row must have six columns")
        from_version, to_version, field, previous_value, replacement_value, reason = row
        if not all([from_version, to_version, field, previous_value, reason]):
            raise RuntimeError("Value Migrations requires versions, field, previous value, and reason")
        if field not in VOCABULARY_FIELDS:
            raise RuntimeError(f"Value Migrations uses unknown field: {field}")
        value_migrations.append(
            {
                "from_version": from_version,
                "to_version": to_version,
                "field": field,
                "previous_value": previous_value,
                "replacement_value": None if replacement_value in {"", "—", "-"} else replacement_value,
                "reason": reason,
            }
        )

    snapshot = {
        "version": version,
        "annotation_fields": annotation_fields,
        "vocabularies": vocabularies,
        "vocabulary_definitions": vocabulary_definitions,
    }
    fingerprint = hashlib.sha256(json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {
        **snapshot,
        "snapshot": snapshot,
        "fingerprint": fingerprint,
        "change_note": version_notes[version],
        "value_migrations": value_migrations,
    }


def validate_values(field: str, values: list[str]) -> None:
    ontology = load_ontology()
    allowed = set(ontology["vocabularies"][field])  # type: ignore[index]
    unknown = sorted(set(values) - allowed)
    if unknown:
        raise ValueError(f"Unknown {field} value(s): {', '.join(unknown)}")


def requires_commentary(values: list[str]) -> bool:
    return any(value.startswith("Other") for value in values)
