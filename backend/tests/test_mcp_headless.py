from __future__ import annotations

import asyncio
import os
from pathlib import Path

from mcp import Client

from scripts import gamma_mcp


def test_mcp_headless_zero_setup_execution(tmp_path: Path, monkeypatch) -> None:
    """Verifica que un cliente MCP pueda interactuar completamente con DocStudio en modo headless,

    sin que exista ningún servidor HTTP o proceso Uvicorn corriendo previamente.
    """
    # Configuramos un puerto inexistente para garantizar que no haya HTTP disponible
    monkeypatch.setenv("GAMMA_API_URL", "http://127.0.0.1:59999")
    monkeypatch.setenv("GEMINI_API_KEY", "")
    # Reiniciar el cliente embebido para asegurar aislamiento
    gamma_mcp.api._embedded_client = None

    # Archivo temporal para prueba de fuente de estudio
    sample_source = tmp_path / "manual_estudio.txt"
    sample_source.write_text("Metodología de desarrollo ágil con TDD y arquitectura hexagonal.", encoding="utf-8")

    # Archivo temporal para prueba de artefacto de evidencia
    sample_artifact = tmp_path / "diagrama.png"
    sample_artifact.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")

    async def exercise_headless() -> None:
        async with Client(gamma_mcp.mcp) as client:
            # 1. Listar proyectos en frío
            projects_res = await client.call_tool("list_projects", {})
            assert isinstance(projects_res.structured_content.get("result"), list)

            # 2. Crear proyecto
            created = await client.call_tool("create_project", {
                "title": "Proyecto Headless Zero-Setup",
                "subject": "Ingeniería de Software",
                "student": "Estudiante Test",
                "career": "Ingeniería en Informática",
                "criteria": [
                    {
                        "criterion": "Diseño de Arquitectura",
                        "indicator": "El documento incluye diagrama y justificación.",
                        "points": 10.0,
                        "requires_evidence": True,
                    }
                ],
            })
            project_id = created.structured_content["project_id"]
            criterion_id = created.structured_content["criteria"][0]["id"]
            assert project_id.startswith("prj_")

            try:
                # 3. Adjuntar fuente de estudio e indexar en FTS5
                src_res = await client.call_tool("attach_source", {
                    "project_id": project_id,
                    "file_path": str(sample_source),
                    "kind": "study_material",
                })
                assert src_res.structured_content["filename"] == "manual_estudio.txt"

                # 4. Búsqueda léxica FTS5 en la fuente recién adjuntada
                search_res = await client.call_tool("search_project_sources", {
                    "project_id": project_id,
                    "query": "arquitectura hexagonal",
                })
                results = search_res.structured_content.get("results", [])
                assert len(results) >= 1
                assert "hexagonal" in results[0]["content"].lower()

                # 5. Definir esquema / outline del documento
                outline_res = await client.call_tool("update_outline", {
                    "project_id": project_id,
                    "outline": [
                        {"title": "Introducción", "description": "Contexto general del sistema", "type": "intro"},
                        {"title": "Arquitectura", "description": "Diagramas y patrones", "type": "development", "needs_evidence": True},
                    ],
                })
                assert outline_res.structured_content["status"] == "saved"

                # 6. Actualizar sección técnica
                sec_res = await client.call_tool("update_section", {
                    "project_id": project_id,
                    "heading": "Arquitectura",
                    "content_html": "<p>Implementación basada en arquitectura hexagonal.</p>",
                })
                assert sec_res.structured_content["status"] == "updated"
                assert sec_res.structured_content["version"] >= 1

                # 7. Adjuntar artefacto como evidencia vinculada al criterio
                art_res = await client.call_tool("attach_artifact", {
                    "project_id": project_id,
                    "file_path": str(sample_artifact),
                    "kind": "image",
                    "criterion_id": criterion_id,
                    "description": "Diagrama de componentes del sistema",
                })
                artifact_id = art_res.structured_content["id"]
                assert artifact_id.startswith("art_")

                # 8. Registrar ejecución exitosa
                exec_res = await client.call_tool("register_execution", {
                    "project_id": project_id,
                    "agent": "headless-test-agent",
                    "action": "pytest tests/ -v",
                    "status": "succeeded",
                    "criterion_id": criterion_id,
                    "exit_code": 0,
                    "stdout_excerpt": "10 passed in 1.2s",
                    "artifact_ids": [artifact_id],
                })
                assert exec_res.structured_content["status"] == "succeeded"

                # 8b. Actualizar / redefinir criterios vía MCP
                crit_res = await client.call_tool("update_criteria", {
                    "project_id": project_id,
                    "criteria": [
                        {
                            "id": criterion_id,
                            "criterion": "Diseño de Arquitectura Hexagonal",
                            "indicator": "El documento incluye diagrama de componentes y justificación técnica.",
                            "points": 15.0,
                            "requires_evidence": True,
                        },
                        {
                            "criterion": "Pruebas Automatizadas",
                            "indicator": "Cobertura con tests unitarios.",
                            "points": 10.0,
                            "requires_evidence": False,
                        },
                    ],
                })
                assert crit_res.structured_content["status"] == "saved"
                assert len(crit_res.structured_content["criteria"]) == 2

                # 9. Consultar contexto completo del proyecto
                ctx_res = await client.call_tool("get_project_context", {"project_id": project_id})
                assert ctx_res.structured_content["project"]["id"] == project_id
                assert len(ctx_res.structured_content["project"]["criteria"]) == 2
                assert len(ctx_res.structured_content["artifacts"]) >= 1
                assert len(ctx_res.structured_content["recent_executions"]) >= 1


                # 10. Solicitar auditoría contra la pauta
                audit_res = await client.call_tool("request_audit", {
                    "project_id": project_id,
                    "html_content": "<p>Se describe la arquitectura con evidencia verificada.</p>",
                    "use_ai": False,
                })
                assert "items" in audit_res.structured_content

                # 11. Exportar documento oficial Word (.docx)
                docx_res = await client.call_tool("export_docx", {"project_id": project_id})
                assert docx_res.structured_content["status"] == "ok"
                docx_file = Path(docx_res.structured_content["file_path"])
                assert docx_file.is_file()
                assert docx_file.stat().st_size > 0

                # 12. Empaquetar entrega final (.zip) con manifiesto SHA-256
                pkg_res = await client.call_tool("package_submission", {
                    "project_id": project_id,
                    "include_sources": True,
                })
                assert pkg_res.structured_content["status"] == "ok"
                zip_file = Path(pkg_res.structured_content["zip_path"])
                assert zip_file.is_file()
                assert zip_file.stat().st_size > 0

            finally:
                # Limpieza higiénica del proyecto de prueba
                from main import store
                store.delete_project(project_id)

    asyncio.run(exercise_headless())
