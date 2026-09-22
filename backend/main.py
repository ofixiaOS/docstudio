from __future__ import annotations

import html
import mimetypes
import os
import re
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from app.ai import ai
from app.audit_service import (
    audit_score,
    enforce_evidence_grounding,
    offline_audit,
    valid_evidence_by_criterion,
)
from app.documents import classify_document, extract_text, list_library_files
from app.evidence import apply_watermark
from app.html_utils import (
    clean_model_output,
    parse_html_to_sections,
    resolve_image_path as _resolve_image_path,
    update_html_section,
)
from app.models import (
    AuditItem,
    AuditRequest,
    AuditResult,
    AgentExecutionRequest,
    ChatRequest,
    ChatResult,
    ConfigUpdateRequest,
    CriteriaUpdateRequest,
    DocumentSaveRequest,
    ExportDocxRequest,
    GenerateRequest,
    LibraryAttachRequest,
    MemoryWriteRequest,
    OutlineUpdateRequest,
    PackageSubmissionRequest,
    QuickCreateRequest,
    RefineRequest,
    RegenerateSectionRequest,
    RestoreVersionRequest,
    SectionUpdateRequest,
    SnapshotRequest,
)
from app.packaging import package_project_submission
from app.prompts import default_outline, section_prompt
from app.search import index_source_embeddings as _search_index_source_embeddings
from app.search import hybrid_memory_search as _search_hybrid_memory
from app.search import hybrid_source_search as _search_hybrid_source
from app.settings import get_gemini_api_key, persist_env_value, settings
from app.storage import Store
from app.uploads import save_content_addressed_upload, save_upload
from docx_exporter import create_docx_document


app = FastAPI(title="DocStudio API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
store = Store(settings.database_path)

AGENT_ARTIFACT_KINDS = {
    "document", "code", "database", "archive", "model", "image", "report", "data", "other",
}
AGENT_ARTIFACT_EXTENSIONS = {
    ".docx", ".pdf", ".txt", ".md", ".csv", ".xlsx", ".sql", ".db", ".sqlite", ".dmd",
    ".py", ".java", ".cs", ".csproj", ".sln", ".html", ".css", ".js", ".jsx", ".ts", ".tsx",
    ".json", ".xml", ".yaml", ".yml", ".zip", ".rar", ".7z", ".png", ".jpg", ".jpeg", ".webp",
}


def require_project(project_id: str) -> dict:
    project = store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    return project


def require_project_criterion(project: dict, criterion_id: str | None) -> str | None:
    criterion_id = (criterion_id or "").strip() or None
    if criterion_id and not any(item["id"] == criterion_id for item in project.get("criteria", [])):
        raise HTTPException(status_code=400, detail="El criterio no pertenece al proyecto.")
    return criterion_id

# -- Thin wrappers that bind the module-level store to the extracted service functions --

def index_source_embeddings(source_id: str) -> int:
    return _search_index_source_embeddings(source_id, store)


async def hybrid_source_search(project_id: str, query: str, limit: int = 8) -> list[dict]:
    return await _search_hybrid_source(project_id, query, limit, store)


async def hybrid_memory_search(project_id: str, query: str, limit: int = 8) -> list[dict]:
    return await _search_hybrid_memory(project_id, query, limit, store)



@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": app.version,
        "database": str(settings.database_path),
        "fts5": store.fts_enabled,
        "library_root": str(settings.library_root),
    }


@app.get("/api/config")
def get_config() -> dict:
    key = get_gemini_api_key()
    return {
        "has_api_key": bool(key),
        "api_key_masked": f"{key[:4]}...{key[-4:]}" if len(key) > 8 else ("Configurada" if key else "No configurada"),
        "default_student": settings.default_author,
        "default_institution": settings.default_institution,
        "default_career": settings.default_career,
        "model": settings.gemini_model,
        "embedding_model": settings.embedding_model,
        "library_root": str(settings.library_root),
        "database_path": str(settings.database_path),
    }


@app.post("/api/config")
def update_config(request: ConfigUpdateRequest) -> dict:
    if request.gemini_api_key:
        persist_env_value("GEMINI_API_KEY", request.gemini_api_key.strip())
    if request.gemini_model:
        persist_env_value("GEMINI_MODEL", request.gemini_model.strip())
    if request.author_name is not None:
        persist_env_value("STUDIO_DEFAULT_AUTHOR", request.author_name.strip())
    if request.institution is not None:
        persist_env_value("STUDIO_DEFAULT_INSTITUTION", request.institution.strip())
    if request.career is not None:
        persist_env_value("STUDIO_DEFAULT_CAREER", request.career.strip())
    return {"status": "ok", "message": "Configuración guardada."}


@app.get("/api/library/files")
def library_files(limit: int = 250) -> dict:
    return {"root": str(settings.library_root), "files": list_library_files(settings.library_root, max(1, min(limit, 1000)))}


@app.get("/api/projects")
def list_projects() -> list[dict]:
    return store.list_projects()


