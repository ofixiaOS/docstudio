from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Literal

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import requests
from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import BaseModel


class CriterionDraft(BaseModel):
    id: str | None = None
    criterion: str
    indicator: str
    points: float | None = None
    requires_evidence: bool = False
    evidence_description: str | None = None
    deliverable: str | None = None



class OutlineCardDraft(BaseModel):
    id: str | None = None
    title: str
    description: str
    type: Literal["intro", "development", "conclusion", "references"] = "development"
    needs_code: bool = False
    needs_evidence: bool = False
    criterion_indexes: list[int] = []


class GammaApiClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or os.getenv("GAMMA_API_URL", "http://127.0.0.1:8765")).rstrip("/")
        self._embedded_client: Any = None

    def _get_embedded_client(self) -> Any:
        if self._embedded_client is None:
            from starlette.testclient import TestClient
            from main import app

            self._embedded_client = TestClient(app)
        return self._embedded_client

    def request(self, method: str, path: str, **kwargs: Any) -> Any:
        force_embedded = os.getenv("GAMMA_FORCE_EMBEDDED", "").lower() in {"1", "true", "yes"}
        response = None
        if not force_embedded:
            try:
                response = requests.request(method, f"{self.base_url}{path}", timeout=60, **kwargs)
            except (requests.ConnectionError, requests.Timeout):
                response = None
            except requests.RequestException as exc:
                raise RuntimeError(
                    f"Error de conexión con Gamma local en {self.base_url}: {exc}"
                ) from exc

        if response is None:
            # Fallback transparente al motor embebido in-process (Zero-Setup Headless)
            client = self._get_embedded_client()
            response = client.request(method, path, **kwargs)

        is_ok = getattr(response, "ok", None)
        if is_ok is None:
            is_ok = 200 <= response.status_code < 400

        if not is_ok:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise RuntimeError(f"Gamma respondió HTTP {response.status_code}: {detail}")
        if response.status_code == 204:
            return None
        return response.json()


api = GammaApiClient()
mcp = MCPServer(
    "docstudio",
    version="1.0.0",
    instructions=(
        "DocStudio es la fuente local de verdad del proyecto técnico y académico. Lee get_project_context antes de escribir. "
        "Los artefactos y ejecuciones son evidencia de trabajo, pero no autorizan declarar criterios completos. "
        "Actualiza secciones en bloques acotados, conserva los criterion_id exactos y solicita auditoría al final. "
        "Nunca inventes capturas, ejecuciones, entregas ni referencias."
    ),
)

READ_ONLY = ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)
SAFE_WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)


@mcp.tool(annotations=READ_ONLY)
def list_projects() -> list[dict[str, Any]]:
    """Lista los proyectos locales de DocStudio para elegir un project_id real."""
    return api.request("GET", "/api/projects")


@mcp.tool(annotations=READ_ONLY)
def get_project_context(project_id: str) -> dict[str, Any]:
    """Obtiene pauta, criterios pendientes, fuentes, evidencias, artefactos y ejecuciones del proyecto."""
    return api.request("GET", f"/api/agent/projects/{project_id}/context")


@mcp.tool(annotations=SAFE_WRITE)
def create_project(
    title: str,
    subject: str = "General",
    student: str = "Autor",
    career: str = "",
    summary: str = "",
    pauta_text: str = "",
    deliverables: list[str] | None = None,
    criteria: list[CriterionDraft] | None = None,
) -> dict[str, Any]:
    """Crea un proyecto local sin llamar a Gemini; usa criterios extraídos previamente si están disponibles."""
    return api.request(
        "POST",
        "/api/projects/quick-create",
        json={
            "title": title,
            "subject": subject,
            "student": student,
            "career": career,
            "summary": summary,
            "pauta_text": pauta_text,
            "deliverables": deliverables or [],
            "criteria": [item.model_dump() for item in (criteria or [])],
        },
    )


@mcp.tool(annotations=SAFE_WRITE)
def update_outline(
    project_id: str,
    outline: list[OutlineCardDraft],
) -> dict[str, Any]:
    """Actualiza la estructura/esquema del documento con tarjetas que definen secciones, tipo y requisitos."""
    serialized = []
    for idx, card in enumerate(outline, start=1):
        data = card.model_dump()
        if not data.get("id"):
            data["id"] = f"sec_{idx}"
        serialized.append(data)
    return api.request(
        "PUT",
        f"/api/projects/{project_id}/outline",
        json={"outline": serialized},
    )


@mcp.tool(annotations=SAFE_WRITE)
def update_criteria(
    project_id: str,
    criteria: list[CriterionDraft],
) -> dict[str, Any]:
    """Actualiza o define los criterios e indicadores de la pauta/rúbrica del proyecto."""
    serialized = [item.model_dump() for item in criteria]
    return api.request(
        "PUT",
        f"/api/projects/{project_id}/criteria",
        json={"criteria": serialized},
    )



