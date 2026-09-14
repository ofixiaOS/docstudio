from io import BytesIO

from docx import Document
from fastapi.testclient import TestClient

from main import app, parse_html_to_sections


client = TestClient(app)


def test_health_and_config_do_not_disclose_key() -> None:
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    config = client.get("/api/config").json()
    assert "gemini_api_key" not in config
    assert "api_key_masked" in config


def test_html_parser_preserves_blocks_and_images() -> None:
    blocks = parse_html_to_sections(
        '<h1>Desarrollo</h1><p>Texto <strong>importante</strong>.</p>'
        '<ol><li>Paso uno</li><li>Paso dos</li></ol><img src="missing.png" alt="captura" />'
    )
    assert [block["type"] for block in blocks] == ["h1", "paragraph", "ordered_item", "ordered_item", "image"]
    assert "<strong>" in blocks[1]["content_html"]


def test_export_docx() -> None:
    response = client.post("/api/export-docx", json={
        "title": "Prueba de exportación",
        "subject": "Programación",
        "student": "Nicolás",
        "html_content": "<h1>Introducción</h1><p>Texto con <strong>formato</strong>.</p>",
    })
    assert response.status_code == 200
    assert response.content.startswith(b"PK")
    document = Document(BytesIO(response.content))
    paragraphs = document.paragraphs
    title = next(paragraph for paragraph in paragraphs if paragraph.text == "Prueba de exportación")
    assert title.style.name == "Title"
    introduction = next(paragraph for paragraph in paragraphs if paragraph.text == "Introducción")
    assert introduction.style.name == "Heading 1"
    formatted = next(paragraph for paragraph in paragraphs if paragraph.text == "Texto con formato.")
    assert any(run.text == "formato" and run.bold for run in formatted.runs)
