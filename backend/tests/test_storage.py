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

    mem1 = store.add_memory(project_id, "preference", "Usar explicaciones breves", 0.7)
    assert store.search_memories(project_id, "explicaciones breves")[0]["kind"] == "preference"

    # Test deduplication: same content updates importance instead of inserting a duplicate
    mem2 = store.add_memory(project_id, "preference", "Usar explicaciones breves", 0.9)
    assert mem1["id"] == mem2["id"]
    assert mem2["importance"] == 0.9
    all_mems = store.list_memories(project_id)
    assert len(all_mems) == 1

    # Test deletion
    assert store.delete_memory(mem1["id"]) is True
    assert len(store.list_memories(project_id)) == 0

    store.update_document(project_id, "<p>Borrador</p>")
    assert store.create_snapshot(project_id, "<p>Versión 1</p>", "manual") == 1
    assert store.create_snapshot(project_id, "<p>Versión 2 modificada</p>", "manual") == 2
    versions = store.list_versions(project_id)
    assert len(versions) == 2
    assert versions[0]["version_number"] == 2
    assert versions[1]["version_number"] == 1

    store.update_document(project_id, "<p>Trabajo actual</p>")
    restored = store.restore_version(project_id, 1)
    assert restored["version_number"] == 3
    assert restored["restored_from"] == 1
    assert "<p>Versión 1</p>" in restored["html_content"]
    backup = store.get_version(project_id, 3)
    assert backup is not None
    assert backup["reason"] == "before_restore_v1"
    assert backup["html_content"] == "<p>Trabajo actual</p>"

    project = store.get_project(project_id)
    assert project is not None
    assert project["document_html"] == "<p>Versión 1</p>"
    assert project["deliverables"] == ["Word con capturas", "archivo DMD"]


def test_delete_project_cascade_and_disk_cleanup(tmp_path: Path) -> None:
    store = Store(tmp_path / "test_del.db")
    project_id = store.create_project(
        title="Para borrar",
        subject="Testing",
        student="Autor",
        career="",
        summary="",
        rubric_text="",
        deliverables=[],
        outline=[],
    )
    # create fake project directory on disk
    project_dir = tmp_path / "projects" / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "dummy.txt").write_text("hello", encoding="utf-8")
    assert project_dir.exists()

    assert store.delete_project(project_id) is True
    assert store.get_project(project_id) is None
    assert not project_dir.exists()
    assert store.delete_project(project_id) is False


def test_delete_source_and_evidence(tmp_path: Path) -> None:
    store = Store(tmp_path / "test_se.db")
    project_id = store.create_project(
        title="Test SE",
        subject="Testing",
        student="Autor",
        career="",
        summary="",
        rubric_text="",
        deliverables=[],
        outline=[],
    )
    # 1. Internal project file: should be deleted from disk
    project_sources = tmp_path / "projects" / project_id / "sources"
    project_sources.mkdir(parents=True, exist_ok=True)
    internal_src_file = project_sources / "internal.txt"
    internal_src_file.write_text("contenido interno", encoding="utf-8")
    src = store.add_source(project_id, internal_src_file, "internal.txt", "study_material", "contenido interno")
    assert store.delete_source(project_id, src["id"]) is True
    assert not internal_src_file.exists()

    # 2. External file (e.g. user library): database record deleted, but disk file protected
    external_file = tmp_path / "library" / "external_book.pdf"
    external_file.parent.mkdir(parents=True, exist_ok=True)
    external_file.write_text("contenido externo que no se debe borrar", encoding="utf-8")
    ext_src = store.add_source(project_id, external_file, "external_book.pdf", "study_material", "contenido externo")
    assert store.delete_source(project_id, ext_src["id"]) is True
    assert external_file.exists()  # Crucial safety check: must NOT delete external user files!

    ev_dir = tmp_path / "projects" / project_id / "evidence"
    ev_dir.mkdir(parents=True, exist_ok=True)
    ev_file = ev_dir / "ev.png"
    ev_file.write_text("fake image", encoding="utf-8")
    ev = store.add_evidence(project_id, ev_file, "ev.png", "captura", None)
    assert store.delete_evidence(project_id, ev["id"]) is True
    assert not ev_file.exists()


def test_add_evidence_normalizes_empty_and_whitespace_criterion_id(tmp_path: Path) -> None:
    store = Store(tmp_path / "test_norm_crit.db")
    project_id = store.create_project(
        title="Test Normalización Criterio",
        subject="Testing",
        student="Autor",
        career="",
        summary="",
        rubric_text="",
        deliverables=[],
        outline=[],
    )
    ev_file1 = tmp_path / "ev1.png"
    ev_file1.write_bytes(b"fake1")
    # Empty string should normalize to None and not raise sqlite3.IntegrityError
    item1 = store.add_evidence(project_id, ev_file1, "ev1.png", "captura 1", "")
    assert item1["criterion_id"] is None
    fetched1 = store.get_evidence(item1["id"])
    assert fetched1 is not None
    assert fetched1["criterion_id"] is None

    ev_file2 = tmp_path / "ev2.png"
    ev_file2.write_bytes(b"fake2")
    # Whitespace string should normalize to None
    item2 = store.add_evidence(project_id, ev_file2, "ev2.png", "captura 2", "   ")
    assert item2["criterion_id"] is None
    fetched2 = store.get_evidence(item2["id"])
    assert fetched2 is not None
    assert fetched2["criterion_id"] is None


def test_extract_text_xlsx(tmp_path: Path) -> None:
    import openpyxl
    from app.documents import extract_text

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Balance"
    ws.append(["Cuenta", "Debe", "Haber"])
    ws.append(["Caja", 150000, 0])
    ws.append(["Proveedores", 0, 150000])
    xlsx_path = tmp_path / "balance.xlsx"
    wb.save(str(xlsx_path))
    wb.close()

    text = extract_text(xlsx_path)
    assert "[Hoja: Balance]" in text
    assert "Cuenta | Debe | Haber" in text
    assert "Caja | 150000 | 0" in text