@app.get("/api/projects/{project_id}")
def get_project(project_id: str) -> dict:
    return require_project(project_id)


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str) -> dict:
    require_project(project_id)
    deleted = store.delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    return {"status": "deleted", "id": project_id}


@app.put("/api/projects/{project_id}/document")
def save_document(project_id: str, request: DocumentSaveRequest) -> dict:
    require_project(project_id)
    store.update_document(project_id, request.html_content)
    return {"status": "saved"}


@app.put("/api/projects/{project_id}/outline")
def update_project_outline(project_id: str, request: OutlineUpdateRequest) -> dict:
    require_project(project_id)
    serialized = [item.model_dump() for item in request.outline]
    store.update_outline(project_id, serialized)
    return {"status": "saved", "project_id": project_id, "outline": serialized}


@app.put("/api/projects/{project_id}/criteria")
def replace_project_criteria(project_id: str, request: CriteriaUpdateRequest) -> dict:
    require_project(project_id)
    serialized = [item.model_dump() for item in request.criteria]
    updated = store.replace_criteria(project_id, serialized)
    return {"status": "saved", "project_id": project_id, "criteria": updated}


@app.post("/api/projects/{project_id}/criteria")
def add_project_criteria(project_id: str, request: CriteriaUpdateRequest) -> dict:
    require_project(project_id)
    serialized = [item.model_dump() for item in request.criteria]
    added = store.add_criteria(project_id, serialized)
    return {"status": "added", "project_id": project_id, "criteria": added}



@app.post("/api/projects/{project_id}/snapshots")
def create_snapshot(project_id: str, request: SnapshotRequest) -> dict:
    require_project(project_id)
    version = store.create_snapshot(project_id, request.html_content, request.reason)
    return {"status": "saved", "version": version}


@app.get("/api/projects/{project_id}/versions")
def list_versions(project_id: str) -> list[dict]:
    require_project(project_id)
    return store.list_versions(project_id)


@app.post("/api/projects/{project_id}/versions/{version_number}/restore")
def restore_version(project_id: str, version_number: int, request: RestoreVersionRequest | None = None) -> dict:
    require_project(project_id)
    try:
        current_html = request.current_html_content if request else None
        return store.restore_version(project_id, version_number, current_html)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc




@app.post("/api/projects/quick-create")
def quick_create_project(request: QuickCreateRequest) -> dict:
    outline = [item.model_dump() for item in request.initial_sections] if request.initial_sections else default_outline()
    project_id = store.create_project(
        title=request.title,
        subject=request.subject,
        student=request.student,
        career=request.career,
        summary=request.summary or f"Trabajo para {request.subject}",
        rubric_text=request.pauta_text,
        deliverables=request.deliverables,
        outline=outline,
    )
    criteria = []
    if request.criteria:
        criteria = store.add_criteria(project_id, [item.model_dump() for item in request.criteria])
    if request.pauta_text:
        source_dir = settings.projects_dir / project_id / "sources"
        source_dir.mkdir(parents=True, exist_ok=True)
        source_file = source_dir / "pauta.txt"
        source_file.write_text(request.pauta_text, encoding="utf-8")
        store.add_source(project_id, source_file, "pauta.txt", "rubric", request.pauta_text)
    return {
        "status": "created",
        "project_id": project_id,
        "title": request.title,
        "subject": request.subject,
        "criteria": criteria,
        "outline": outline,
    }


@app.post("/api/projects/import")
async def import_project_offline(
    title: str = Form(...),
    file: UploadFile | None = File(None),
    pauta_raw_text: str | None = Form(None),
    subject: str = Form("General"),
    student: str | None = Form(None),
    career: str | None = Form(None),
) -> dict:
    clean_title = title.strip()
    if not clean_title:
        raise HTTPException(status_code=400, detail="El título del proyecto es obligatorio en modo local.")
    resolved_student = (student or settings.default_author or "Autor").strip()
    resolved_career = (career or settings.default_career or "").strip()
    filename = "pauta-pegada.txt"
    temp_path: Path | None = None
    try:
        if file and file.filename:
            filename = Path(file.filename).name
            handle = tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix)
            handle.close()
            temp_path = Path(handle.name)
            save_upload(file, temp_path)
            text_content = await run_in_threadpool(extract_text, temp_path, settings.max_source_chars)
        else:
            text_content = (pauta_raw_text or "").strip()
        if len(text_content) < 10:
            raise HTTPException(status_code=400, detail="No se pudo extraer texto suficiente de la pauta.")

        outline = default_outline()
        project_id = store.create_project(
            title=clean_title,
            subject=subject.strip() or "General",
            student=resolved_student,
            career=resolved_career,
            summary="Proyecto importado localmente; pauta pendiente de desglosar en criterios.",
            rubric_text=text_content,
            deliverables=[],
            outline=outline,
        )
        source_dir = settings.projects_dir / project_id / "sources"
        if file and file.filename:
            stored_path = save_content_addressed_upload(file, source_dir, filename)
        else:
            stored_path = source_dir / "pauta-pegada.txt"
            stored_path.parent.mkdir(parents=True, exist_ok=True)
            stored_path.write_text(text_content, encoding="utf-8")
        store.add_source(project_id, stored_path, filename, "rubric_unparsed", text_content)
        return {
            "project_id": project_id,
            "title": clean_title,
            "subject": subject.strip() or "General",
            "student": resolved_student,
            "career": resolved_career,
            "summary": "Proyecto importado localmente; pauta pendiente de desglosar en criterios.",
            "deliverables": [],
            "key_requirements": [],
            "criteria": [],
            "outline": outline,
            "raw_pauta_full": text_content,
            "requires_manual_rubric_review": True,
            "ai_used": False,
        }
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


