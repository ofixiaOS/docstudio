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


def test_html_parser_preserves_images_nested_in_paragraphs() -> None:
    # Regression test for H-02: images inside <p> were silently dropped
    html = '<p>Nota previa: <img src="/api/evidence/test/content" alt="Captura Red Hat" /></p>'
    blocks = parse_html_to_sections(html)
    assert len(blocks) == 2
    assert blocks[0]["type"] == "paragraph"
    assert "Nota previa:" in blocks[0]["content"]
    assert blocks[1]["type"] == "image"
    assert blocks[1]["image_path"] == "/api/evidence/test/content"
    assert blocks[1]["image_alt"] == "Captura Red Hat"


def test_html_parser_handles_standalone_paragraph_image() -> None:
    html = '<p><img src="test.png" alt="Diagrama" /></p>'
    blocks = parse_html_to_sections(html)
    assert len(blocks) == 1
    assert blocks[0]["type"] == "image"
    assert blocks[0]["image_path"] == "test.png"


def test_version_endpoints() -> None:
    from main import store
    project_id = store.create_project(
        title="Test Version API", subject="Sistemas", student="Nicolas", career="Info",
        summary="Test", rubric_text="Test", deliverables=[], outline=[]
    )
    # Create snapshots
    snap1 = client.post(f"/api/projects/{project_id}/snapshots", json={"html_content": "<p>V1</p>", "reason": "manual"})
    assert snap1.status_code == 200
    assert snap1.json()["version"] == 1

    snap2 = client.post(f"/api/projects/{project_id}/snapshots", json={"html_content": "<p>V2</p>", "reason": "manual"})
    assert snap2.status_code == 200
    assert snap2.json()["version"] == 2

    # List versions
    v_list = client.get(f"/api/projects/{project_id}/versions")
    assert v_list.status_code == 200
    assert len(v_list.json()) >= 2
    assert v_list.json()[0]["version_number"] == 2

    # Restore version 1
    restore_resp = client.post(f"/api/projects/{project_id}/versions/1/restore")
    assert restore_resp.status_code == 200
    data = restore_resp.json()
    assert data["restored_from"] == 1
    assert "<p>V1</p>" in data["html_content"]


def test_quick_create_and_patch_section() -> None:
    # 1. Quick create without calling Gemini
    create_resp = client.post("/api/projects/quick-create", json={
        "title": "Proyecto Red Hat Offline",
        "subject": "Sistemas Operativos",
        "student": "Nicolás Jara",
        "pauta_text": "Instalar VSFTPD y MariaDB en Red Hat",
        "deliverables": ["Informe Word con capturas"],
        "criteria": [
            {
                "criterion": "Servicios",
                "indicator": "Configura VSFTPD y MariaDB",
                "points": 30.0,
                "requires_evidence": True,
            }
        ]
    })
    assert create_resp.status_code == 200
    pid = create_resp.json()["project_id"]
    assert pid.startswith("prj_")

    # 2. Patch a specific section
    patch_resp = client.patch(f"/api/projects/{pid}/section", json={
        "heading": "Desarrollo Técnico",
        "content_html": "<p>Se ejecutó el comando <code>systemctl start vsftpd</code> con éxito.</p>",
        "create_snapshot": True,
        "reason": "agent:add_vsftpd"
    })
    assert patch_resp.status_code == 200
    doc_html = patch_resp.json()["html_content"]
    assert "Desarrollo Técnico" in doc_html
    assert "systemctl start vsftpd" in doc_html

    # 3. Update existing section without overwriting other sections
    patch_resp2 = client.patch(f"/api/projects/{pid}/section", json={
        "heading": "Conclusión",
        "content_html": "<p>Se cumplieron todos los objetivos.</p>",
        "create_snapshot": True
    })
    assert patch_resp2.status_code == 200
    doc2_html = patch_resp2.json()["html_content"]
    assert "systemctl start vsftpd" in doc2_html
    assert "Conclusión" in doc2_html
    assert "Se cumplieron todos los objetivos." in doc2_html


