from __future__ import annotations

import json
import math
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .documents import chunk_text, sha256_file


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


class Store:
    def __init__(self, database_path: Path):
        self.database_path = database_path
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.fts_enabled = False
        self.initialize()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as db:
            db.execute("PRAGMA journal_mode = WAL")
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    subject TEXT NOT NULL DEFAULT '',
                    student TEXT NOT NULL DEFAULT '',
                    career TEXT NOT NULL DEFAULT '',
                    summary TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'active',
                    rubric_text TEXT NOT NULL DEFAULT '',
                    document_html TEXT NOT NULL DEFAULT '',
                    deliverables_json TEXT NOT NULL DEFAULT '[]',
                    outline_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS rubric_criteria (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL,
                    criterion TEXT NOT NULL,
                    indicator TEXT NOT NULL,
                    points REAL,
                    requires_evidence INTEGER NOT NULL DEFAULT 0,
                    evidence_description TEXT,
                    deliverable TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    feedback TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS project_versions (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    version_number INTEGER NOT NULL,
                    reason TEXT NOT NULL,
                    html_content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(project_id, version_number)
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    role TEXT NOT NULL CHECK(role IN ('user','assistant','system')),
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
                    kind TEXT NOT NULL,
                    content TEXT NOT NULL,
                    importance REAL NOT NULL DEFAULT 0.5,
                    source TEXT NOT NULL DEFAULT 'user',
                    embedding_json TEXT,
                    embedding_model TEXT,
                    created_at TEXT NOT NULL,
                    last_accessed_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS source_documents (
                    id TEXT PRIMARY KEY,
                    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
                    path TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    sha256 TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    text_content TEXT NOT NULL,
                    indexed_at TEXT NOT NULL,
                    UNIQUE(project_id, sha256)
                );
                CREATE TABLE IF NOT EXISTS source_chunks (
                    id TEXT PRIMARY KEY,
                    source_document_id TEXT NOT NULL REFERENCES source_documents(id) ON DELETE CASCADE,
                    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    embedding_json TEXT,
                    embedding_model TEXT,
                    UNIQUE(source_document_id, chunk_index)
                );
                CREATE TABLE IF NOT EXISTS evidence_files (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    criterion_id TEXT REFERENCES rubric_criteria(id) ON DELETE SET NULL,
                    filename TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    caption TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_projects_updated ON projects(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_criteria_project ON rubric_criteria(project_id, position);
                CREATE INDEX IF NOT EXISTS idx_messages_project ON messages(project_id, created_at);
                CREATE INDEX IF NOT EXISTS idx_memories_project ON memories(project_id, importance DESC);
                CREATE INDEX IF NOT EXISTS idx_chunks_project ON source_chunks(project_id);
                """
            )
            project_columns = {row["name"] for row in db.execute("PRAGMA table_info(projects)").fetchall()}
            if "outline_json" not in project_columns:
                db.execute("ALTER TABLE projects ADD COLUMN outline_json TEXT NOT NULL DEFAULT '[]'")
            memory_columns = {row["name"] for row in db.execute("PRAGMA table_info(memories)").fetchall()}
            if "embedding_json" not in memory_columns:
                db.execute("ALTER TABLE memories ADD COLUMN embedding_json TEXT")
            if "embedding_model" not in memory_columns:
                db.execute("ALTER TABLE memories ADD COLUMN embedding_model TEXT")
            try:
                db.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS source_chunks_fts USING fts5("
                    "chunk_id UNINDEXED, project_id UNINDEXED, content, tokenize='unicode61 remove_diacritics 2')"
                )
                self.fts_enabled = True
            except sqlite3.OperationalError:
                self.fts_enabled = False

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        return dict(row) if row else None

    def create_project(self, *, title: str, subject: str, student: str, career: str,
                       summary: str, rubric_text: str, deliverables: list[str], outline: list[dict[str, Any]]) -> str:
        project_id = new_id("prj")
        now = utcnow()
        with self.connect() as db:
            db.execute(
                "INSERT INTO projects(id,title,subject,student,career,summary,rubric_text,deliverables_json,outline_json,created_at,updated_at) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (project_id, title, subject, student, career, summary, rubric_text,
                 json.dumps(deliverables, ensure_ascii=False), json.dumps(outline, ensure_ascii=False), now, now),
            )
        return project_id

    def list_projects(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT id,title,subject,student,status,summary,created_at,updated_at, "
                "length(document_html) AS document_size FROM projects ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            project = self._row(db.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone())
            if not project:
                return None
            criteria = [dict(row) for row in db.execute(
                "SELECT * FROM rubric_criteria WHERE project_id=? ORDER BY position", (project_id,)
            ).fetchall()]
            sources = [dict(row) for row in db.execute(
                "SELECT id,filename,path,kind,indexed_at,length(text_content) AS text_size FROM source_documents "
                "WHERE project_id=? ORDER BY indexed_at DESC", (project_id,)
            ).fetchall()]
            evidence = [dict(row) for row in db.execute(
                "SELECT * FROM evidence_files WHERE project_id=? ORDER BY created_at DESC", (project_id,)
            ).fetchall()]
        project["deliverables"] = json.loads(project.pop("deliverables_json") or "[]")
        project["outline"] = json.loads(project.pop("outline_json") or "[]")
        project["criteria"] = criteria
        project["sources"] = sources
        project["evidence"] = evidence
        return project

    def add_criteria(self, project_id: str, criteria: list[dict[str, Any]]) -> list[dict[str, Any]]:
        created = []
        with self.connect() as db:
            for position, item in enumerate(criteria):
                criterion_id = new_id("crit")
                db.execute(
                    "INSERT INTO rubric_criteria(id,project_id,position,criterion,indicator,points,requires_evidence,"
                    "evidence_description,deliverable) VALUES(?,?,?,?,?,?,?,?,?)",
                    (criterion_id, project_id, position, item.get("criterion", ""), item.get("indicator", ""),
                     item.get("points"), int(bool(item.get("requires_evidence"))),
                     item.get("evidence_description"), item.get("deliverable")),
                )
                created.append({"id": criterion_id, **item, "position": position, "status": "pending", "feedback": ""})
        return created

    def update_document(self, project_id: str, html_content: str) -> None:
        with self.connect() as db:
            db.execute(
                "UPDATE projects SET document_html=?, updated_at=? WHERE id=?",
                (html_content, utcnow(), project_id),
            )

    def create_snapshot(self, project_id: str, html_content: str, reason: str) -> int:
        with self.connect() as db:
            current = db.execute(
                "SELECT COALESCE(MAX(version_number),0) FROM project_versions WHERE project_id=?", (project_id,)
            ).fetchone()[0]
            version = int(current) + 1
            db.execute(
                "INSERT INTO project_versions(id,project_id,version_number,reason,html_content,created_at) "
                "VALUES(?,?,?,?,?,?)",
                (new_id("ver"), project_id, version, reason, html_content, utcnow()),
            )
            db.execute(
                "UPDATE projects SET document_html=?, updated_at=? WHERE id=?",
                (html_content, utcnow(), project_id),
            )
        return version

    def add_message(self, project_id: str, role: str, content: str) -> dict[str, Any]:
        item = {"id": new_id("msg"), "project_id": project_id, "role": role, "content": content, "created_at": utcnow()}
        with self.connect() as db:
            db.execute(
                "INSERT INTO messages(id,project_id,role,content,created_at) VALUES(:id,:project_id,:role,:content,:created_at)",
                item,
            )
        return item

    def list_messages(self, project_id: str, limit: int = 30) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM (SELECT * FROM messages WHERE project_id=? ORDER BY created_at DESC LIMIT ?) "
                "ORDER BY created_at", (project_id, limit)
            ).fetchall()
        return [dict(row) for row in rows]

    def add_memory(self, project_id: str | None, kind: str, content: str,
                   importance: float = 0.6, source: str = "user",
                   embedding: list[float] | None = None, embedding_model: str | None = None) -> dict[str, Any]:
        now = utcnow()
        item = {"id": new_id("mem"), "project_id": project_id, "kind": kind, "content": content,
                "importance": importance, "source": source, "created_at": now, "last_accessed_at": now}
        with self.connect() as db:
            db.execute(
                "INSERT INTO memories(id,project_id,kind,content,importance,source,embedding_json,embedding_model,created_at,last_accessed_at) "
                "VALUES(:id,:project_id,:kind,:content,:importance,:source,:embedding_json,:embedding_model,:created_at,:last_accessed_at)",
                {**item, "embedding_json": json.dumps(embedding) if embedding else None, "embedding_model": embedding_model}
            )
        return item

    def search_memories(self, project_id: str, query: str, limit: int = 8) -> list[dict[str, Any]]:
        tokens = [token for token in re.findall(r"\w+", query.lower()) if len(token) > 3]
        with self.connect() as db:
            if tokens:
                clauses = " OR ".join("lower(content) LIKE ?" for _ in tokens)
                params: list[Any] = [project_id, *[f"%{token}%" for token in tokens], limit]
                rows = db.execute(
                    f"SELECT * FROM memories WHERE (project_id=? OR project_id IS NULL) AND ({clauses}) "
                    "ORDER BY importance DESC,last_accessed_at DESC LIMIT ?", params
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM memories WHERE project_id=? OR project_id IS NULL "
                    "ORDER BY importance DESC,last_accessed_at DESC LIMIT ?", (project_id, limit)
                ).fetchall()
            ids = [row["id"] for row in rows]
            if ids:
                db.execute(
                    f"UPDATE memories SET last_accessed_at=? WHERE id IN ({','.join('?' for _ in ids)})",
                    (utcnow(), *ids),
                )
        return [dict(row) for row in rows]

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        if not left or len(left) != len(right):
            return -1.0
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        return dot / (left_norm * right_norm) if left_norm and right_norm else -1.0

    def search_memories_vector(self, project_id: str, query_embedding: list[float], limit: int = 8) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM memories WHERE (project_id=? OR project_id IS NULL) AND embedding_json IS NOT NULL",
                (project_id,),
            ).fetchall()
        ranked = []
        for row in rows:
            item = dict(row)
            item["similarity"] = self._cosine(query_embedding, json.loads(item["embedding_json"]))
            ranked.append(item)
        ranked.sort(key=lambda item: (item["similarity"], item["importance"]), reverse=True)
        return ranked[:limit]

    def add_source(self, project_id: str, path: Path, filename: str, kind: str, text: str) -> dict[str, Any]:
        source_id = new_id("src")
        digest = sha256_file(path)
        chunks = chunk_text(text)
        with self.connect() as db:
            existing = db.execute(
                "SELECT id,filename,path,kind,indexed_at,length(text_content) AS text_size FROM source_documents "
                "WHERE project_id=? AND sha256=?", (project_id, digest)
            ).fetchone()
            if existing:
                return dict(existing)
            db.execute(
                "INSERT INTO source_documents(id,project_id,path,filename,sha256,kind,text_content,indexed_at) "
                "VALUES(?,?,?,?,?,?,?,?)", (source_id, project_id, str(path), filename, digest, kind, text, utcnow())
            )
            for index, content in enumerate(chunks):
                chunk_id = new_id("chk")
                db.execute(
                    "INSERT INTO source_chunks(id,source_document_id,project_id,chunk_index,content) VALUES(?,?,?,?,?)",
                    (chunk_id, source_id, project_id, index, content),
                )
                if self.fts_enabled:
                    db.execute(
                        "INSERT INTO source_chunks_fts(chunk_id,project_id,content) VALUES(?,?,?)",
                        (chunk_id, project_id, content),
                    )
        return {"id": source_id, "filename": filename, "path": str(path), "kind": kind,
                "indexed_at": utcnow(), "text_size": len(text), "chunks": len(chunks)}

    def get_source_chunks(self, source_id: str) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT sc.*,sd.filename FROM source_chunks sc JOIN source_documents sd ON sd.id=sc.source_document_id "
                "WHERE sc.source_document_id=? ORDER BY sc.chunk_index", (source_id,)
            ).fetchall()
        return [dict(row) for row in rows]

    def set_chunk_embeddings(self, items: list[tuple[str, list[float]]], model: str) -> None:
        with self.connect() as db:
            db.executemany(
                "UPDATE source_chunks SET embedding_json=?,embedding_model=? WHERE id=?",
                [(json.dumps(vector), model, chunk_id) for chunk_id, vector in items],
            )

    @staticmethod
    def _fts_query(query: str) -> str:
        tokens = [token for token in re.findall(r"\w+", query, flags=re.UNICODE) if len(token) > 2]
        return " OR ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens[:12])

    def search_sources(self, project_id: str, query: str, limit: int = 8) -> list[dict[str, Any]]:
        with self.connect() as db:
            fts_query = self._fts_query(query)
            if self.fts_enabled and fts_query:
                rows = db.execute(
                    "SELECT sc.id,sc.chunk_index,sc.content,sd.filename,sd.path,sd.kind,fts.rank "
                    "FROM source_chunks_fts AS fts JOIN source_chunks sc ON sc.id=fts.chunk_id "
                    "JOIN source_documents sd ON sd.id=sc.source_document_id "
                    "WHERE source_chunks_fts MATCH ? AND fts.project_id=? ORDER BY fts.rank LIMIT ?",
                    (fts_query, project_id, limit),
                ).fetchall()
            else:
                rows = db.execute(
                    "SELECT sc.id,sc.chunk_index,sc.content,sd.filename,sd.path,sd.kind,NULL AS rank "
                    "FROM source_chunks sc JOIN source_documents sd ON sd.id=sc.source_document_id "
                    "WHERE sc.project_id=? AND lower(sc.content) LIKE ? LIMIT ?",
                    (project_id, f"%{query.lower()}%", limit),
                ).fetchall()
        return [dict(row) for row in rows]

    def search_sources_vector(self, project_id: str, query_embedding: list[float], limit: int = 8) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT sc.id,sc.chunk_index,sc.content,sc.embedding_json,sd.filename,sd.path,sd.kind "
                "FROM source_chunks sc JOIN source_documents sd ON sd.id=sc.source_document_id "
                "WHERE sc.project_id=? AND sc.embedding_json IS NOT NULL", (project_id,)
            ).fetchall()
        ranked = []
        for row in rows:
            item = dict(row)
            item["similarity"] = self._cosine(query_embedding, json.loads(item.pop("embedding_json")))
            ranked.append(item)
        ranked.sort(key=lambda item: item["similarity"], reverse=True)
        return ranked[:limit]

    def update_audit(self, project_id: str, items: list[dict[str, Any]]) -> None:
        with self.connect() as db:
            for item in items:
                db.execute(
                    "UPDATE rubric_criteria SET status=?,feedback=? WHERE id=? AND project_id=?",
                    (item["status"], item.get("feedback", ""), item["criterion_id"], project_id),
                )

    def add_evidence(self, project_id: str, stored_path: Path, filename: str,
                     caption: str, criterion_id: str | None) -> dict[str, Any]:
        item = {"id": new_id("ev"), "project_id": project_id, "criterion_id": criterion_id,
                "filename": filename, "stored_path": str(stored_path), "caption": caption, "created_at": utcnow()}
        with self.connect() as db:
            db.execute(
                "INSERT INTO evidence_files(id,project_id,criterion_id,filename,stored_path,caption,created_at) "
                "VALUES(:id,:project_id,:criterion_id,:filename,:stored_path,:caption,:created_at)", item
            )
        return item

    def get_evidence(self, evidence_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            return self._row(db.execute("SELECT * FROM evidence_files WHERE id=?", (evidence_id,)).fetchone())
