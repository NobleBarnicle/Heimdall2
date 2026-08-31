export type Ontology = { version: string; vocabularies: Record<string, string[]> };
export type Document = { id: string; title: string; neutral_citation: string | null; court: string | null; decision_date: string | null; source_filename: string; extraction_status: string; bail_proceeding: string | null; bail_result: string | null; bail_grounds: string[]; bail_case_material: string[]; bail_case_note: string | null; created_at: string };
export type Paragraph = { id: string; ordinal: number; label: string; text: string; source_page_start: number; source_page_end: number };
export type Annotation = { id: string; document_id: string; paragraph_ids: string[]; proposition: string; decision_track: string | null; bail_proceeding: string | null; bail_issue: string | null; bail_result: string | null; annotation_type: string; areas: string[]; authority_weight: string; function: string; relationship_type: string | null; boundary: string | null; triggers: string[]; commentary: string | null; related_authorities: string[]; ontology_version: string; created_at: string; updated_at: string };
export type Backup = { filename: string; bytes: number; created_at: string };
export type StatuteSnapshot = { id: string; short_title: string; citation: string; jurisdiction: string; language: string; source_url: string; current_to_date: string | null; in_force_from: string | null; in_force_to: string | null; downloaded_at: string; parser_version: string };
export type StatuteProvision = { id: string; citation: string; node_key: string | null; parent_key: string | null; kind: string; heading: string | null; marginal_note: string | null; definition_term: string | null; text: string; parent_citation: string | null; ordinal: number };
export type StatuteComparison = { citation: string; earlier_snapshot_id: string; later_snapshot_id: string; entries: { node_key: string; citation: string; label: string | null; change: string; earlier_text: string | null; later_text: string | null }[] };
export type StatuteSectionPage = { items: StatuteProvision[]; total: number; offset: number; limit: number };

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail ?? response.statusText);
  }
  return response.json() as Promise<T>;
}

export const api = {
  ontology: () => request<Ontology>("/ontology"),
  documents: () => request<Document[]>("/documents"),
  paragraphs: (documentId: string) => request<Paragraph[]>(`/documents/${documentId}/paragraphs`),
  reextractParagraphs: (documentId: string) => request<Paragraph[]>(`/documents/${documentId}/paragraphs/reextract`, { method: "POST" }),
  updateDocumentCaseContext: (documentId: string, context: { bail_proceeding: string; bail_result: string; bail_grounds: string[]; bail_case_material: string[]; bail_case_note: string | null }) => request<Document>(`/documents/${documentId}/case-context`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(context) }),
  annotations: (filters: { q?: string; bail_ground?: string; bail_case_material?: string } = {}) => {
    const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value) as [string, string][]);
    return request<Annotation[]>(`/annotations${query.size ? `?${query}` : ""}`);
  },
  statutes: () => request<StatuteSnapshot[]>("/statutes"),
  provisions: (snapshotId: string, query = "") => request<StatuteProvision[]>(`/statutes/${snapshotId}/provisions${query ? `?q=${encodeURIComponent(query)}` : ""}`),
  sections: (snapshotId: string, offset = 0, limit = 25) => request<StatuteSectionPage>(`/statutes/${snapshotId}/sections?offset=${offset}&limit=${limit}`),
  importCode: () => request<StatuteSnapshot>("/statutes/criminal-code/import", { method: "POST" }),
  importCodeAt: (inForceDate: string) => request<StatuteSnapshot>(`/statutes/criminal-code/import-at?in_force_date=${encodeURIComponent(inForceDate)}`, { method: "POST" }),
  compareProvisions: (snapshotId: string, otherSnapshotId: string, citation: string) => request<StatuteComparison>(`/statutes/${snapshotId}/compare/${otherSnapshotId}?citation=${encodeURIComponent(citation)}`),
  importDocument: (form: FormData) => request<Document>("/documents", { method: "POST", body: form }),
  createAnnotation: (annotation: Omit<Annotation, "id" | "ontology_version" | "created_at" | "updated_at">) => request<Annotation>("/annotations", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(annotation) }),
  createBackup: () => request<Backup>("/backups", { method: "POST" }),
};
