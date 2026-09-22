import React from 'react';
import { Clock3, Database, FilePlus2, FolderKanban, Trash2 } from 'lucide-react';

function formatDate(value) {
  if (!value) return '';
  return new Intl.DateTimeFormat('es-CL', { day: '2-digit', month: 'short' }).format(new Date(value));
}

export default function ProjectSidebar({ projects, activeProjectId, onOpenProject, onNewProject, onDeleteProject, health }) {
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
          <div
            key={project.id}
            className={`project-item ${activeProjectId === project.id ? 'active' : ''}`}
            onClick={() => onOpenProject(project.id)}
            style={{ position: 'relative', cursor: 'pointer' }}
          >
            <div style={{ flex: 1, minWidth: 0, paddingRight: '22px' }}>
              <strong>{project.title}</strong>
              <span>{project.subject || 'Sin asignatura'}</span>
              <small><Clock3 size={12} /> {formatDate(project.updated_at)}</small>
            </div>
            {onDeleteProject && (
              <button
                type="button"
                className="btn-icon-danger"
                style={{
                  position: 'absolute',
                  top: '10px',
                  right: '10px',
                  opacity: 0.6,
                  padding: '4px',
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  color: 'var(--text-dim)',
                  borderRadius: '4px',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.opacity = '1'; e.currentTarget.style.color = '#ef4444'; }}
                onMouseLeave={(e) => { e.currentTarget.style.opacity = '0.6'; e.currentTarget.style.color = 'var(--text-dim)'; }}
                onClick={(e) => {
                  e.stopPropagation();
                  if (window.confirm(`¿Estás seguro de eliminar el proyecto "${project.title}"? Esta acción borrará el documento y sus archivos de forma permanente.`)) {
                    onDeleteProject(project.id);
                  }
                }}
                title="Eliminar proyecto"
              >
                <Trash2 size={14} />
              </button>
            )}
          </div>
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