@mcp.tool(annotations=SAFE_WRITE)
def attach_source(
    project_id: str,
    file_path: str,
    kind: str = "study_material",
) -> dict[str, Any]:
    """Copia e indexa un archivo local (apunte, pauta, código o documentación) como fuente de estudio en FTS5."""
    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        raise RuntimeError(f"La fuente local no existe: {path}")
    with path.open("rb") as handle:
        return api.request(
            "POST",
            f"/api/agent/projects/{project_id}/sources",
            files={"file": (path.name, handle, "application/octet-stream")},
            data={"kind": kind},
        )


@mcp.tool(annotations=READ_ONLY)
def search_project_sources(project_id: str, query: str, limit: int = 8) -> dict[str, Any]:
    """Busca fragmentos textuales en las fuentes del proyecto usando el índice local FTS5."""
    bounded_limit = max(1, min(limit, 20))
    return api.request(
        "GET",
        f"/api/projects/{project_id}/search",
        params={"q": query, "limit": bounded_limit},
    )


@mcp.tool(annotations=SAFE_WRITE)
def remember_project_decision(
    project_id: str,
    content: str,
    kind: Literal["preference", "fact", "decision", "summary"] = "decision",
    importance: float = 0.7,
) -> dict[str, Any]:
    """Guarda una preferencia o decisión explícita; la memoria nunca reemplaza pauta, fuente ni evidencia."""
    return api.request(
        "POST",
        f"/api/projects/{project_id}/memories",
        json={"content": content, "kind": kind, "importance": max(0.0, min(importance, 1.0))},
    )


@mcp.tool(annotations=SAFE_WRITE)
def update_section(
    project_id: str,
    heading: str,
    content_html: str,
    reason: str = "agent:mcp",
    create_snapshot: bool = True,
) -> dict[str, Any]:
    """Actualiza una sola sección HTML y crea una versión por defecto; no reemplaza el documento completo."""
    return api.request(
        "PATCH",
        f"/api/projects/{project_id}/section",
        json={
            "heading": heading,
            "content_html": content_html,
            "reason": reason,
            "create_snapshot": create_snapshot,
        },
    )


@mcp.tool(annotations=SAFE_WRITE)
def attach_artifact(
    project_id: str,
    file_path: str,
    kind: str,
    criterion_id: str | None = None,
    description: str = "",
    source: str = "mcp-agent",
) -> dict[str, Any]:
    """Copia a Gamma un archivo local ya creado y lo vincula opcionalmente a un criterio exacto."""
    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        raise RuntimeError(f"El artefacto local no existe: {path}")
    with path.open("rb") as handle:
        return api.request(
            "POST",
            f"/api/agent/projects/{project_id}/artifacts",
            files={"file": (path.name, handle, "application/octet-stream")},
            data={
                "kind": kind,
                "criterion_id": criterion_id or "",
                "description": description,
                "source": source,
            },
        )


@mcp.tool(annotations=SAFE_WRITE)
def register_execution(
    project_id: str,
    agent: str,
    action: str,
    status: str,
    criterion_id: str | None = None,
    command: str = "",
    exit_code: int | None = None,
    stdout_excerpt: str = "",
    stderr_excerpt: str = "",
    artifact_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Registra el resultado real de una ejecución; status debe ser succeeded, failed o partial."""
    return api.request(
        "POST",
        f"/api/agent/projects/{project_id}/executions",
        json={
            "agent": agent,
            "action": action,
            "status": status,
            "criterion_id": criterion_id,
            "command": command,
            "exit_code": exit_code,
            "stdout_excerpt": stdout_excerpt,
            "stderr_excerpt": stderr_excerpt,
            "artifact_ids": artifact_ids or [],
        },
    )


@mcp.tool(annotations=SAFE_WRITE)
def request_audit(project_id: str, html_content: str, use_ai: bool = True) -> dict[str, Any]:
    """Audita el HTML contra la pauta; Gamma conserva el control final de estados y evidencias."""
    return api.request(
        "POST",
        f"/api/projects/{project_id}/audit",
        json={"html_content": html_content, "use_ai": use_ai},
    )


@mcp.tool(annotations=SAFE_WRITE)
def export_docx(project_id: str, output_path: str | None = None) -> dict[str, Any]:
    """Genera el informe Word oficial (.docx) del proyecto en disco y devuelve su ruta y metadatos."""
    return api.request(
        "POST",
        f"/api/agent/projects/{project_id}/export-docx",
        params={"output_path": output_path} if output_path else {},
    )


@mcp.tool(annotations=SAFE_WRITE)
def package_submission(project_id: str, include_sources: bool = True) -> dict[str, Any]:
    """Empaqueta la entrega final (.zip) con el informe Word, código, artefactos y evidencias."""
    return api.request(
        "POST",
        f"/api/agent/projects/{project_id}/package-submission",
        params={"include_sources": include_sources},
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
