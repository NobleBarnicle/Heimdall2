import { FormEvent, KeyboardEvent, useEffect, useMemo, useState } from "react";
import { Annotation, api, Document, Ontology, Paragraph, StatuteComparison, StatuteProvision, StatuteSectionPage, StatuteSnapshot } from "./api";

type Workspace = "library" | "code";
type AnnotationDraft = Omit<Annotation, "id" | "ontology_version" | "created_at" | "updated_at" | "decision_track"> & { decision_track: string };

const emptyDraft = (documentId = ""): AnnotationDraft => ({
  document_id: documentId, paragraph_ids: [], proposition: "", decision_track: "", bail_proceeding: null, bail_issue: null, bail_result: null, bail_factors: [], annotation_type: "Principle", areas: ["Bail"], authority_weight: "Routine", function: "", relationship_type: null, boundary: null, triggers: [], commentary: null, related_authorities: [],
});

function Options({ values }: { values: string[] }) {
  return <>{values.map((value) => <option value={value} key={value}>{value}</option>)}</>;
}

export default function App() {
  const [workspace, setWorkspace] = useState<Workspace>("library");
  const [ontology, setOntology] = useState<Ontology | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [selectedDocument, setSelectedDocument] = useState<Document | null>(null);
  const [readerMode, setReaderMode] = useState<"text" | "pdf">("text");
  const [paragraphs, setParagraphs] = useState<Paragraph[]>([]);
  const [selectedParagraphs, setSelectedParagraphs] = useState<string[]>([]);
  const [draft, setDraft] = useState<AnnotationDraft>(emptyDraft());
  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [search, setSearch] = useState("");
  const [snapshots, setSnapshots] = useState<StatuteSnapshot[]>([]);
  const [selectedSnapshot, setSelectedSnapshot] = useState<StatuteSnapshot | null>(null);
  const [provisions, setProvisions] = useState<StatuteProvision[]>([]);
  const [codeQuery, setCodeQuery] = useState("");
  const [sectionPage, setSectionPage] = useState<StatuteSectionPage | null>(null);
  const [sectionOffset, setSectionOffset] = useState(0);
  const [historicalDate, setHistoricalDate] = useState("");
  const [comparisonSnapshotId, setComparisonSnapshotId] = useState("");
  const [comparison, setComparison] = useState<StatuteComparison | null>(null);
  const [message, setMessage] = useState("Loading local workspace…");
  const [busy, setBusy] = useState(false);

  const vocab = ontology?.vocabularies ?? {};
  const selectedParagraphSet = useMemo(() => new Set(selectedParagraphs), [selectedParagraphs]);

  async function refreshDocuments() {
    const next = await api.documents();
    setDocuments(next);
    if (!selectedDocument && next[0]) setSelectedDocument(next[0]);
  }

  useEffect(() => {
    Promise.all([api.ontology(), api.documents(), api.annotations(), api.statutes()])
      .then(([nextOntology, nextDocuments, nextAnnotations, nextSnapshots]) => {
        setOntology(nextOntology); setDocuments(nextDocuments); setAnnotations(nextAnnotations); setSnapshots(nextSnapshots);
        if (nextDocuments[0]) setSelectedDocument(nextDocuments[0]);
        if (nextSnapshots[0]) setSelectedSnapshot(nextSnapshots[0]);
        setMessage("");
      })
      .catch((error: Error) => setMessage(error.message));
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      api.annotations(search).then(setAnnotations).catch((error: Error) => setMessage(error.message));
    }, 150);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    if (!selectedDocument) { setParagraphs([]); return; }
    api.paragraphs(selectedDocument.id).then((next) => {
      setParagraphs(next); setSelectedParagraphs([]); setDraft(emptyDraft(selectedDocument.id));
    }).catch((error: Error) => setMessage(error.message));
  }, [selectedDocument]);

  useEffect(() => {
    if (!selectedSnapshot) { setProvisions([]); setSectionPage(null); return; }
    if (codeQuery.trim()) {
      setSectionPage(null);
      api.provisions(selectedSnapshot.id, codeQuery).then(setProvisions).catch((error: Error) => setMessage(error.message));
      return;
    }
    setProvisions([]);
    api.sections(selectedSnapshot.id, sectionOffset).then(setSectionPage).catch((error: Error) => setMessage(error.message));
  }, [selectedSnapshot, codeQuery, sectionOffset]);

  useEffect(() => { setSectionOffset(0); }, [selectedSnapshot]);

  useEffect(() => {
    const normalized = codeQuery.trim().replace(/^s\.\s*/i, "");
    if (!selectedSnapshot || !comparisonSnapshotId || !/^\d[\da-z.()]*$/i.test(normalized)) { setComparison(null); return; }
    api.compareProvisions(comparisonSnapshotId, selectedSnapshot.id, `s. ${normalized}`)
      .then(setComparison).catch((error: Error) => setMessage(error.message));
  }, [selectedSnapshot, comparisonSnapshotId, codeQuery]);

  function toggleParagraph(id: string) {
    setSelectedParagraphs((current) => current.includes(id) ? current.filter((value) => value !== id) : [...current, id]);
  }

  function chooseDecisionTrack(decision_track: string) {
    setDraft((current) => ({
      ...current,
      decision_track,
      areas: decision_track === "Bail" ? ["Bail"] : current.areas,
      bail_proceeding: decision_track === "Bail" ? current.bail_proceeding : null,
      bail_issue: decision_track === "Bail" ? current.bail_issue : null,
      bail_result: decision_track === "Bail" ? current.bail_result : null,
      bail_factors: decision_track === "Bail" ? current.bail_factors : [],
    }));
  }

  async function uploadDocument(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setBusy(true); setMessage("Importing and extracting text…");
    try {
      const document = await api.importDocument(form);
      await refreshDocuments(); setSelectedDocument(document); formElement.reset(); setMessage("Judgment imported locally.");
    } catch (error) { setMessage((error as Error).message); }
    finally { setBusy(false); }
  }

  async function saveAnnotation() {
    if (!selectedDocument) return;
    if (!draft.decision_track || !draft.function || (draft.decision_track === "Bail" && (!draft.bail_proceeding || !draft.bail_issue || !draft.bail_result))) {
      setMessage("Choose the passage function and, for Bail, the proceeding, point of law, and result.");
      return;
    }
    setBusy(true); setMessage("Saving human annotation…");
    try {
      const saved = await api.createAnnotation({ ...draft, document_id: selectedDocument.id, paragraph_ids: selectedParagraphs });
      setAnnotations((current) => [saved, ...current]); setDraft(emptyDraft(selectedDocument.id)); setSelectedParagraphs([]); setMessage("Annotation saved with paragraph provenance.");
    } catch (error) { setMessage((error as Error).message); }
    finally { setBusy(false); }
  }

  async function reextractSelectedDocument() {
    if (!selectedDocument) return;
    setBusy(true); setMessage("Re-extracting judgment structure…");
    try {
      const nextParagraphs = await api.reextractParagraphs(selectedDocument.id);
      setParagraphs(nextParagraphs); setSelectedParagraphs([]); setMessage("Extracted text refreshed from the original PDF.");
    } catch (error) { setMessage((error as Error).message); }
    finally { setBusy(false); }
  }

  async function createBackup() {
    setBusy(true); setMessage("Creating a consistent local database backup…");
    try {
      const backup = await api.createBackup();
      setMessage(`Local backup created: ${backup.filename}`);
    } catch (error) { setMessage((error as Error).message); }
    finally { setBusy(false); }
  }

  function annotationKeys(event: KeyboardEvent<HTMLTextAreaElement>) {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") { event.preventDefault(); void saveAnnotation(); }
  }

  async function importCriminalCode() {
    setBusy(true); setMessage("Downloading the official English XML and creating a local snapshot…");
    try {
      const snapshot = await api.importCode();
      setSnapshots((current) => [snapshot, ...current]); setSelectedSnapshot(snapshot); setMessage("Criminal Code snapshot imported.");
    } catch (error) { setMessage((error as Error).message); }
    finally { setBusy(false); }
  }

  async function importHistoricalCriminalCode() {
    if (!historicalDate) return;
    setBusy(true); setMessage("Retrieving the official point-in-time consolidation and storing it locally…");
    try {
      const snapshot = await api.importCodeAt(historicalDate);
      setSnapshots((current) => [snapshot, ...current]); setSelectedSnapshot(snapshot); setHistoricalDate("");
      setMessage("Historical Criminal Code snapshot imported.");
    } catch (error) { setMessage((error as Error).message); }
    finally { setBusy(false); }
  }

  return <main className="app-shell">
    <aside className="sidebar">
      <div className="brand">
