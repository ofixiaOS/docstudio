"""Prompt templates and default outline for document generation."""

from __future__ import annotations

from typing import Any

from .settings import settings


def default_outline() -> list[dict]:
    """Return the fallback outline used when no AI analysis is available."""
    return [
        {"id": "sec-intro", "title": "Introducción", "description": "Contexto y objetivos", "type": "intro", "needs_code": False, "needs_evidence": False},
        {"id": "sec-dev", "title": "Desarrollo Técnico", "description": "Ejecución y evidencia", "type": "development", "needs_code": True, "needs_evidence": True},
        {"id": "sec-conc", "title": "Conclusión", "description": "Síntesis de aprendizajes", "type": "conclusion", "needs_code": False, "needs_evidence": False},
        {"id": "sec-bib", "title": "Bibliografía", "description": "Fuentes consultadas", "type": "references", "needs_code": False, "needs_evidence": False},
    ]


def section_prompt(
    request: Any,
    card: dict,
    rubric_context: str,
    source_context: str,
    memory_context: str = "",
) -> str:
    """Build the LLM prompt for generating a single document section."""
    institution = settings.default_institution or "educación superior técnica y universitaria"
    title = getattr(request, "title", str(request))
    subject = getattr(request, "subject", "General")
    return f"""
Redacta solamente una sección de un trabajo académico y técnico para {institution}.

TRABAJO: {title}
ASIGNATURA: {subject}
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
