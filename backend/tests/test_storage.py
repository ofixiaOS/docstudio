from pathlib import Path

from app.storage import Store


def test_project_memory_versions_and_search(tmp_path: Path) -> None:
    store = Store(tmp_path / "test.db")
    project_id = store.create_project(
        title="Evaluación de prueba",
        subject="Bases de datos",
        student="Nicolás",
        career="Informática",
        summary="Normalización",
        rubric_text="Aplicar tercera forma normal",
        deliverables=["Word con capturas", "archivo DMD"],
        outline=[{"id": "intro", "title": "Introducción", "description": "Contexto", "type": "intro"}],
    )
    criteria = store.add_criteria(project_id, [{
        "criterion": "Normalización",
        "indicator": "Aplica tercera forma normal",
        "points": 30,
        "requires_evidence": True,
    }])
    assert criteria[0]["status"] == "pending"

    source_path = tmp_path / "material.txt"
    source_path.write_text("La tercera forma normal elimina dependencias transitivas.", encoding="utf-8")
    store.add_source(project_id, source_path, source_path.name, "study_material", source_path.read_text(encoding="utf-8"))
    results = store.search_sources(project_id, "dependencias transitivas")
    assert results and results[0]["filename"] == "material.txt"

    store.add_memory(project_id, "preference", "Usar explicaciones breves", 0.9)
    assert store.search_memories(project_id, "explicaciones breves")[0]["kind"] == "preference"

    store.update_document(project_id, "<p>Borrador</p>")
    assert store.create_snapshot(project_id, "<p>Versión 1</p>", "manual") == 1
    project = store.get_project(project_id)
    assert project is not None
    assert project["document_html"] == "<p>Versión 1</p>"
    assert project["deliverables"] == ["Word con capturas", "archivo DMD"]
