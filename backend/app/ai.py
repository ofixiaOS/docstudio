from __future__ import annotations

from fastapi import HTTPException
from google import genai
from google.genai import types
from pydantic import BaseModel

from .models import AuditResult, ChatResult, RubricAnalysis
from .settings import get_gemini_api_key, settings


class GeminiService:
    def client(self) -> genai.Client:
        key = get_gemini_api_key()
        if not key:
            raise HTTPException(
                status_code=400,
                detail="Falta configurar GEMINI_API_KEY. Puedes hacerlo desde Configuración.",
            )
        return genai.Client(api_key=key)

    def structured(self, prompt: str, schema: type[BaseModel], *, temperature: float = 0.2) -> BaseModel:
        response = self.client().models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=schema,
                temperature=temperature,
            ),
        )
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, schema):
            return parsed
        if parsed is not None:
            return schema.model_validate(parsed)
        return schema.model_validate_json(response.text)

    def text(self, prompt: str, *, temperature: float = 0.3, max_output_tokens: int = 6000) -> str:
        response = self.client().models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_output_tokens,
            ),
        )
        return (response.text or "").strip()

    def analyze_rubric(self, text: str, subject_hint: str = "") -> RubricAnalysis:
        prompt = f"""
Actúa como analista de requisitos académicos de Iplacex. Convierte la pauta en datos verificables.
No inventes requisitos ni puntajes. Distingue claramente el documento de respaldo de otros entregables
(proyecto, ZIP/RAR, DMD, repositorio, enlace, TXT, PDF). Cada captura o evidencia obligatoria debe quedar
marcada. Conserva la granularidad de los indicadores de logro de la tabla de evaluación.

Asignatura indicada por el usuario: {subject_hint or 'no indicada'}

PAUTA ENTRE MARCADORES:
<PAUTA>
{text[:settings.max_source_chars]}
</PAUTA>

El esquema debe incluir introducción, una sección por actividad o conjunto coherente de criterios,
conclusión y bibliografía. criterion_indexes usa índices base cero de la lista criteria.
"""
        return self.structured(prompt, RubricAnalysis, temperature=0.1)  # type: ignore[return-value]

    def chat(self, prompt: str) -> ChatResult:
        return self.structured(prompt, ChatResult, temperature=0.25)  # type: ignore[return-value]

    def audit(self, prompt: str) -> AuditResult:
        return self.structured(prompt, AuditResult, temperature=0.1)  # type: ignore[return-value]

    def embed_documents(self, texts: list[str], titles: list[str] | None = None) -> list[list[float]]:
        if not texts:
            return []
        titles = titles or ["sin título"] * len(texts)
        contents = [
            types.Content(parts=[types.Part(text=f"title: {title} | text: {text}")])
            for text, title in zip(texts, titles)
        ]
        response = self.client().models.embed_content(
            model=settings.embedding_model,
            contents=contents,
            config=types.EmbedContentConfig(output_dimensionality=settings.embedding_dimensions),
        )
        return [list(item.values or []) for item in (response.embeddings or [])]

    def embed_query(self, text: str) -> list[float]:
        prepared = f"task: question answering | query: {text}"
        response = self.client().models.embed_content(
            model=settings.embedding_model,
            contents=prepared,
            config=types.EmbedContentConfig(output_dimensionality=settings.embedding_dimensions),
        )
        if not response.embeddings:
            return []
        return list(response.embeddings[0].values or [])


ai = GeminiService()
