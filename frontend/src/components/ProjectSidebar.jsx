import React from 'react';
import { Clock3, Database, FilePlus2, FolderKanban } from 'lucide-react';

function formatDate(value) {
  if (!value) return '';
  return new Intl.DateTimeFormat('es-CL', { day: '2-digit', month: 'short' }).format(new Date(value));
}

export default function ProjectSidebar({ projects, activeProjectId, onOpenProject, onNewProject, health }) {
  return (
    <aside className="project-sidebar">
      <div className="sidebar-heading">
        <div>
          <span className="eyebrow">Espacio local</span>
          <h2>Mis trabajos</h2>
        </div>
        <button className="icon-button" onClick={onNewProject} title="Crear trabajo">
          <FilePlus2 size={17} />
        </button>
      </div>

      <div className="project-list">
        {projects.length === 0 ? (
          <div className="sidebar-empty">
            <FolderKanban size={22} />
            <span>Tu primer trabajo aparecerá aquí.</span>
          </div>
        ) : projects.map((project) => (
          <button
            key={project.id}
            className={`project-item ${activeProjectId === project.id ? 'active' : ''}`}
            onClick={() => onOpenProject(project.id)}
          >
            <strong>{project.title}</strong>
            <span>{project.subject || 'Sin asignatura'}</span>
            <small><Clock3 size={12} /> {formatDate(project.updated_at)}</small>
          </button>
        ))}
      </div>

      <div className="database-status">
        <Database size={14} />
        <div>
          <strong>{health?.status === 'ok' ? 'Memoria activa' : 'Backend desconectado'}</strong>
          <span>{health?.fts5 ? 'SQLite + búsqueda FTS5' : 'SQLite local'}</span>
        </div>
      </div>
    </aside>
  );
}