@app.patch("/api/projects/{project_id}/section")
def update_project_section(project_id: str, request: SectionUpdateRequest) -> dict:
    project = require_project(project_id)
    current_html = project.get("document_html") or ""
    new_html = update_html_section(current_html, request.heading, request.content_html)
    version = None
    if request.create_snapshot:
        version = store.create_snapshot(project_id, new_html, request.reason or f"section:{request.heading[:25]}")
    else:
        store.update_document(project_id, new_html)
    return {
        "status": "updated",
        "project_id": project_id,
        "heading": request.heading,
        "version": version,
        "html_content": new_html,
    }


@app.get("/api/agent/projects/{project_id}/context")
def agent_project_context(project_id: str) -> dict:
    project = require_project(project_id)
    artifacts = store.list_artifacts(project_id)
    executions = store.list_executions(project_id, 50)
    pending_criteria = [item for item in project["criteria"] if item.get("status") != "complete"]
    return {
        "schema_version": "1.0",
        "project": project,
        "pending_criteria": pending_criteria,
        "artifacts": artifacts,
        "recent_executions": executions,
        "constraints": {
            "completion_is_audit_controlled": True,
            "artifact_validation_default": "unverified",
            "evidence_content_requires_manual_review": True,
        },
        "operations": {
            "update_section": f"/api/projects/{project_id}/section",
            "attach_source": f"/api/agent/projects/{project_id}/sources",
            "attach_artifact": f"/api/agent/projects/{project_id}/artifacts",
            "register_execution": f"/api/agent/projects/{project_id}/executions",
            "update_outline": f"/api/projects/{project_id}/outline",
            "update_criteria": f"/api/projects/{project_id}/criteria",
            "request_audit": f"/api/projects/{project_id}/audit",
            "export_docx": f"/api/agent/projects/{project_id}/export-docx",
            "package_submission": f"/api/agent/projects/{project_id}/package-submission",
        },
    }


@app.post("/api/agent/projects/{project_id}/sources")
async def agent_attach_source(
    project_id: str,
    file: UploadFile = File(...),
    kind: str = Form("study_material"),
) -> dict:
    require_project(project_id)
    filename = Path(file.filename or "source.txt").name
    target_dir = settings.projects_dir / project_id / "sources"
    try:
        path = save_content_addressed_upload(file, target_dir, filename)
        text = await run_in_threadpool(extract_text, path, settings.max_source_chars)
        resolved_kind = kind.strip().lower() if kind and kind.strip() else classify_document(path)
        source = store.add_source(project_id, path, filename, resolved_kind, text)
        try:
            source["embedded_chunks"] = await run_in_threadpool(index_source_embeddings, source["id"])
        except Exception:
            source["embedded_chunks"] = 0
        return source
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"No se pudo indexar la fuente: {exc}") from exc


@app.post("/api/agent/projects/{project_id}/artifacts")
async def agent_attach_artifact(
    project_id: str,
    file: UploadFile = File(...),
    kind: str = Form("other"),
    criterion_id: str | None = Form(None),
    source: str = Form("agent"),
    description: str = Form(""),
) -> dict:
    project = require_project(project_id)
    criterion_id = require_project_criterion(project, criterion_id)
    normalized_kind = kind.strip().lower()
    if normalized_kind not in AGENT_ARTIFACT_KINDS:
        raise HTTPException(status_code=400, detail=f"Tipo de artefacto no permitido: {kind}")
    filename = Path(file.filename or "").name
    suffix = Path(filename).suffix.lower()
    if not filename or suffix not in AGENT_ARTIFACT_EXTENSIONS:
        raise HTTPException(status_code=400, detail="La extensión del artefacto no está permitida.")
    normalized_source = source.strip()[:100]
    if not normalized_source:
        raise HTTPException(status_code=400, detail="El origen del artefacto es obligatorio.")
    target_dir = settings.projects_dir / project_id / "artifacts"
    stored_path = save_content_addressed_upload(file, target_dir, filename)
    item = store.add_artifact(
        project_id,
        stored_path,
        filename,
        normalized_kind,
        file.content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream",
        normalized_source,
        description.strip()[:5000],
        criterion_id,
    )
    item["url"] = f"/api/agent/artifacts/{item['id']}/content"
    return item