<span className="brand-mark">H</span>
<div>
<strong>Heimdall</strong>
<small>Legal knowledge engine</small>
</div>
</div>
      <nav>
        <button className={workspace === "library" ? "active" : ""} onClick={() => setWorkspace("library")}>Judgments & annotations</button>
        <button className={workspace === "code" ? "active" : ""} onClick={() => setWorkspace("code")}>Criminal Code</button>
      </nav>
      <div className="side-note">
<span>Ontology</span>
<strong>v{ontology?.version ?? "…"}</strong>
<p>Human analysis is canonical.</p>
</div>
    </aside>

    <section className="content">
      <header>
<div>
<p className="eyebrow">PHASE 1 · LOCAL ONLY</p>
<h1>{workspace === "library" ? "Judgment workspace" : "Criminal Code"}</h1>
</div>
<p className={message ? "status" : "status empty"}>{message}</p>
</header>
      {workspace === "library" ? <>
        <section className="import-card">
          <h2>Import a judgment</h2>
          <form onSubmit={uploadDocument} className="import-form">
            <input name="file" type="file" accept="application/pdf" required />
            <input name="title" placeholder="Case name" required />
            <input name="neutral_citation" placeholder="Neutral citation (optional)" />
            <input name="court" placeholder="Court (optional)" />
            <button disabled={busy}>Import PDF</button>
          </form>
        </section>
        <section className="workspace-grid">
          <aside className="document-list">
<div className="panel-heading">
<h2>Authorities</h2>
<span>{documents.length}</span>
</div>{documents.length === 0 ? <p className="muted">Import a judgment to begin.</p> : documents.map((document) => <button key={document.id} className={selectedDocument?.id === document.id ? "document active" : "document"} onClick={() => setSelectedDocument(document)}>
<strong>{document.title}</strong>
<small>{document.neutral_citation || document.source_filename}</small>
</button>)}</aside>
          <section className="reader-panel">
            {selectedDocument ? <>
<div className="panel-heading">
<div>
<h2>{selectedDocument.title}</h2>
<span>{selectedDocument.neutral_citation || selectedDocument.source_filename}</span>
</div>
<div className="reader-actions">
<button className={readerMode === "text" ? "active" : ""} onClick={() => setReaderMode("text")}>Extracted text</button>
<button className={readerMode === "pdf" ? "active" : ""} onClick={() => setReaderMode("pdf")}>PDF</button>
<button disabled={busy} onClick={() => void reextractSelectedDocument()}>Re-extract</button>
<a href={`/api/documents/${selectedDocument.id}/file`} target="_blank">Open ↗</a>
</div>
</div>{readerMode === "pdf" ? <iframe className="pdf-viewer" title={`${selectedDocument.title} PDF`} src={`/api/documents/${selectedDocument.id}/file`} /> : <div className="paragraph-list">{paragraphs.map((paragraph) => paragraph.label === "heading" ? <h3 className="extracted-heading" key={paragraph.id}>{paragraph.text}</h3> : <article key={paragraph.id} className={selectedParagraphSet.has(paragraph.id) ? "paragraph selected" : "paragraph"} onClick={() => toggleParagraph(paragraph.id)}>
<span>¶ {paragraph.label} · judgment p. {paragraph.source_page_start}{paragraph.source_page_end !== paragraph.source_page_start ? `–${paragraph.source_page_end}` : ""}</span>
<p>{paragraph.text}</p>
</article>)}</div>}</> : <Empty text="Select or import a judgment." />}
          </section>
          <aside className="annotation-panel">
<div className="panel-heading">
<h2>Annotation</h2>
<span>{selectedParagraphs.length} ¶</span>
</div>{selectedDocument && ontology ? <>
<fieldset className="decision-track">
<legend>Where does this proposition belong?</legend>
<div>{(vocab["Research Track"] ?? []).map((track) => <button type="button" key={track} className={draft.decision_track === track ? "active" : ""} onClick={() => chooseDecisionTrack(track)}>{track === "Charter and Procedure" ? "Charter / procedure" : track}</button>)}</div>
</fieldset>
{draft.decision_track === "Bail" && <>
<section className="bail-case-context">
<p>Case context</p>
<Select label="Proceeding" value={draft.bail_proceeding || ""} values={["", ...(vocab["Bail Proceeding"] ?? [])]} onChange={(bail_proceeding) => setDraft({ ...draft, bail_proceeding: bail_proceeding || null })} />
<Select label="Result" value={draft.bail_result || ""} values={["", ...(vocab["Bail Result"] ?? [])]} onChange={(bail_result) => setDraft({ ...draft, bail_result: bail_result || null })} />
</section>
<section className="proposition-card">
<div><strong>Proposition</strong><span>Classify the highlighted passage itself.</span></div>
<Select label="Point of bail law" value={draft.bail_issue || ""} values={["", ...(vocab["Bail Issue"] ?? [])]} onChange={(bail_issue) => setDraft({ ...draft, bail_issue: bail_issue || null })} />
<Select label="What does this passage do?" value={draft.function} values={["", ...(vocab.Function ?? [])]} onChange={(functionValue) => setDraft({ ...draft, function: functionValue })} />
<FactorPicker values={vocab["Bail Factors"] ?? []} selected={draft.bail_factors} onChange={(bail_factors) => setDraft({ ...draft, bail_factors })} />
<label>Proposition<textarea value={draft.proposition} onKeyDown={annotationKeys} onChange={(event) => setDraft({ ...draft, proposition: event.target.value })} placeholder="State the legal proposition in your own words." />
</label>
</section>
</>}
{draft.decision_track && draft.decision_track !== "Bail" && <label>Proposition<textarea value={draft.proposition} onKeyDown={annotationKeys} onChange={(event) => setDraft({ ...draft, proposition: event.target.value })} placeholder="State the legal proposition in your own words." />
</label>}
<details className="annotation-more">
<summary>Additional legal context <span>optional</span></summary>
<div className="field-grid">
<Select label="Type" value={draft.annotation_type} values={vocab.Type} onChange={(annotation_type) => setDraft({ ...draft, annotation_type })} />
<Select label="Authority" value={draft.authority_weight} values={vocab["Authority Weight"]} onChange={(authority_weight) => setDraft({ ...draft, authority_weight })} />
<Select label="Area" value={draft.areas[0]} values={vocab.Area} onChange={(area) => setDraft({ ...draft, areas: [area] })} />
{draft.decision_track !== "Bail" && <Select label="Function" value={draft.function} values={["", ...(vocab.Function ?? [])]} onChange={(functionValue) => setDraft({ ...draft, function: functionValue })} />}
<Select label="Boundary" value={draft.boundary || ""} values={["", ...(vocab.Boundary ?? [])]} onChange={(boundary) => setDraft({ ...draft, boundary: boundary || null })} />
<Select label="Trigger" value={draft.triggers[0] || ""} values={["", ...(vocab.Trigger ?? [])]} onChange={(trigger) => setDraft({ ...draft, triggers: trigger ? [trigger] : [] })} />
</div>
<label>Commentary <textarea value={draft.commentary ?? ""} onChange={(event) => setDraft({ ...draft, commentary: event.target.value || null })} placeholder="Optional context, limitation, or why this matters." />
</label>
</details>
<button className="primary" disabled={busy || !draft.decision_track || !draft.function || !draft.proposition || selectedParagraphs.length === 0 || (draft.decision_track === "Bail" && (!draft.bail_proceeding || !draft.bail_issue || !draft.bail_result))} onClick={() => void saveAnnotation()}>Save annotation <kbd>⌘↵</kbd>
</button>
</> : <Empty text="Select a judgment to annotate." />}</aside>
        </section>
        <section className="annotation-search">
<div className="panel-heading">
<h2>Saved propositions</h2>
<div className="annotation-actions"><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search annotations and source text" />
<button disabled={busy} onClick={() => void createBackup()}>Back up</button>
<a href="/api/exports/annotations">Export</a></div>
</div>{annotations.slice(0, 12).map((annotation) => <article key={annotation.id}>
<p>{annotation.proposition}</p>
<small>{annotation.decision_track || "Legacy annotation"}{annotation.bail_issue ? ` · ${annotation.bail_issue}` : ""} · {annotation.annotation_type} · {annotation.authority_weight}</small>{annotation.bail_factors.length > 0 && <small>{annotation.bail_factors.join(" · ")}</small>}
</article>)}</section>
      </> : <section className="code-layout">
<div className="code-toolbar">
<div>
<h2>Official English consolidation</h2>
<p>Immutable local official snapshots, with point-in-time comparison.</p>
</div>
<button className="primary" disabled={busy} onClick={() => void importCriminalCode()}>Import latest Criminal Code</button>
</div>
<form className="historical-import" onSubmit={(event) => { event.preventDefault(); void importHistoricalCriminalCode(); }}>
<label>In-force date <input type="date" value={historicalDate} onChange={(event) => setHistoricalDate(event.target.value)} required />
</label>
<button disabled={busy}>Import historical version</button>
<small>Uses the official Justice Laws consolidation that was in force on that date.</small>
</form>
<div className="snapshot-row">{snapshots.length === 0 ? <Empty text="No local snapshot yet. Import the official Criminal Code to make it searchable offline." /> : snapshots.map((snapshot) => <button className={selectedSnapshot?.id === snapshot.id ? "snapshot active" : "snapshot"} key={snapshot.id} onClick={() => { setSelectedSnapshot(snapshot); setComparison(null); }}>
<strong>{snapshot.short_title}</strong>
<span>{snapshot.citation}</span>
<small>{snapshot.in_force_from ? `In force ${snapshot.in_force_from}${snapshot.in_force_to ? ` – ${snapshot.in_force_to}` : ""}` : `Current to ${snapshot.current_to_date || "not supplied"}`}</small>
</button>)}</div>{selectedSnapshot && <>
<div className="code-search">
<input value={codeQuery} onChange={(event) => setCodeQuery(event.target.value)} placeholder="Open s. 515, a phrase, or a definition" />
<span>{codeQuery.trim() ? `${provisions.length} nodes shown` : `${sectionPage?.total ?? "…"} sections`}</span>
</div>{/^\s*s?\.?\s*\d/.test(codeQuery) && snapshots.length > 1 && <label className="comparison-picker">Compare this section with <select value={comparisonSnapshotId} onChange={(event) => setComparisonSnapshotId(event.target.value)}>
<option value="">Choose local version…</option>{snapshots.filter((snapshot) => snapshot.id !== selectedSnapshot.id).map((snapshot) => <option key={snapshot.id} value={snapshot.id}>{snapshot.in_force_from || snapshot.current_to_date || "Unknown date"}</option>)}</select>
</label>}{codeQuery.trim() ? <ProvisionTree provisions={provisions} /> : <SectionBrowser page={sectionPage} onOpen={(citation) => setCodeQuery(citation)} onPage={(offset) => setSectionOffset(offset)} />}
<ComparisonPanel comparison={comparison} />
</>}</section>}
    </section>
  </main>;
}

