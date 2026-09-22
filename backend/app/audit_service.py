"""Offline and AI-grounded audit of document coverage against rubric criteria."""

from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup

from .models import AuditItem, AuditResult


def valid_evidence_by_criterion(project: dict) -> dict[str, list[dict]]:
    """Group verified evidence files, agent artifacts, and successful execution records keyed by criterion_id."""
    grouped: dict[str, list[dict]] = {}
    criterion_ids = {item["id"] for item in project.get("criteria", [])}

    # 1. Evidence files physically present on disk
    for evidence in project.get("evidence", []):
        criterion_id = evidence.get("criterion_id")
        stored_path = evidence.get("stored_path")
        if criterion_id in criterion_ids and stored_path and Path(stored_path).is_file():
            grouped.setdefault(criterion_id, []).append({
                "type": "evidence_file",
                "id": evidence.get("id"),
                "filename": evidence.get("filename"),
                "stored_path": stored_path,
                "caption": evidence.get("caption", ""),
            })

    # 2. Agent artifacts physically present on disk and not rejected
    for artifact in project.get("artifacts", []):
        criterion_id = artifact.get("criterion_id")
        stored_path = artifact.get("stored_path")
        if (
            criterion_id in criterion_ids
            and artifact.get("validation_status") != "rejected"
            and stored_path
            and Path(stored_path).is_file()
        ):
            grouped.setdefault(criterion_id, []).append({
                "type": "artifact",
                "id": artifact.get("id"),
                "filename": artifact.get("filename"),
                "kind": artifact.get("kind"),
                "stored_path": stored_path,
                "description": artifact.get("description", ""),
            })

    # 3. Successful execution records (e.g., passing tests, scripts, database queries)
    for execution in project.get("executions", []):
        criterion_id = execution.get("criterion_id")
        if criterion_id in criterion_ids and execution.get("status") == "succeeded":
            grouped.setdefault(criterion_id, []).append({
                "type": "execution",
                "id": execution.get("id"),
                "agent": execution.get("agent"),
                "action": execution.get("action"),
                "command": execution.get("command"),
                "exit_code": execution.get("exit_code"),
            })

    return grouped


def audit_score(project: dict, items: list[AuditItem]) -> float:
    """Compute the estimated coverage score (0–100) from audit items."""
    status_weight = {"complete": 1.0, "partial": 0.5, "missing": 0.0}
    by_id = {item.criterion_id: item for item in items}
    possible = sum(float(criterion.get("points") or 0) for criterion in project["criteria"])
    if possible:
        earned = sum(
            float(criterion.get("points") or 0) * status_weight[by_id[criterion["id"]].status]
            for criterion in project["criteria"] if criterion["id"] in by_id
        )
        return earned / possible * 100
    return sum(status_weight[item.status] for item in items) / max(len(items), 1) * 100


def enforce_evidence_grounding(project: dict, result: AuditResult, fallback: AuditResult) -> AuditResult:
    """Override AI audit results with filesystem-verified evidence truth."""
    evidence_by_criterion = valid_evidence_by_criterion(project)
    result_by_id = {item.criterion_id: item for item in result.items}
    fallback_by_id = {item.criterion_id: item for item in fallback.items}
    grounded_items: list[AuditItem] = []
    for criterion in project["criteria"]:
        criterion_id = criterion["id"]
        item = result_by_id.get(criterion_id) or fallback_by_id[criterion_id]
        evidence_found = bool(evidence_by_criterion.get(criterion_id))
        status = item.status
        feedback = item.feedback.strip()
        if criterion["requires_evidence"]:
            if evidence_found:
                items_for_crit = evidence_by_criterion.get(criterion_id, [])
                kinds = {i.get("type") for i in items_for_crit}
                tag_parts = []
                if "evidence_file" in kinds:
                    tag_parts.append("Evidencia gráfica vinculada")
                if "artifact" in kinds:
                    tag_parts.append("Artefacto técnico vinculado")
                if "execution" in kinds:
                    tag_parts.append("Ejecución técnica verificada")
                tag_str = "; ".join(tag_parts) if tag_parts else "Evidencia vinculada"
                feedback = f"{feedback} [{tag_str}]".strip()
            else:
                if status == "complete":
                    status = "partial"
                feedback = f"{feedback} [Pendiente de adjuntar captura]".strip()
        grounded_items.append(AuditItem(
            criterion_id=criterion_id,
            status=status,
            evidence_found=evidence_found,
            feedback=feedback,
        ))
    return AuditResult(
        summary=result.summary or "Revisión de cobertura completada.",
        estimated_score=audit_score(project, grounded_items),
        items=grounded_items,
    )


def offline_audit(project: dict, html_content: str) -> AuditResult:
    """Compute a keyword-based audit without calling any AI model."""
    text = BeautifulSoup(html_content, "html.parser").get_text(" ", strip=True).lower()
    evidence_by_criterion = valid_evidence_by_criterion(project)
    items = []
    for criterion in project["criteria"]:
        words = {word for word in re.findall(r"\w+", criterion["indicator"].lower()) if len(word) > 4}
        ratio = sum(1 for word in words if word in text) / max(len(words), 1)
        evidence_found = bool(evidence_by_criterion.get(criterion["id"]))
        status = "complete" if ratio >= 0.35 else "partial" if ratio >= 0.15 else "missing"
        if criterion["requires_evidence"] and not evidence_found and status == "complete":
            status = "partial"
        if criterion["requires_evidence"] and evidence_found:
            feedback = "Tema abordado y evidencia técnica/gráfica vinculada."
        elif criterion["requires_evidence"]:
            feedback = "Tema mencionado en el texto. Puedes adjuntar una captura o artefacto cuando corresponda."
        elif status == "complete":
            feedback = "El tema o requerimiento se encuentra desarrollado en el documento."
        else:
            feedback = "Tema pendiente de desarrollar con mayor detalle."
        items.append(AuditItem(criterion_id=criterion["id"], status=status,
                               evidence_found=evidence_found, feedback=feedback))
    return AuditResult(summary="Revisión de cobertura de temas y requerimientos.",
                       estimated_score=audit_score(project, items), items=items)