@app.get("/api/agent/artifacts/{artifact_id}/content")
def agent_artifact_content(artifact_id: str) -> FileResponse:
    item = store.get_artifact(artifact_id)
    if not item or not Path(item["stored_path"]).is_file():
        raise HTTPException(status_code=404, detail="Artefacto no encontrado.")
    return FileResponse(item["stored_path"], media_type=item["media_type"], filename=item["filename"])


@app.post("/api/agent/projects/{project_id}/executions")
def agent_register_execution(project_id: str, request: AgentExecutionRequest) -> dict:
    project = require_project(project_id)
    criterion_id = require_project_criterion(project, request.criterion_id)
    if not store.artifacts_belong_to_project(project_id, request.artifact_ids):
        raise HTTPException(status_code=400, detail="Uno o más artefactos no pertenecen al proyecto.")
    if request.status == "succeeded" and request.exit_code not in {None, 0}:
        raise HTTPException(status_code=400, detail="Una ejecución con código distinto de cero no puede declararse exitosa.")
    return store.add_execution(
        project_id,
        agent=request.agent,
        action=request.action,
        status=request.status,
        criterion_id=criterion_id,
        command=request.command,
        exit_code=request.exit_code,
        stdout_excerpt=request.stdout_excerpt,
        stderr_excerpt=request.stderr_excerpt,
        artifact_ids=request.artifact_ids,
    )




@app.post("/api/analyze-rubric")
async def analyze_rubric(
    file: UploadFile | None = File(None),
    pauta_raw_text: str | None = Form(None),
    subject: str = Form(""),
    student: str | None = Form(None),
    career: str | None = Form(None),
) -> dict:
    resolved_student = (student or settings.default_author or "Autor").strip()
    resolved_career = (career or settings.default_career or "").strip()
    temp_path: Path | None = None
    filename = "pauta-pegada.txt"
    try:
        if file and file.filename:
            filename = Path(file.filename).name
            handle = tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix)
            handle.close()
            temp_path = Path(handle.name)
            save_upload(file, temp_path)
            text_content = await run_in_threadpool(extract_text, temp_path, settings.max_source_chars)
        else:
            text_content = (pauta_raw_text or "").strip()
        if len(text_content) < 40:
            raise HTTPException(status_code=400, detail="No se pudo extraer suficiente texto de la pauta.")

        analysis = await run_in_threadpool(ai.analyze_rubric, text_content, subject)
        if subject.strip():
            analysis.subject = subject.strip()
        project_id = store.create_project(
            title=analysis.title,
            subject=analysis.subject,
            student=resolved_student,
            career=resolved_career,
            summary=analysis.summary,
            rubric_text=text_content,
            deliverables=analysis.deliverables,
            outline=[item.model_dump() for item in analysis.outline],
        )
        criteria = store.add_criteria(project_id, [item.model_dump() for item in analysis.criteria])
        project_sources = settings.projects_dir / project_id / "sources"
        project_sources.mkdir(parents=True, exist_ok=True)
        stored_path = project_sources / filename
        if temp_path:
            shutil.copy2(temp_path, stored_path)
        else:
            stored_path.write_text(text_content, encoding="utf-8")
        source = store.add_source(project_id, stored_path, filename, "rubric", text_content)
        try:
            source["embedded_chunks"] = await run_in_threadpool(index_source_embeddings, source["id"])
        except Exception:
            source["embedded_chunks"] = 0

        payload = analysis.model_dump()
        payload.update({
            "project_id": project_id,
            "criteria": criteria,
            "raw_pauta_snippet": text_content[:2000],
            "raw_pauta_full": text_content,
        })
        return payload
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)


@app.post("/api/projects/{project_id}/sources")
async def upload_sources(project_id: str, files: list[UploadFile] = File(...)) -> dict:
    require_project(project_id)
    results = []
    target_dir = settings.projects_dir / project_id / "sources"
    for upload in files:
        filename = Path(upload.filename or "source.txt").name
        try:
            path = save_content_addressed_upload(upload, target_dir, filename)
            text = await run_in_threadpool(extract_text, path, settings.max_source_chars)
            source = store.add_source(project_id, path, filename, classify_document(path), text)
            try:
                source["embedded_chunks"] = await run_in_threadpool(index_source_embeddings, source["id"])
            except Exception:
                source["embedded_chunks"] = 0
            results.append(source)
        except Exception as exc:
            results.append({"filename": filename, "error": str(exc)})
    return {"sources": results}


@app.post("/api/projects/{project_id}/sources/attach")
async def attach_library_source(project_id: str, request: LibraryAttachRequest) -> dict:
    require_project(project_id)
    path = Path(request.path).resolve()
    try:
        path.relative_to(settings.library_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="La fuente debe estar dentro de la biblioteca de estudio configurada.") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")
    text = await run_in_threadpool(extract_text, path, settings.max_source_chars)
    source = store.add_source(project_id, path, path.name, classify_document(path), text)
    try:
        source["embedded_chunks"] = await run_in_threadpool(index_source_embeddings, source["id"])
    except Exception:
        source["embedded_chunks"] = 0
    return source


