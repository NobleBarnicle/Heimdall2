from __future__ import annotations

import hashlib
import html
import re
import ssl
import xml.etree.ElementTree as ET
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen

import truststore
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import STATUTES_DIR
from .models import StatuteProvision, StatuteSnapshot

CRIMINAL_CODE_XML_URL = "https://laws-lois.justice.gc.ca/eng/XML/C-46.xml"
CRIMINAL_CODE_PAGE_URL = "https://laws-lois.justice.gc.ca/eng/acts/C-46/"
PIT_INDEX_URL = "https://laws-lois.justice.gc.ca/eng/acts/c-46/PITIndex.html"
PARSER_VERSION = "2.0.2"
STRUCTURAL_TAGS = {"section", "subsection", "paragraph", "subparagraph", "clause", "subclause"}
ARCHIVED_STRUCTURAL_CLASSES = {"section", "subsection", "paragraph", "subparagraph"}


def _system_ssl_context() -> ssl.SSLContext:
    return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)


def _local_name(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1].lower()


def _element_text(element: ET.Element) -> str:
    return re.sub(r"\s+", " ", " ".join(element.itertext())).strip()


def _child_text(element: ET.Element, names: set[str]) -> str | None:
    for child in element:
        if _local_name(child) in names:
            value = _element_text(child)
            if value:
                return value
    return None


def _descendant_text(element: ET.Element, names: set[str]) -> str | None:
    for child in element.iter():
        if child is not element and _local_name(child) in names:
            value = _element_text(child)
            if value:
                return value
    return None


def _attribute(element: ET.Element, name: str) -> str | None:
    for key, value in element.attrib.items():
        if key.rsplit("}", 1)[-1] == name:
            return value
    return None


def _label(element: ET.Element) -> str | None:
    label = _child_text(element, {"label", "sectionnumber", "number"})
    return re.sub(r"\s+", "", label) if label else None


def _direct_text(element: ET.Element) -> str:
    """Return only the words belonging to this node, excluding child provisions."""
    values = [_element_text(child) for child in element if _local_name(child) in {"text", "continueddefinition"}]
    return re.sub(r"\s+", " ", " ".join(value for value in values if value)).strip()


def _current_to_date() -> date | None:
    page = _download(CRIMINAL_CODE_PAGE_URL).decode("utf-8", errors="replace")
    match = re.search(r"Act current to\s+(\d{4}-\d{2}-\d{2})", page)
    return date.fromisoformat(match.group(1)) if match else None


def _download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "Heimdall local importer"})
    with urlopen(request, timeout=120, context=_system_ssl_context()) as response:
        return response.read()


def _download_xml() -> bytes:
    """Compatibility seam for the importer and its isolated tests."""
    return _download(CRIMINAL_CODE_XML_URL)


def _citation(parent: str | None, label: str, kind: str) -> str:
    if kind == "section":
        return f"s. {label}"
    normalized = label if label.startswith("(") else f"({label})"
    return f"{parent or 's.'}{normalized}"


def _node_key(parent_key: str | None, kind: str, label: str, position: int) -> str:
    token = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-") or str(position)
    return f"{parent_key}/{kind}:{token}" if parent_key else f"{kind}:{token}"


def _definition_key(parent_key: str, term: str | None, position: int) -> str:
    token = re.sub(r"[^a-z0-9]+", "-", (term or "definition").lower()).strip("-") or str(position)
    return f"{parent_key}/definition:{token}-{position}"


def parse_provisions(xml_bytes: bytes) -> list[dict[str, str | int | None]]:
    """Parse official XML into display-ready, citation-addressable nodes."""
    root = ET.fromstring(xml_bytes)
    provisions: list[dict[str, str | int | None]] = []

    def visit(element: ET.Element, parent_citation: str | None, parent_key: str | None) -> None:
        kind = _local_name(element)
        current_citation, current_key = parent_citation, parent_key
        if kind in STRUCTURAL_TAGS:
            label = _label(element)
            if label:
                current_citation = _citation(parent_citation, label, kind)
                current_key = _node_key(parent_key, kind, label, len(provisions) + 1)
                provisions.append({
                    "citation": current_citation, "node_key": current_key, "parent_key": parent_key,
                    "kind": kind, "heading": _child_text(element, {"heading", "titletext", "title"}),
                    "marginal_note": _child_text(element, {"marginalnote", "marginalnotetext"}),
                    "definition_term": None, "text": _direct_text(element),
                    "parent_citation": parent_citation, "ordinal": len(provisions) + 1,
                })
        elif kind == "definition" and parent_citation and parent_key:
            term = _descendant_text(element, {"definedtermen"})
            current_key = _definition_key(parent_key, term, len(provisions) + 1)
            provisions.append({
                "citation": parent_citation, "node_key": current_key, "parent_key": parent_key,
                "kind": "definition", "heading": None, "marginal_note": None,
                "definition_term": term, "text": _direct_text(element),
                "parent_citation": parent_citation, "ordinal": len(provisions) + 1,
            })
        for child in element:
            visit(child, current_citation, current_key)

    body = next((element for element in root if _local_name(element) == "body"), root)
    visit(body, None, None)
    if not provisions:
        raise ValueError("The official XML did not contain recognizable structural provisions")
    return provisions


