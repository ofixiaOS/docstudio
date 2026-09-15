from __future__ import annotations

import html
import mimetypes
import os
import re
import shutil
import tempfile
from pathlib import Path

from bs4 import BeautifulSoup, NavigableString, Tag
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from app.ai import ai
from app.documents import classify_document, extract_text, list_library_files
from app.models import (
    AuditItem,
    AuditRequest,
    AuditResult,
    ChatRequest,
    ChatResult,
    ConfigUpdateRequest,
    DocumentSaveRequest,
    ExportDocxRequest,
    GenerateRequest,
    LibraryAttachRequest,
    MemoryWriteRequest,
    QuickCreateRequest,
    RefineRequest,
    SectionUpdateRequest,
    SnapshotRequest,
)
from app.settings import get_gemini_api_key, persist_env_value, settings
from app.storage import Store
from docx_exporter import create_iplacex_document


app = FastAPI(title="Gamma Iplacex API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
store = Store(settings.database_path)


def require_project(project_id: str) -> dict:
    project = store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Proyecto no encontrado.")
    return project


def clean_model_output(value: str) -> str:
    value = value.strip()
    value = re.sub(r"^```(?:html|json)?\s*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s*```$", "", value)
    return value.strip()


def save_upload(upload: UploadFile, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    upload.file.seek(0)
    with destination.open("wb") as output:
        shutil.copyfileobj(upload.file, output)


def index_source_embeddings(source_id: str) -> int:
    if not get_gemini_api_key():
        return 0
    chunks = store.get_source_chunks(source_id)
    pending = [item for item in chunks if not item.get("embedding_json")]
    if not pending:
        return 0
    vectors = ai.embed_documents(
        [item["content"] for item in pending],
        [item["filename"] for item in pending],
    )
    pairs = [(item["id"], vector) for item, vector in zip(pending, vectors) if vector]
    store.set_chunk_embeddings(pairs, settings.embedding_model)
    return len(pairs)


async def hybrid_source_search(project_id: str, query: str, limit: int = 8) -> list[dict]:
    lexical = store.search_sources(project_id, query, limit)
    vector = []
    if get_gemini_api_key():
        try:
            query_embedding = await run_in_threadpool(ai.embed_query, query)
            vector = store.search_sources_vector(project_id, query_embedding, limit)
        except Exception:
            vector = []
    scores: dict[str, float] = {}
    values: dict[str, dict] = {}
    for result_set, weight in ((lexical, 1.0), (vector, 1.25)):
        for rank, item in enumerate(result_set, start=1):
            values[item["id"]] = item
            scores[item["id"]] = scores.get(item["id"], 0) + weight / (40 + rank)
    ordered = sorted(values.values(), key=lambda item: scores[item["id"]], reverse=True)
    return ordered[:limit]


async def hybrid_memory_search(project_id: str, query: str, limit: int = 8) -> list[dict]:
    lexical = store.search_memories(project_id, query, limit)
    vector = []
    if get_gemini_api_key():
        try:
            query_embedding = await run_in_threadpool(ai.embed_query, query)
            vector = store.search_memories_vector(project_id, query_embedding, limit)
        except Exception:
            vector = []
    scores: dict[str, float] = {}
    values: dict[str, dict] = {}
    for result_set, weight in ((lexical, 1.0), (vector, 1.25)):
        for rank, item in enumerate(result_set, start=1):
            values[item["id"]] = item
            importance_boost = float(item.get("importance", 0.5)) * 0.15
            scores[item["id"]] = scores.get(item["id"], 0) + (weight / (40 + rank)) + importance_boost
    ordered = sorted(values.values(), key=lambda item: scores[item["id"]], reverse=True)
    return ordered[:limit]


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
        "default_student": "Nicolás Javier Jara Guzmán",
        "default_institution": "Instituto Profesional Iplacex",
        "default_career": "Ingeniería en Informática",
        "model": settings.gemini_model,
        "embedding_model": settings.embedding_model,
        "library_root": str(settings.library_root),
        "database_path": str(settings.database_path),
    }


@app.post("/api/config")
def update_config(request: ConfigUpdateRequest) -> dict:
    persist_env_value("GEMINI_API_KEY", request.gemini_api_key.strip())
    if request.gemini_model:
        persist_env_value("GEMINI_MODEL", request.gemini_model.strip())
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


@app.put("/api/projects/{project_id}/document")
def save_document(project_id: str, request: DocumentSaveRequest) -> dict:
    require_project(project_id)
    store.update_document(project_id, request.html_content)
    return {"status": "saved"}


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
def restore_version(project_id: str, version_number: int) -> dict:
    require_project(project_id)
    try:
        return store.restore_version(project_id, version_number)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def update_html_section(existing_html: str, heading: str, content_html: str) -> str:
    soup = BeautifulSoup(existing_html or "", "html.parser")
    clean_heading = heading.strip().lower()
    target = None
    for h in soup.find_all(["h1", "h2", "h3"]):
        ht = h.get_text(" ", strip=True).lower()
        if clean_heading in ht or ht in clean_heading:
            target = h
            break
    new_section_soup = BeautifulSoup(content_html, "html.parser")
    if target:
        curr = target.next_sibling
        while curr:
            if isinstance(curr, Tag) and curr.name.lower() in ["h1", "h2", "h3"]:
                break
            nxt = curr.next_sibling
            curr.extract()
            curr = nxt
        insert_pt = target
        for el in list(new_section_soup.children):
            insert_pt.insert_after(el)
            insert_pt = el
        return str(soup)
    else:
        h_tag = soup.new_tag("h2")
        h_tag.string = heading
        soup.append(h_tag)
        for el in list(new_section_soup.children):
            soup.append(el)
        return str(soup)


@app.post("/api/projects/quick-create")
def quick_create_project(request: QuickCreateRequest) -> dict:
    outline = [item.model_dump() for item in request.initial_sections] if request.initial_sections else [
        {"id": "sec-intro", "title": "Introducción", "description": "Contexto y objetivos", "type": "intro", "needs_code": False, "needs_evidence": False},
        {"id": "sec-dev", "title": "Desarrollo Técnico", "description": "Ejecución y evidencia", "type": "development", "needs_code": True, "needs_evidence": True},
        {"id": "sec-conc", "title": "Conclusión", "description": "Síntesis de aprendizajes", "type": "conclusion", "needs_code": False, "needs_evidence": False},
        {"id": "sec-bib", "title": "Bibliografía", "description": "Fuentes consultadas", "type": "references", "needs_code": False, "needs_evidence": False},
    ]
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




@app.post("/api/analyze-rubric")
async def analyze_rubric(
    file: UploadFile | None = File(None),
    pauta_raw_text: str | None = Form(None),
    subject: str = Form(""),
    student: str = Form("Nicolás Javier Jara Guzmán"),
    career: str = Form("Ingeniería en Informática"),
) -> dict:
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
            student=student,
            career=career,
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
        path = target_dir / filename
        save_upload(upload, path)
        try:
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
        raise HTTPException(status_code=400, detail="La fuente debe estar dentro de la biblioteca Iplacex.") from exc
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


def section_prompt(request: GenerateRequest, card: dict, rubric_context: str, source_context: str, memory_context: str = "") -> str:
    return f"""
Redacta solamente una sección de un trabajo académico técnico para Iplacex.

TRABAJO: {request.title}
ASIGNATURA: {request.subject}
SECCIÓN: {card['title']}
OBJETIVO: {card['description']}
REQUIERE CÓDIGO: {card.get('needs_code', False)}
REQUIERE CAPTURA/EVIDENCIA: {card.get('needs_evidence', False)}

CRITERIOS RELACIONADOS:
{rubric_context or 'No hay criterios específicos asociados.'}

PREFERENCIAS O DECISIONES RECORDADAS DEL PROYECTO:
{memory_context or 'Ninguna preferencia previa registrada.'}

FRAGMENTOS DE FUENTES DISPONIBLES:
{source_context or 'No se adjuntaron materiales adicionales. No inventes citas ni resultados de ejecución.'}

Devuelve HTML semántico compatible con Tiptap. Comienza con h2 según corresponda y usa p, ul, ol,
pre/code y blockquote. Si hace falta una captura real, inserta exactamente un blockquote que comience con
"EVIDENCIA PENDIENTE:" y describa qué debe demostrar la captura; jamás inventes que una ejecución ocurrió.
No inventes bibliografía. Cuando uses una fuente adjunta, cítala por su nombre de archivo en el texto.
"""


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
            sections.append(clean_model_output(await run_in_threadpool(
                ai.text, section_prompt(request, card, rubric_context, source_context, memory_context)
            )))
    html_content = "\n".join(sections)
    if request.project_id:
        store.create_snapshot(request.project_id, html_content, "generated")
    return {"project_id": request.project_id, "title": request.title, "subject": request.subject,
            "student": request.student, "career": request.career, "html_content": html_content}


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
    memory_contents = result.memories_to_store[:5]
    memory_vectors: list[list[float]] = []
    if memory_contents:
        try:
            memory_vectors = await run_in_threadpool(
                ai.embed_documents, memory_contents, ["memoria del proyecto"] * len(memory_contents)
            )
        except Exception:
            memory_vectors = []
    for index, content in enumerate(memory_contents):
        embedding = memory_vectors[index] if index < len(memory_vectors) else None
        store.add_memory(project_id, "decision", content, 0.7, "assistant", embedding,
                         settings.embedding_model if embedding else None)
    return result


def offline_audit(project: dict, html_content: str) -> AuditResult:
    text = BeautifulSoup(html_content, "html.parser").get_text(" ", strip=True).lower()
    has_evidence = "evidencia pendiente" not in text and ("captura" in text or "figura" in text)
    items = []
    earned = 0.0
    possible = 0.0
    for criterion in project["criteria"]:
        words = {word for word in re.findall(r"\w+", criterion["indicator"].lower()) if len(word) > 4}
        ratio = sum(1 for word in words if word in text) / max(len(words), 1)
        evidence_ok = not criterion["requires_evidence"] or has_evidence
        status = "complete" if ratio >= 0.45 and evidence_ok else "partial" if ratio >= 0.2 else "missing"
        feedback = ("Hay cobertura textual y evidencia aparente; revísala manualmente." if status == "complete"
                    else "Falta evidencia real." if criterion["requires_evidence"] and not evidence_ok
                    else "El indicador no está cubierto con suficiente claridad.")
        points = float(criterion.get("points") or 0)
        possible += points
        earned += points * ({"complete": 1, "partial": 0.5, "missing": 0}[status])
        items.append(AuditItem(criterion_id=criterion["id"], status=status,
                               evidence_found=evidence_ok, feedback=feedback))
    score = earned / possible * 100 if possible else (
        sum({"complete": 1, "partial": 0.5, "missing": 0}[item.status] for item in items)
        / max(len(items), 1) * 100
    )
    return AuditResult(summary="Auditoría local preliminar; confirma manualmente las evidencias.",
                       estimated_score=score, items=items)


@app.post("/api/projects/{project_id}/audit", response_model=AuditResult)
async def audit_project(project_id: str, request: AuditRequest) -> AuditResult:
    project = require_project(project_id)
    result = offline_audit(project, request.html_content)
    if request.use_ai and get_gemini_api_key():
        criteria_text = "\n".join(
            f"- criterion_id={item['id']} | indicador={item['indicator']} | puntos={item.get('points')} | "
            f"requiere_evidencia={bool(item['requires_evidence'])}" for item in project["criteria"]
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
    store.update_audit(project_id, [item.model_dump() for item in result.items])
    return result


@app.post("/api/projects/{project_id}/evidence")
async def upload_evidence(
    project_id: str,
    file: UploadFile = File(...),
    caption: str = Form(""),
    criterion_id: str | None = Form(None),
) -> dict:
    require_project(project_id)
    filename = Path(file.filename or "evidence.png").name
    suffix = Path(filename).suffix.lower()
    if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
        raise HTTPException(status_code=400, detail="La evidencia debe ser PNG, JPG o WebP.")
    stem = re.sub(r"[^a-zA-Z0-9_-]", "_", Path(filename).stem)[:40]
    target = settings.projects_dir / project_id / "evidence" / f"{stem}_{os.urandom(5).hex()}{suffix}"
    save_upload(file, target)
    item = store.add_evidence(project_id, target, filename, caption, criterion_id)
    item["url"] = f"/api/evidence/{item['id']}/content"
    return item


@app.get("/api/evidence/{evidence_id}/content")
def evidence_content(evidence_id: str) -> FileResponse:
    item = store.get_evidence(evidence_id)
    if not item or not Path(item["stored_path"]).is_file():
        raise HTTPException(status_code=404, detail="Evidencia no encontrada.")
    media_type = mimetypes.guess_type(item["stored_path"])[0] or "application/octet-stream"
    return FileResponse(item["stored_path"], media_type=media_type, filename=item["filename"])


def parse_html_to_sections(html_content: str) -> list[dict]:
    soup = BeautifulSoup(html_content or "", "html.parser")
    sections: list[dict] = []
    root = soup.body or soup
    mapping = {"h1": "h1", "h2": "h2", "h3": "h3", "pre": "code", "blockquote": "callout", "p": "paragraph"}

    def process_node(node: Tag) -> None:
        tag = node.name.lower()
        if tag in {"ul", "ol"}:
            section_type = "ordered_item" if tag == "ol" else "list_item"
            for li in node.find_all("li", recursive=False):
                sections.append({
                    "type": section_type,
                    "content": li.get_text(" ", strip=True),
                    "content_html": str(li),
                })
            return

        if tag == "img":
            sections.append({
                "type": "image",
                "content": "",
                "image_path": node.get("src"),
                "image_alt": node.get("alt"),
            })
            return

        # If a block contains img tags, separate them cleanly so images are never lost
        if node.find("img"):
            for child in list(node.children):
                if isinstance(child, NavigableString):
                    text = str(child).strip()
                    if text:
                        sections.append({
                            "type": mapping.get(tag, "paragraph"),
                            "content": text,
                            "content_html": f"<{tag}>{html.escape(text)}</{tag}>",
                        })
                elif isinstance(child, Tag):
                    if child.name.lower() == "img":
                        sections.append({
                            "type": "image",
                            "content": "",
                            "image_path": child.get("src"),
                            "image_alt": child.get("alt"),
                        })
                    else:
                        if child.find("img"):
                            process_node(child)
                        else:
                            child_text = child.get_text(" ", strip=True)
                            if child_text:
                                sections.append({
                                    "type": mapping.get(tag, "paragraph"),
                                    "content": child_text,
                                    "content_html": str(child),
                                })
            return

        if tag not in mapping:
            for child in node.children:
                if isinstance(child, Tag):
                    process_node(child)
            return

        content = node.get_text("\n" if tag == "pre" else " ", strip=True)
        if content:
            sections.append({
                "type": mapping[tag],
                "content": content,
                "content_html": str(node),
            })

    for top_child in root.children:
        if isinstance(top_child, Tag):
            process_node(top_child)

    return sections



def resolve_image_path(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"/api/evidence/([^/]+)/content", html.unescape(value))
    if match:
        evidence = store.get_evidence(match.group(1))
        return evidence["stored_path"] if evidence else None
    return value if Path(value).is_file() else None


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
    filename_stem = re.sub(r'[\\/*?:"<>|]', "", request.title or "Trabajo Iplacex")[:60].strip()
    output_dir = settings.projects_dir / (request.project_id or "exports") / "exports"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{filename_stem}.docx"
    data = request.model_dump(exclude={"html_content", "sections"})
    data["sections"] = sections
    await run_in_threadpool(create_iplacex_document, data, str(output_path))
    return FileResponse(output_path, filename=output_path.name,
                        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765)