@app.get("/api/projects/{project_id}/search")
def search_project_sources(project_id: str, q: str, limit: int = 8) -> dict:
    require_project(project_id)
    return {"results": store.search_sources(project_id, q, max(1, min(limit, 20)))}


@app.delete("/api/projects/{project_id}/sources/{source_id}")
def delete_project_source(project_id: str, source_id: str) -> dict:
    require_project(project_id)
    deleted = store.delete_source(project_id, source_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Fuente no encontrada.")
    return {"status": "deleted", "id": source_id}



@app.post("/api/generate-document")
async def generate_document(request: GenerateRequest) -> dict:
    project = require_project(request.project_id) if request.project_id else None
    criteria = project.get("criteria", []) if project else []
    sections: list[str] = []
    if request.mode == "single":
        outline = "\n".join(f"- {card.title}: {card.description}" for card in request.outline)
        prompt = section_prompt(request, {"title": request.title, "description": outline, "needs_code": True,
                                                  "needs_evidence": True}, request.pauta_text[:16000], "")
        sections.append(clean_model_output(await run_in_threadpool(ai.text, prompt)))
        html_content = "\n".join(sections)
        if request.project_id:
            store.update_document(request.project_id, html_content)
            store.create_snapshot(request.project_id, html_content, "generated")
    else:
        for card_model in request.outline:
            card = card_model.model_dump()
            related = [criteria[index] for index in card.get("criterion_indexes", []) if index < len(criteria)]
            rubric_context = "\n".join(
                f"- {item['indicator']} ({item.get('points') or 'sin puntaje'} puntos)" for item in related
            ) or request.pauta_text[:5000]
            source_hits = await hybrid_source_search(
                request.project_id, f"{card['title']} {card['description']}", 5
            ) if request.project_id else []
            source_context = "\n\n".join(
                f"[Fuente: {hit['filename']}, fragmento {hit['chunk_index'] + 1}]\n{hit['content']}" for hit in source_hits
            )[:14000]
            memory_hits = await hybrid_memory_search(
                request.project_id, f"{card['title']} {card['description']}", 4
            ) if request.project_id else []
            memory_context = "\n".join(f"- {item['content']}" for item in memory_hits)
            try:
                section_text = clean_model_output(await run_in_threadpool(
                    ai.text, section_prompt(request, card, rubric_context, source_context, memory_context)
                ))
            except Exception as exc:
                section_text = f"<h2>{html.escape(card['title'])}</h2><p><em>[Sección pendiente: no se pudo completar la generación automática ({html.escape(str(exc))}). Puedes redactar aquí o regenerar esta sección.]</em></p>"
            sections.append(section_text)
            if request.project_id:
                store.update_document(request.project_id, "\n".join(sections))
        html_content = "\n".join(sections)
        if request.project_id:
            store.create_snapshot(request.project_id, html_content, "generated")
    return {"project_id": request.project_id, "title": request.title, "subject": request.subject,
            "student": request.student, "career": request.career, "html_content": html_content}


@app.post("/api/projects/{project_id}/regenerate-section")
async def regenerate_section(project_id: str, request: RegenerateSectionRequest) -> dict:
    project = require_project(project_id)
    clean_heading = request.heading.strip()
    if not clean_heading:
        raise HTTPException(status_code=400, detail="El título de la sección es obligatorio.")

    outline = project.get("outline") or []
    target_card = None
    for c in outline:
        title = (c.get("title") or "").strip().lower()
        if title == clean_heading.lower() or clean_heading.lower() in title or title in clean_heading.lower():
            target_card = c
            break

    if not target_card:
        target_card = {
            "title": clean_heading,
            "description": f"Sección de {clean_heading}",
            "needs_code": True,
            "needs_evidence": True,
            "criterion_indexes": [],
        }

    criteria = project.get("criteria", [])
    related = [criteria[index] for index in target_card.get("criterion_indexes", []) if index < len(criteria)]
    rubric_context = "\n".join(
        f"- {item['indicator']} ({item.get('points') or 'sin puntaje'} puntos)" for item in related
    ) or (project.get("rubric_text") or "")[:5000]

    search_query = f"{target_card['title']} {target_card.get('description', '')} {request.instruction or ''}".strip()
    source_hits = await hybrid_source_search(project_id, search_query, 5)
    source_context = "\n\n".join(
        f"[Fuente: {hit['filename']}, fragmento {hit['chunk_index'] + 1}]\n{hit['content']}" for hit in source_hits
    )[:14000]

    memory_hits = await hybrid_memory_search(project_id, search_query, 4)
    memory_context = "\n".join(f"- {item['content']}" for item in memory_hits)

    gen_req = GenerateRequest(
        project_id=project_id,
        title=project.get("title") or "Documento",
        subject=project.get("subject") or "General",
        student=project.get("student") or settings.default_author or "Autor",
        career=project.get("career") or "",
        outline=[],
        pauta_text=project.get("rubric_text") or "",
    )

    prompt = section_prompt(gen_req, target_card, rubric_context, source_context, memory_context)
    if request.instruction:
        prompt += f"\nINSTRUCCIÓN ADICIONAL DEL USUARIO:\n{request.instruction.strip()}\n"

    new_section_html = clean_model_output(await run_in_threadpool(ai.text, prompt))
    persisted_html = project.get("document_html") or ""
    current_html = (
        request.current_html_content
        if request.current_html_content is not None
        else persisted_html
    )
    if request.current_html_content is not None and request.current_html_content != persisted_html:
        store.create_snapshot(project_id, current_html, f"before_regen:{clean_heading[:20]}")

    updated_doc_html = update_html_section(current_html, clean_heading, new_section_html)
    version = store.create_snapshot(project_id, updated_doc_html, f"regen:{clean_heading[:25]}")

    return {
        "status": "regenerated",
        "project_id": project_id,
        "heading": clean_heading,
        "section_html": new_section_html,
        "html_content": updated_doc_html,
        "version": version,
    }


@app.post("/api/refine-text")
async def refine_text(request: RefineRequest) -> dict:
    memory_context = ""
    source_context = ""
    if request.project_id:
        require_project(request.project_id)
        memories = await hybrid_memory_search(request.project_id, request.instruction, 6)
        sources = await hybrid_source_search(request.project_id, request.instruction, 5)
        memory_context = "\n".join(f"- {item['content']}" for item in memories)
        source_context = "\n\n".join(
            f"[Fuente: {item['filename']}, fragmento {item['chunk_index'] + 1}]\n{item['content']}" for item in sources
        )[:12000]
    prompt = f"""
Mejora un fragmento de un documento técnico de la asignatura {request.subject}.
Instrucción del usuario: {request.instruction}
Preferencias o decisiones recordadas:
{memory_context or 'Ninguna.'}
Fuentes recuperadas:
{source_context or 'Ninguna. No inventes resultados ni referencias.'}
Texto original: <TEXTO>{request.selected_text}</TEXTO>
Devuelve únicamente HTML compatible con Tiptap. Conserva los hechos del original. Si la instrucción requiere
evidencia que no existe, deja un marcador "EVIDENCIA PENDIENTE" en lugar de fingir una captura o ejecución.
"""
    return {"refined_text": clean_model_output(await run_in_threadpool(ai.text, prompt))}


@app.get("/api/projects/{project_id}/messages")
def list_messages(project_id: str) -> list[dict]:
    require_project(project_id)
    return store.list_messages(project_id, 50)


@app.post("/api/projects/{project_id}/memories")
async def remember(project_id: str, request: MemoryWriteRequest) -> dict:
    require_project(project_id)
    embedding = None
    if get_gemini_api_key():
        try:
            vectors = await run_in_threadpool(ai.embed_documents, [request.content], ["memoria del proyecto"])
            embedding = vectors[0] if vectors else None
        except Exception:
            embedding = None
    return store.add_memory(project_id, request.kind, request.content, request.importance,
                            embedding=embedding, embedding_model=settings.embedding_model if embedding else None)


@app.get("/api/projects/{project_id}/memories")
def list_project_memories(project_id: str) -> list[dict]:
    require_project(project_id)
    return store.list_memories(project_id)


@app.delete("/api/memories/{memory_id}")
def delete_memory(memory_id: str) -> dict:
    deleted = store.delete_memory(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memoria no encontrada.")
    return {"status": "deleted", "id": memory_id}


@app.post("/api/projects/{project_id}/chat", response_model=ChatResult)
async def project_chat(project_id: str, request: ChatRequest) -> ChatResult:
    project = require_project(project_id)
    store.add_message(project_id, "user", request.message)
    history = store.list_messages(project_id, 14)
    memories = await hybrid_memory_search(project_id, request.message, 8)
    sources = await hybrid_source_search(project_id, request.message, 7)
    history_text = "\n".join(f"{item['role']}: {item['content']}" for item in history)
    memory_text = "\n".join(f"- [{item['kind']}] {item['content']}" for item in memories)
    source_text = "\n\n".join(
        f"[Fuente: {item['filename']}, fragmento {item['chunk_index'] + 1}]\n{item['content']}" for item in sources
    )[:16000]
    criteria_text = "\n".join(
        f"- id={item['id']} | {item['indicator']} | estado={item['status']}" for item in project["criteria"]
    )
    prompt = f"""
Eres el copiloto del proyecto académico "{project['title']}" ({project['subject']}).
Ayuda a completar el trabajo con precisión. No afirmes que existe una captura, archivo o ejecución si no aparece
en el contexto. Cita fragmentos recuperados como [Fuente: nombre, fragmento N]. Separa una recomendación de un
hecho comprobado. Puedes sugerir acciones, pero no digas que ya modificaste el documento.
CRITERIOS:
{criteria_text}
MEMORIA DE LARGO PLAZO:
{memory_text or 'Sin memorias relevantes.'}
FUENTES RECUPERADAS:
{source_text or 'Sin fuentes recuperadas.'}
HISTORIAL RECIENTE:
{history_text}
EXTRACTO ACTUAL DEL DOCUMENTO:
{request.document_excerpt}
Mensaje actual: {request.message}
Guarda en memories_to_store solo preferencias estables, decisiones o hechos del proyecto que serán útiles en
sesiones futuras. Usa suggested_actions únicamente si hay una edición concreta y segura que proponer.
"""
    result = await run_in_threadpool(ai.chat, prompt)
    store.add_message(project_id, "assistant", result.answer)
    return result




@app.post("/api/projects/{project_id}/audit", response_model=AuditResult)
async def audit_project(project_id: str, request: AuditRequest) -> AuditResult:
    project = require_project(project_id)
    fallback = offline_audit(project, request.html_content)
    result = fallback
    if request.use_ai and get_gemini_api_key():
        evidence_counts = valid_evidence_by_criterion(project)
        criteria_text = "\n".join(
            f"- criterion_id={item['id']} | indicador={item['indicator']} | puntos={item.get('points')} | "
            f"requiere_evidencia={bool(item['requires_evidence'])} | "
            f"archivos_vinculados={len(evidence_counts.get(item['id'], []))}" for item in project["criteria"]
        )
        prompt = f"""
Audita el documento contra cada indicador. No concedas cumplimiento por promesas o marcadores de evidencia.
Una frase "EVIDENCIA PENDIENTE" significa que la evidencia NO existe. Conserva exactamente cada criterion_id.
CRITERIOS:
{criteria_text}
DOCUMENTO:
{request.html_content[:60000]}
"""
        try:
            result = await run_in_threadpool(ai.audit, prompt)
        except Exception:
            pass
    result = enforce_evidence_grounding(project, result, fallback)
    store.update_audit(project_id, [item.model_dump() for item in result.items])
    return result


@app.post("/api/projects/{project_id}/evidence")
async def upload_evidence(
    project_id: str,
    file: UploadFile = File(...),
    caption: str = Form(""),
    criterion_id: str | None = Form(None),
    watermark: bool = Form(False),
    watermark_text: str | None = Form(None),
) -> dict:
    project = require_project(project_id)
    resolved_criterion_id = require_project_criterion(project, criterion_id)
    filename = Path(file.filename or "evidence.png").name
    suffix = Path(filename).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=400, detail="La evidencia debe ser PNG, JPG o WebP.")
    stem = re.sub(r"[^a-zA-Z0-9_-]", "_", Path(filename).stem)[:40]
    target = settings.projects_dir / project_id / "evidence" / f"{stem}_{os.urandom(5).hex()}{suffix}"
    save_upload(file, target)

    try:
        if watermark:
            student_name = project.get("student") or settings.default_author or "Autor"
            institution_name = project.get("institution") or settings.default_institution or "DocStudio"
            resolved_text = (watermark_text or f"{student_name} - {institution_name}").strip()
            try:
                apply_watermark(target, resolved_text)
            except Exception:
                pass

        item = store.add_evidence(project_id, target, filename, caption, resolved_criterion_id)
        item["url"] = f"/api/evidence/{item['id']}/content"
        return item
    except Exception:
        target.unlink(missing_ok=True)
        raise


@app.post("/api/projects/{project_id}/evidence/{evidence_id}/watermark")
def watermark_existing_evidence(
    project_id: str,
    evidence_id: str,
    watermark_text: str | None = None,
) -> dict:
    project = require_project(project_id)
    item = store.get_evidence(evidence_id)
    if not item or not Path(item["stored_path"]).is_file():
        raise HTTPException(status_code=404, detail="Evidencia no encontrada.")
    student_name = project.get("student") or settings.default_author or "Autor"
    institution_name = project.get("institution") or settings.default_institution or "DocStudio"
    resolved_text = (watermark_text or f"{student_name} - {institution_name}").strip()
    apply_watermark(item["stored_path"], resolved_text)
    return {"status": "watermarked", "evidence_id": evidence_id, "url": f"/api/evidence/{evidence_id}/content"}



@app.get("/api/evidence/{evidence_id}/content")
def evidence_content(evidence_id: str) -> FileResponse:
    item = store.get_evidence(evidence_id)
    if not item or not Path(item["stored_path"]).is_file():
        raise HTTPException(status_code=404, detail="Evidencia no encontrada.")
    media_type = mimetypes.guess_type(item["stored_path"])[0] or "application/octet-stream"
    return FileResponse(item["stored_path"], media_type=media_type, filename=item["filename"])


@app.delete("/api/projects/{project_id}/evidence/{evidence_id}")
def delete_project_evidence(project_id: str, evidence_id: str) -> dict:
    require_project(project_id)
    deleted = store.delete_evidence(project_id, evidence_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Evidencia no encontrada.")
    return {"status": "deleted", "id": evidence_id}

def resolve_image_path(value: str | None) -> str | None:
    return _resolve_image_path(value, get_evidence=store.get_evidence, get_artifact=store.get_artifact)


@app.post("/api/export-docx")
async def export_docx(request: ExportDocxRequest) -> FileResponse:
    if request.sections:
        sections = [item.model_dump() for item in request.sections]
    elif request.html_content:
        sections = parse_html_to_sections(request.html_content)
    else:
        sections = [{"type": "paragraph", "content": "Documento vacío."}]
    for section in sections:
        if section.get("type") == "image":
            section["image_path"] = resolve_image_path(section.get("image_path"))
    filename_stem = re.sub(r'[\\/*?:"<>|]', "", request.title or "Documento Tecnico")[:60].strip()
    output_dir = settings.projects_dir / (request.project_id or "exports") / "exports"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{filename_stem}.docx"
    data = request.model_dump(exclude={"html_content", "sections"})
    data["sections"] = sections
    await run_in_threadpool(create_docx_document, data, str(output_path))
    return FileResponse(output_path, filename=output_path.name,
                        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


@app.post("/api/projects/{project_id}/package-submission")
async def package_submission(
    project_id: str,
    request: PackageSubmissionRequest | None = None,
) -> FileResponse:
    project = require_project(project_id)
    html_content = (request.html_content if request and request.html_content else project.get("document_html")) or "<p>Documento inicial.</p>"

    sections = parse_html_to_sections(html_content)
    for section in sections:
        if section.get("type") == "image":
            section["image_path"] = resolve_image_path(section.get("image_path"))

    filename_stem = re.sub(r'[\\/*?:"<>|]', "", project.get("title") or "Entrega")[:60].strip() or "Entrega"
    output_dir = settings.projects_dir / project_id / "exports"
    output_dir.mkdir(parents=True, exist_ok=True)
    docx_path = output_dir / f"{filename_stem}.docx"

    doc_data = {
        "title": project.get("title") or "Entrega",
        "subject": project.get("subject") or "General",
        "student": project.get("student") or settings.default_author or "Autor",
        "career": project.get("career") or settings.default_career or "",
        "institution": project.get("institution") or settings.default_institution or "",
        "sections": sections,
    }
    await run_in_threadpool(create_docx_document, doc_data, str(docx_path))

    include_sources = request.include_sources if request else True
    zip_path, zip_filename = await run_in_threadpool(
        package_project_submission, project_id, store, docx_path, include_sources
    )

    return FileResponse(zip_path, filename=zip_filename, media_type="application/zip")


@app.post("/api/agent/projects/{project_id}/export-docx")
async def agent_export_docx(
    project_id: str,
    output_path: str | None = None,
) -> dict:
    project = require_project(project_id)
    html_content = project.get("document_html") or "<p>Documento vacío.</p>"
    sections = parse_html_to_sections(html_content)
    for section in sections:
        if section.get("type") == "image":
            section["image_path"] = resolve_image_path(section.get("image_path"))

    filename_stem = re.sub(r'[\\/*?:"<>|]', "", project.get("title") or "Documento Tecnico")[:60].strip() or "Documento"
    if output_path:
        out = Path(output_path).resolve()
    else:
        output_dir = settings.projects_dir / project_id / "exports"
        output_dir.mkdir(parents=True, exist_ok=True)
        out = output_dir / f"{filename_stem}.docx"

    doc_data = {
        "title": project.get("title") or "Documento Técnico",
        "subject": project.get("subject") or "General",
        "student": project.get("student") or settings.default_author or "Autor",
        "career": project.get("career") or settings.default_career or "",
        "institution": project.get("institution") or settings.default_institution or "",
        "sections": sections,
    }
    await run_in_threadpool(create_docx_document, doc_data, str(out))
    return {
        "status": "ok",
        "project_id": project_id,
        "file_path": str(out),
        "filename": out.name,
        "size_bytes": out.stat().st_size if out.is_file() else 0,
    }


@app.post("/api/agent/projects/{project_id}/package-submission")
async def agent_package_submission(
    project_id: str,
    include_sources: bool = True,
) -> dict:
    project = require_project(project_id)
    html_content = project.get("document_html") or "<p>Documento inicial.</p>"
    sections = parse_html_to_sections(html_content)
    for section in sections:
        if section.get("type") == "image":
            section["image_path"] = resolve_image_path(section.get("image_path"))

    filename_stem = re.sub(r'[\\/*?:"<>|]', "", project.get("title") or "Entrega")[:60].strip() or "Entrega"
    output_dir = settings.projects_dir / project_id / "exports"
    output_dir.mkdir(parents=True, exist_ok=True)
    docx_path = output_dir / f"{filename_stem}.docx"

    doc_data = {
        "title": project.get("title") or "Entrega",
        "subject": project.get("subject") or "General",
        "student": project.get("student") or settings.default_author or "Autor",
        "career": project.get("career") or settings.default_career or "",
        "institution": project.get("institution") or settings.default_institution or "",
        "sections": sections,
    }
    await run_in_threadpool(create_docx_document, doc_data, str(docx_path))

    zip_path, zip_filename = await run_in_threadpool(
        package_project_submission, project_id, store, docx_path, include_sources
    )
    return {
        "status": "ok",
        "project_id": project_id,
        "zip_path": str(zip_path),
        "filename": zip_filename,
        "size_bytes": zip_path.stat().st_size if zip_path.is_file() else 0,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765)