function Select({ label, value, values = [], onChange }: { label: string; value: string; values?: string[]; onChange: (value: string) => void }) {
  return <label>{label}<select value={value} onChange={(event) => onChange(event.target.value)}>
<Options values={values} />
</select>
</label>;
}

function FactorPicker({ values, selected, onChange }: { values: string[]; selected: string[]; onChange: (values: string[]) => void }) {
  return <details className="bail-factors"><summary>Add bail factors <span>{selected.length ? `${selected.length} selected` : "optional"}</span></summary><div>{values.map((factor) => <button type="button" key={factor} className={selected.includes(factor) ? "active" : ""} aria-pressed={selected.includes(factor)} onClick={() => onChange(selected.includes(factor) ? selected.filter((value) => value !== factor) : [...selected, factor])}>{factor}</button>)}</div></details>;
}

function Empty({ text }: { text: string }) { return <p className="muted empty-state">{text}</p>; }

function SectionBrowser({ page, onOpen, onPage }: { page: StatuteSectionPage | null; onOpen: (citation: string) => void; onPage: (offset: number) => void }) {
  if (!page) return <Empty text="Loading the section browser…" />;
  const first = page.total === 0 ? 0 : page.offset + 1;
  const last = Math.min(page.offset + page.items.length, page.total);
  return <section className="section-browser"><div className="panel-heading"><div><h2>Sections</h2><small>Choose a section to open its complete readable hierarchy.</small></div><span>{first}–{last} of {page.total}</span></div><div className="section-list">{page.items.map((section) => <button key={section.id} onClick={() => onOpen(section.citation)}><strong>{section.citation}</strong><span>{section.marginal_note || section.heading || "Untitled provision"}</span></button>)}</div><nav className="section-pagination" aria-label="Section pages"><button disabled={page.offset === 0} onClick={() => onPage(Math.max(0, page.offset - page.limit))}>Previous sections</button><span>Sections {first}–{last}</span><button disabled={page.offset + page.limit >= page.total} onClick={() => onPage(page.offset + page.limit)}>Next sections</button></nav></section>;
}

