from __future__ import annotations

import hashlib
import re
import zipfile
from datetime import datetime
from pathlib import Path

from app.documents import sha256_file
from app.settings import settings
from app.storage import Store


def build_submission_manifest(project: dict, artifacts: list[dict], evidence: list[dict], sources: list[dict]) -> str:
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    title = project.get("title") or "Trabajo Académico"
    subject = project.get("subject") or "General"
    student = project.get("student") or settings.default_author or "Autor"
    career = project.get("career") or settings.default_career or ""
    institution = project.get("institution") or settings.default_institution or "Educación Superior"
    deliverables = project.get("deliverables") or []
    criteria = project.get("criteria") or []

    lines = [
        "=" * 70,
        f"PAQUETE DE ENTREGA ACADÉMICA - {title.upper()}",
        "=" * 70,
        f"Institución:   {institution}",
        f"Asignatura:    {subject}",
        f"Carrera:       {career}",
        f"Estudiante:    {student}",
        f"Fecha empaque: {now_str}",
        "",
        "-" * 70,
        "ENTREGABLES DECLARADOS EN LA PAUTA:",
        "-" * 70,
    ]
    if deliverables:
        for d in deliverables:
            lines.append(f"  [x] {d}")
    else:
        lines.append("  (Sin entregables desglosados en la pauta)")

    lines.extend([
        "",
        "-" * 70,
        "CRITERIOS DE EVALUACIÓN Y COBERTURA:",
        "-" * 70,
    ])
    if criteria:
        for c in criteria:
            status = c.get("status") or "pending"
            pts = f"{c.get('points')} pts" if c.get("points") is not None else "sugerido"
            lines.append(f"  - [{status.upper()}] {c.get('indicator')} ({pts})")
    else:
        lines.append("  (Sin criterios cargados)")

    lines.extend([
        "",
        "-" * 70,
        "CONTENIDO DE ESTE PAQUETE (.ZIP):",
        "-" * 70,
        "  1. Informe/: Documento Word con el desarrollo, portada y figuras.",
        f"  2. Artefactos_y_Codigo/: {len(artifacts)} artefacto(s) técnico(s) de soporte.",
        f"  3. Evidencias/: {len(evidence)} captura(s) de pantalla y pruebas de ejecución.",
        "  4. checksums.sha256: Manifiesto criptográfico de integridad de cada archivo.",
        "",
        "Generado automáticamente por DocStudio (Workspace local-first).",
        "=" * 70,
    ])
    return "\n".join(lines)


def package_project_submission(
    project_id: str,
    store: Store,
    docx_path: Path | None = None,
    include_sources: bool = True,
) -> tuple[Path, str]:
    project = store.get_project(project_id)
    if not project:
        raise ValueError(f"Proyecto {project_id} no encontrado.")

    title = project.get("title") or "Entrega"
    filename_stem = re.sub(r'[\\/*?:"<>|]', "", title)[:50].strip() or "Entrega"
    zip_filename = f"{filename_stem}_Entrega_Final.zip"

    export_dir = settings.projects_dir / project_id / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    zip_path = export_dir / zip_filename

    artifacts = store.list_artifacts(project_id)
    evidence = store.list_evidence(project_id)
    sources = project.get("sources") or []

    manifest_text = build_submission_manifest(project, artifacts, evidence, sources)
    checksum_entries: list[tuple[str, str]] = []

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Manifest
        zf.writestr("LEEME_ENTREGA.txt", manifest_text)
        manifest_digest = hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()
        checksum_entries.append((manifest_digest, "LEEME_ENTREGA.txt"))

        # 2. Informe Word
        if docx_path and docx_path.is_file():
            arc = f"Informe/{docx_path.name}"
            zf.write(docx_path, arcname=arc)
            checksum_entries.append((sha256_file(docx_path), arc))

        # 3. Artefactos y Código
        seen_artifact_names: set[str] = set()
        for art in artifacts:
            stored_path = Path(art.get("stored_path") or "")
            if stored_path.is_file():
                base_name = art.get("filename") or stored_path.name
                if base_name in seen_artifact_names:
                    base_name = f"{stored_path.stem}_{art['id'][:4]}{stored_path.suffix}"
                seen_artifact_names.add(base_name)
                arc = f"Artefactos_y_Codigo/{base_name}"
                zf.write(stored_path, arcname=arc)
                checksum_entries.append((sha256_file(stored_path), arc))

        # If include_sources, also include code/data sources from sources folder
        if include_sources:
            code_extensions = {".sql", ".dmd", ".java", ".py", ".sh", ".cs", ".xml", ".json", ".zip", ".rar", ".7z"}
            for src in sources:
                src_path = Path(src.get("stored_path") or src.get("path") or "")
                filename = src.get("filename") or src_path.name
                suffix = Path(filename).suffix.lower() or src_path.suffix.lower()
                if src_path.is_file() and suffix in code_extensions:
                    base_name = filename
                    if base_name in seen_artifact_names:
                        base_name = f"{Path(filename).stem}_{src['id'][:4]}{suffix}"
                    seen_artifact_names.add(base_name)
                    arc = f"Artefactos_y_Codigo/{base_name}"
                    zf.write(src_path, arcname=arc)
                    checksum_entries.append((sha256_file(src_path), arc))

        # 4. Evidencias
        seen_evidence_names: set[str] = set()
        for ev in evidence:
            stored_path = Path(ev.get("stored_path") or "")
            if stored_path.is_file():
                base_name = ev.get("filename") or stored_path.name
                if base_name in seen_evidence_names:
                    base_name = f"{stored_path.stem}_{ev['id'][:4]}{stored_path.suffix}"
                seen_evidence_names.add(base_name)
                arc = f"Evidencias/{base_name}"
                zf.write(stored_path, arcname=arc)
                checksum_entries.append((sha256_file(stored_path), arc))

        # 5. Checksums cryptographic manifest
        checksum_text = "\n".join(f"{digest}  {arcname}" for digest, arcname in checksum_entries) + "\n"
        zf.writestr("checksums.sha256", checksum_text)

    return zip_path, zip_filename