class _ArchivedProvisionParser(HTMLParser):
    """Extract provision hierarchy from official archived HTML consolidations."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.active: dict[str, object] | None = None
        self.pending_marginal_note: str | None = None
        self.provisions: list[dict[str, str | int | None]] = []
        self.keys_by_level: dict[int, tuple[str, str]] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        classes = set(values.get("class", "").lower().split())
        if tag.lower() == "p" and "marginalnote" in classes:
            self.active = {"type": "marginal", "chunks": []}
        elif tag.lower() == "p" and classes.intersection(ARCHIVED_STRUCTURAL_CLASSES):
            kind = next(value for value in ARCHIVED_STRUCTURAL_CLASSES if value in classes)
            self.active = {"type": "provision", "kind": kind, "chunks": [], "label_chunks": [], "in_label": False}
        elif self.active and self.active.get("type") == "provision" and tag.lower() == "span" and classes.intersection({"sectionlabel", "lawlabel"}):
            self.active["in_label"] = True

    def handle_endtag(self, tag: str) -> None:
        if self.active and self.active.get("type") == "provision" and tag.lower() == "span":
            self.active["in_label"] = False
        if self.active and tag.lower() == "p":
            if self.active["type"] == "marginal":
                self.pending_marginal_note = re.sub(r"^Marginal note:\s*", "", self._clean("".join(self.active["chunks"])), flags=re.I)
            else:
                self._finish_provision()
            self.active = None

    def handle_data(self, data: str) -> None:
        if self.active:
            self.active["chunks"].append(data)
            if self.active.get("in_label"):
                self.active["label_chunks"].append(data)

    @staticmethod
    def _clean(value: str) -> str:
        return re.sub(r"\s+", " ", html.unescape(value)).strip()

    def _finish_provision(self) -> None:
        assert self.active
        label = self._clean("".join(self.active["label_chunks"]))
        if not label:
            return
        kind = str(self.active["kind"])
        level = {"section": 0, "subsection": 1, "paragraph": 2, "subparagraph": 3}[kind]
        self.keys_by_level = {key: value for key, value in self.keys_by_level.items() if key < level}
        parent_key, parent_citation = self.keys_by_level.get(level - 1, (None, None))
        citation = _citation(parent_citation, label, kind)
        node_key = _node_key(parent_key, kind, label, len(self.provisions) + 1)
        text = re.sub(rf"^{re.escape(label)}\s*", "", self._clean("".join(self.active["chunks"])))
        self.provisions.append({
            "citation": citation, "node_key": node_key, "parent_key": parent_key, "kind": kind,
            "heading": None, "marginal_note": self.pending_marginal_note, "definition_term": None,
            "text": text, "parent_citation": parent_citation, "ordinal": len(self.provisions) + 1,
        })
        self.keys_by_level[level] = (node_key, citation)
        self.pending_marginal_note = None


def parse_archived_provisions(html_bytes: bytes) -> list[dict[str, str | int | None]]:
    parser = _ArchivedProvisionParser()
    parser.feed(html_bytes.decode("utf-8", errors="replace"))
    if not parser.provisions:
        raise ValueError("The official archived page did not contain recognizable provisions")
    return parser.provisions


def _snapshot_from_source(session: Session, source: bytes, *, source_url: str, source_format: str, in_force_from: date | None, in_force_to: date | None) -> StatuteSnapshot:
    snapshot_id = __import__("uuid").uuid4().hex
    snapshot_directory = STATUTES_DIR / snapshot_id
    snapshot_directory.mkdir(parents=True, exist_ok=False)
    source_path = snapshot_directory / ("source.xml" if source_format == "XML" else "source.html")
    source_path.write_bytes(source)
    parsed = parse_provisions(source) if source_format == "XML" else parse_archived_provisions(source)
    snapshot = StatuteSnapshot(
        id=snapshot_id, short_title="Criminal Code", citation="R.S.C. 1985, c. C-46", jurisdiction="Canada", language="en",
        source_url=source_url, source_format=source_format, source_sha256=hashlib.sha256(source).hexdigest(),
        current_to_date=_current_to_date() if source_format == "XML" else in_force_to,
        in_force_from=in_force_from, in_force_to=in_force_to, parser_version=PARSER_VERSION,
        stored_path=str(source_path.relative_to(STATUTES_DIR.parent)),
    )
    session.add(snapshot)
    session.flush()
    for provision in parsed:
        session.add(StatuteProvision(snapshot_id=snapshot.id, **provision))
    session.commit()
    session.refresh(snapshot)
    return snapshot


def import_criminal_code(session: Session) -> StatuteSnapshot:
    xml_bytes = _download_xml()
    root = ET.fromstring(xml_bytes)
    pit_date = _attribute(root, "pit-date")
    return _snapshot_from_source(
        session, xml_bytes, source_url=CRIMINAL_CODE_XML_URL, source_format="XML",
        in_force_from=date.fromisoformat(pit_date) if pit_date else None, in_force_to=None,
    )


def _point_in_time_range(requested_date: date) -> tuple[date, date]:
    page = _download(PIT_INDEX_URL).decode("utf-8", errors="replace")
    for start, end in re.findall(r"From\s+(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})", page):
        valid_from, valid_to = date.fromisoformat(start), date.fromisoformat(end)
        if valid_from <= requested_date <= valid_to:
            return valid_from, valid_to
    raise ValueError("Justice Laws does not list a Criminal Code point-in-time version for that date")


def import_criminal_code_at(session: Session, requested_date: date) -> StatuteSnapshot:
    valid_from, valid_to = _point_in_time_range(requested_date)
    source_url = f"https://laws-lois.justice.gc.ca/eng/acts/c-46/{valid_from:%Y%m%d}/P1TT3xt3.html"
    return _snapshot_from_source(
        session, _download(source_url), source_url=source_url, source_format="HTML",
        in_force_from=valid_from, in_force_to=valid_to,
    )


def refresh_legacy_snapshot(session: Session, snapshot: StatuteSnapshot) -> None:
    if snapshot.parser_version == PARSER_VERSION:
        return
    source = STATUTES_DIR.parent / snapshot.stored_path
    if not source.exists():
        return
    raw = source.read_bytes()
    parsed = parse_provisions(raw) if snapshot.source_format == "XML" else parse_archived_provisions(raw)
    session.query(StatuteProvision).filter(StatuteProvision.snapshot_id == snapshot.id).delete()
    for provision in parsed:
        session.add(StatuteProvision(snapshot_id=snapshot.id, **provision))
    snapshot.parser_version = PARSER_VERSION
    session.commit()


def _subtree(session: Session, snapshot_id: str, node_key: str | None) -> dict[str, StatuteProvision]:
    if not node_key:
        return {}
    nodes = session.scalars(select(StatuteProvision).where(StatuteProvision.snapshot_id == snapshot_id)).all()
    return {node.node_key: node for node in nodes if node.node_key and (node.node_key == node_key or node.node_key.startswith(f"{node_key}/"))}


def compare_snapshots(session: Session, earlier: StatuteSnapshot, later: StatuteSnapshot, citation: str) -> dict[str, object]:
    normalized = citation if citation.startswith("s. ") else f"s. {citation.removeprefix('s.').strip()}"
    earlier_root = session.scalar(select(StatuteProvision).where(StatuteProvision.snapshot_id == earlier.id, StatuteProvision.citation == normalized, StatuteProvision.kind == "section"))
    later_root = session.scalar(select(StatuteProvision).where(StatuteProvision.snapshot_id == later.id, StatuteProvision.citation == normalized, StatuteProvision.kind == "section"))
    if not earlier_root and not later_root:
        raise ValueError("That section is not present in either selected snapshot")
    before_nodes, after_nodes = _subtree(session, earlier.id, earlier_root.node_key) if earlier_root else {}, _subtree(session, later.id, later_root.node_key) if later_root else {}
    entries = []
    for key in sorted(set(before_nodes) | set(after_nodes)):
        before, after = before_nodes.get(key), after_nodes.get(key)
        if before and after and before.text == after.text and before.marginal_note == after.marginal_note:
            continue
        node = after or before
        entries.append({
            "node_key": key, "citation": node.citation, "label": node.definition_term or node.marginal_note,
            "change": "added" if after and not before else "repealed" if before and not after else "amended",
            "earlier_text": before.text if before else None, "later_text": after.text if after else None,
        })
    return {"citation": normalized, "earlier_snapshot_id": earlier.id, "later_snapshot_id": later.id, "entries": entries}
