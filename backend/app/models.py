from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ConfigUpdateRequest(BaseModel):
    gemini_api_key: str | None = None
    gemini_model: str | None = None
    author_name: str | None = None
    institution: str | None = None
    career: str | None = None


class RubricCriterionDraft(BaseModel):
    id: str | None = None
    criterion: str
    indicator: str
    points: float | None = None
    requires_evidence: bool = False
    evidence_description: str | None = None
    deliverable: str | None = None


class CriteriaUpdateRequest(BaseModel):
    criteria: list[RubricCriterionDraft] = Field(default_factory=list)



class OutlineCard(BaseModel):
    id: str
    title: str
    description: str
    type: Literal["intro", "development", "conclusion", "references"] = "development"
    needs_code: bool = False
    needs_evidence: bool = False
    criterion_indexes: list[int] = Field(default_factory=list)


class RubricAnalysis(BaseModel):
    title: str
    subject: str
    summary: str
    deliverables: list[str] = Field(default_factory=list)
    key_requirements: list[str] = Field(default_factory=list)
    criteria: list[RubricCriterionDraft] = Field(default_factory=list)
    outline: list[OutlineCard] = Field(default_factory=list)


class GenerateRequest(BaseModel):
    project_id: str | None = None
    title: str
    subject: str
    student: str = "Autor"
    career: str = ""
    outline: list[OutlineCard]
    pauta_text: str = ""
    mode: Literal["sectional", "single"] = "sectional"


class RefineRequest(BaseModel):
    project_id: str | None = None
    selected_text: str
    instruction: str
    subject: str = "General"


class DocumentSaveRequest(BaseModel):
    html_content: str


class OutlineUpdateRequest(BaseModel):
    outline: list[OutlineCard]


class SnapshotRequest(BaseModel):
    html_content: str
    reason: str = "manual"


class RestoreVersionRequest(BaseModel):
    current_html_content: str | None = None


class QuickCreateRequest(BaseModel):
    title: str
    subject: str = "General"
    student: str = "Autor"
    career: str = ""
    summary: str = ""
    pauta_text: str = ""
    deliverables: list[str] = Field(default_factory=list)
    criteria: list[RubricCriterionDraft] = Field(default_factory=list)
    initial_sections: list[OutlineCard] = Field(default_factory=list)


class SectionUpdateRequest(BaseModel):
    heading: str = Field(min_length=1)
    content_html: str
    create_snapshot: bool = True
    reason: str = "section_update"


class RegenerateSectionRequest(BaseModel):
    heading: str = Field(min_length=1)
    instruction: str | None = None
    current_html_content: str | None = None


class PackageSubmissionRequest(BaseModel):
    html_content: str | None = None
    include_sources: bool = True



class MemoryWriteRequest(BaseModel):
    content: str = Field(min_length=3, max_length=5000)
    kind: Literal["preference", "fact", "decision", "summary"] = "fact"
    importance: float = Field(default=0.6, ge=0, le=1)


class LibraryAttachRequest(BaseModel):
    path: str


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    document_excerpt: str = Field(default="", max_length=20000)


class AgentAction(BaseModel):
    tool: Literal["replace_selection", "append_section", "add_evidence_placeholder", "none"] = "none"
    title: str = ""
    content: str = ""


class ChatResult(BaseModel):
    answer: str
    suggested_actions: list[AgentAction] = Field(default_factory=list)
    memories_to_store: list[str] = Field(default_factory=list)


class AuditItem(BaseModel):
    criterion_id: str
    status: Literal["complete", "partial", "missing"] = "complete"
    evidence_found: bool = False
    feedback: str = ""


class AuditResult(BaseModel):
    summary: str = "Revisión de contenido"
    estimated_score: float = Field(default=100.0, ge=0, le=100)
    items: list[AuditItem] = Field(default_factory=list)


class AuditRequest(BaseModel):
    html_content: str
    use_ai: bool = True


class AgentExecutionRequest(BaseModel):
    agent: str = Field(min_length=1, max_length=100)
    action: str = Field(min_length=1, max_length=500)
    status: Literal["succeeded", "failed", "partial"]
    criterion_id: str | None = None
    command: str = Field(default="", max_length=10000)
    exit_code: int | None = None
    stdout_excerpt: str = Field(default="", max_length=20000)
    stderr_excerpt: str = Field(default="", max_length=20000)
    artifact_ids: list[str] = Field(default_factory=list, max_length=100)


class DocSection(BaseModel):
    type: str
    content: str = ""
    content_html: str | None = None
    image_path: str | None = None
    image_alt: str | None = None
    table_rows: list[list[str]] | None = None


class ExportDocxRequest(BaseModel):
    project_id: str | None = None
    title: str
    subject: str = "General"
    student: str = "Autor"
    date: str | None = None
    career: str = ""
    institution: str = ""
    sections: list[DocSection] | None = None
    html_content: str | None = None