type ProvisionNode = StatuteProvision & { children: ProvisionNode[] };

function ProvisionTree({ provisions }: { provisions: StatuteProvision[] }) {
  const roots = useMemo(() => {
    const nodes = new Map<string, ProvisionNode>();
    provisions.forEach((provision) => nodes.set(provision.node_key || provision.id, { ...provision, children: [] }));
    const nextRoots: ProvisionNode[] = [];
    nodes.forEach((node) => {
      const parent = node.parent_key ? nodes.get(node.parent_key) : undefined;
      if (parent) parent.children.push(node); else nextRoots.push(node);
    });
    return nextRoots;
  }, [provisions]);
  if (!provisions.length) return <Empty text="Search a citation, phrase, or definition to open a readable provision." />;
  return <div className="provision-tree">{roots.map((node) => <ProvisionTreeNode key={node.id} node={node} />)}</div>;
}

function ProvisionTreeNode({ node }: { node: ProvisionNode }) {
  const title = node.definition_term || node.marginal_note || node.heading;
  const anchor = node.node_key || node.id;
  if (node.kind === "definition") return <details className="definition-node" id={anchor}>
<summary>
<span>{node.definition_term || "Definition"}</span>
<a href={`#${anchor}`} aria-label={`Link to ${node.definition_term || "definition"}`}>#</a>
</summary>
<p>{node.text}</p>{node.children.map((child) => <ProvisionTreeNode key={child.id} node={child} />)}</details>;
  return <article className={`provision-node ${node.kind}`} id={anchor}>
<header>
<a href={`#${anchor}`} className="citation-link">{node.citation}</a>{title && <h3>{title}</h3>}<a href={`#${anchor}`} className="anchor-link" aria-label={`Link to ${node.citation}`}>#</a>
</header>{node.text && <p>{node.text}</p>}{node.children.length > 0 && <div className={node.citation === "s. 2" ? "definition-list" : "provision-children"}>{node.children.map((child) => <ProvisionTreeNode key={child.id} node={child} />)}</div>}</article>;
}

function ComparisonPanel({ comparison }: { comparison: StatuteComparison | null }) {
  if (!comparison) return null;
  return <section className="comparison-panel">
<div className="panel-heading">
<h2>Version changes in {comparison.citation}</h2>
<span>{comparison.entries.length} changes</span>
</div>{comparison.entries.length === 0 ? <p className="muted">No textual differences found in this local comparison.</p> : comparison.entries.map((entry) => <article key={entry.node_key} className={`change-${entry.change}`}>
<small>{entry.change.toUpperCase()} · {entry.label || entry.citation}</small>
<div>
<p>{entry.earlier_text || "— not present —"}</p>
<p>{entry.later_text || "— no longer present —"}</p>
</div>
</article>)}</section>;
}
