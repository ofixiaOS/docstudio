#!/usr/bin/env python
"""
Command-line utility for managing Iplacex projects directly.
Usage:
    python scripts/project_cli.py list
    python scripts/project_cli.py show <project_id>
    python scripts/project_cli.py export <project_id> [output_path]
    python scripts/project_cli.py search <project_id> <query>
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.settings import settings
from app.storage import Store
from docx_exporter import create_iplacex_document
from main import parse_html_to_sections, resolve_image_path


def get_store() -> Store:
    return Store(settings.database_path)


def cmd_list(args: argparse.Namespace) -> None:
    store = get_store()
    projects = store.list_projects()
    if not projects:
        print("No hay proyectos en la base de datos.")
        return
    print(f"\n{'ID':<36} | {'ASIGNATURA':<25} | {'TÍTULO':<35} | {'TAMAÑO DOC'}")
    print("-" * 115)
    for p in projects:
        size_kb = (p.get("document_size") or 0) / 1024
        print(f"{p['id']:<36} | {(p.get('subject') or 'General')[:25]:<25} | {p['title'][:35]:<35} | {size_kb:.1f} KB")
    print(f"\nTotal: {len(projects)} proyectos.\n")


def cmd_show(args: argparse.Namespace) -> None:
    store = get_store()
    project = store.get_project(args.project_id)
    if not project:
        print(f"Error: Proyecto '{args.project_id}' no encontrado.")
        sys.exit(1)

    print("\n" + "=" * 80)
    print(f"PROYECTO: {project['title']}")
    print(f"ID:       {project['id']}")
    print(f"RAMO:     {project['subject']}")
    print(f"ALUMNO:   {project['student']} ({project['career']})")
    print("=" * 80)

    deliverables = project.get("deliverables") or []
    if deliverables:
        print("\nENTREGABLES SOLICITADOS:")
        for d in deliverables:
            print(f"  [ ] {d}")

    criteria = project.get("criteria") or []
    if criteria:
        print(f"\nCRITERIOS DE EVALUACIÓN ({len(criteria)}):")
        total_pts = 0.0
        for c in criteria:
            pts = f"{c.get('points')} pts" if c.get("points") is not None else "sin puntaje"
            ev = " [EVIDENCIA OBLIGATORIA]" if c.get("requires_evidence") else ""
            status_symbol = "[OK]" if c.get("status") == "complete" else "[PARCIAL]" if c.get("status") == "partial" else "[PENDIENTE]"
            print(f"  {status_symbol:<12} {c['indicator']} ({pts}){ev}")
            if c.get("points") is not None:
                total_pts += float(c["points"])
        print(f"  Puntaje total rúbrica: {total_pts:.1f} puntos")

    versions = store.list_versions(args.project_id)
    print(f"\nVERSIONES GUARDADAS ({len(versions)}):")
    for v in versions[:5]:
        print(f"  v{v['version_number']:<3} | motivo: {v['reason']:<20} | fecha: {v['created_at']}")

    doc_len = len(project.get("document_html") or "")
    print(f"\nDOCUMENTO HTML: {doc_len} caracteres ({doc_len / 1024:.1f} KB)\n")


def cmd_export(args: argparse.Namespace) -> None:
    store = get_store()
    project = store.get_project(args.project_id)
    if not project:
        print(f"Error: Proyecto '{args.project_id}' no encontrado.")
        sys.exit(1)

    html_content = project.get("document_html") or "<p>Documento vacío.</p>"
    sections = parse_html_to_sections(html_content)
    for s in sections:
        if s.get("type") == "image":
            s["image_path"] = resolve_image_path(s.get("image_path"))

    if args.output:
        output_path = Path(args.output).resolve()
    else:
        stem = "".join(c for c in project["title"] if c.isalnum() or c in (" ", "-", "_")).strip()[:50]
        output_path = settings.projects_dir / args.project_id / "exports" / f"{stem}.docx"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc_data = {
        "title": project["title"],
        "subject": project.get("subject", "General"),
        "student": project.get("student", "Nicolás Javier Jara Guzmán"),
        "career": project.get("career", "Ingeniería en Informática"),
        "institution": "Instituto Profesional Iplacex",
        "sections": sections,
    }
    create_iplacex_document(doc_data, str(output_path))
    print(f"\n[OK] Documento exportado exitosamente:\n{output_path}\n")


def cmd_search(args: argparse.Namespace) -> None:
    store = get_store()
    results = store.search_sources(args.project_id, args.query, limit=args.limit)
    print(f"\nResultados para '{args.query}' en fuentes ({len(results)}):\n")
    for r in results:
        print(f"--- [Fuente: {r['filename']}, fragmento {r['chunk_index'] + 1}] ---")
        print(r["content"][:300].strip() + "...\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Iplacex Studio CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    subparsers.add_parser("list", help="Listar todos los proyectos")

    # show
    show_p = subparsers.add_parser("show", help="Ver detalles de un proyecto")
    show_p.add_argument("project_id", help="ID del proyecto (ej: prj_...)")

    # export
    export_p = subparsers.add_parser("export", help="Exportar proyecto a DOCX")
    export_p.add_argument("project_id", help="ID del proyecto")
    export_p.add_argument("--output", "-o", help="Ruta de salida personalizada")

    # search
    search_p = subparsers.add_parser("search", help="Buscar en fuentes del proyecto")
    search_p.add_argument("project_id", help="ID del proyecto")
    search_p.add_argument("query", help="Término a buscar")
    search_p.add_argument("--limit", type=int, default=5)

    args = parser.parse_args()
    if args.command == "list":
        cmd_list(args)
    elif args.command == "show":
        cmd_show(args)
    elif args.command == "export":
        cmd_export(args)
    elif args.command == "search":
        cmd_search(args)


if __name__ == "__main__":
    main()
