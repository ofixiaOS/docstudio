import React, { useState, useRef } from 'react';
import { UploadCloud, Wand2, BookOpen, User, GraduationCap, CheckCircle2 } from 'lucide-react';

const COMMON_SUBJECTS = [
  'Sistemas Operativos',
  'Bases de Datos',
  'Arquitectura de Software',
  'Programación Web',
  'Redes y Seguridad',
  'Inteligencia Artificial',
  'Ingeniería de Software',
  'Informe Técnico',
];

export default function UploadView({ onAnalyze, onCreateOffline, loading, config }) {
  const [file, setFile] = useState(null);
  const [pautaText, setPautaText] = useState('');
  const [projectTitle, setProjectTitle] = useState('');
  const [subject, setSubject] = useState('');
  const [student, setStudent] = useState(config.default_student || 'Autor');
  const [career, setCareer] = useState(config.default_career || '');
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef(null);

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelect = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!file && !pautaText.trim()) {
      if (!projectTitle.trim()) {
        alert('Escribe al menos un título para crear el documento o sube una pauta.');
        return;
      }
      onCreateOffline({ title: projectTitle, file: null, pautaText: 'Documento en blanco', subject, student, career });
      return;
    }
    if (config.has_api_key) {
      onAnalyze({ file, pautaText, subject, student, career });
      return;
    }
    if (!projectTitle.trim()) {
      alert('Escribe un título para crear el proyecto.');
      return;
    }
    onCreateOffline({ title: projectTitle, file, pautaText, subject, student, career });
  };

  const createOffline = () => {
    if (!projectTitle.trim() && !file && !pautaText.trim()) {
      alert('Escribe un título para crear el proyecto en blanco.');
      return;
    }
    const title = projectTitle.trim() || 'Nuevo Documento';
    onCreateOffline({ title, file, pautaText: pautaText || 'Documento inicial', subject, student, career });
  };

  return (
    <div className="upload-card">
      <div style={{ maxWidth: 640, margin: '0 auto 1.5rem auto' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 800, letterSpacing: '-0.02em', marginBottom: '0.6rem' }}>
          Crea o desarrolla tu documento asistido por IA
        </h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem' }}>
          Sube una guía, pauta o requerimientos (o parte en blanco). El estudio estructura el esquema, aprende tus preferencias con memoria activa y exporta a Word profesional.
        </p>
      </div>

      <form onSubmit={handleSubmit}>
        {/* Dropzone */}
        <div
          className={`dropzone ${isDragOver ? 'dragover' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
          onDragLeave={() => setIsDragOver(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
        >
          <input
            type="file"
            ref={fileInputRef}
            style={{ display: 'none' }}
            accept=".pdf,.docx,.txt"
            onChange={handleFileSelect}
          />
          <div className="dropzone-icon">
            <UploadCloud size={30} />
          </div>
          {file ? (
            <div>
              <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', color: 'var(--success)', fontWeight: 600, fontSize: '1.05rem', marginBottom: '0.3rem' }}>
                <CheckCircle2 size={18} /> {file.name}
              </div>
              <p style={{ color: 'var(--text-dim)', fontSize: '0.8rem' }}>
                {(file.size / 1024).toFixed(1)} KB — Clic para cambiar archivo
              </p>
            </div>
          ) : (
            <div>
              <p style={{ fontWeight: 600, fontSize: '1rem', marginBottom: '0.3rem' }}>
                Arrastra aquí el PDF o Word de la pauta
              </p>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>
                o haz clic para explorar tus archivos (Soporta PDF, DOCX, TXT)
              </p>
            </div>
          )}
        </div>

        {/* Alternativa: Texto directo */}
        <div style={{ marginBottom: '1.5rem', textAlign: 'left' }}>
          <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', display: 'block', marginBottom: '0.4rem' }}>
            O pega las instrucciones / rúbrica directamente:
          </label>
          <textarea
            className="form-input"
            style={{ width: '100%', minHeight: 90, resize: 'vertical', fontFamily: 'inherit' }}
            placeholder="Pega aquí el contenido de la pauta si no tienes el archivo a mano..."
            value={pautaText}
            onChange={(e) => setPautaText(e.target.value)}
          />
        </div>

        {/* Metadatos del Estudiante y Ramo */}
        <div className="form-grid">
          <div className="form-group" style={{ gridColumn: 'span 2' }}>
            <label><BookOpen size={13} style={{ display: 'inline', marginRight: 4 }} /> Título del proyecto {config.has_api_key ? '(obligatorio solo en modo local)' : '(obligatorio)'}</label>
            <input
              type="text"
              className="form-input"
              value={projectTitle}
              onChange={(e) => setProjectTitle(e.target.value)}
              placeholder="Ej: Evaluación 2 - Modelamiento de Base de Datos"
            />
          </div>
          <div className="form-group">
            <label><User size={13} style={{ display: 'inline', marginRight: 4 }} /> Nombre del Estudiante</label>
            <input
              type="text"
              className="form-input"
              value={student}
              onChange={(e) => setStudent(e.target.value)}
              placeholder={config?.default_student || 'Ej: Nombre y Apellido'}
            />
          </div>

          <div className="form-group">
            <label><GraduationCap size={13} style={{ display: 'inline', marginRight: 4 }} /> Carrera / Área</label>
            <input
              type="text"
              className="form-input"
              value={career}
              onChange={(e) => setCareer(e.target.value)}
              placeholder={config?.default_career || 'Ej: Ingeniería en Informática'}
            />
          </div>

          <div className="form-group" style={{ gridColumn: 'span 2' }}>
            <label><BookOpen size={13} style={{ display: 'inline', marginRight: 4 }} /> Asignatura (Opcional - la IA la detecta del archivo)</label>
            <input
              type="text"
              className="form-input"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              placeholder="Ej: Paradigma Orientado a Objetos (o déjalo en blanco para autodetectar)"
              list="subjects-list"
            />
            <datalist id="subjects-list">
              {COMMON_SUBJECTS.map((s) => (
                <option key={s} value={s} />
              ))}
            </datalist>
          </div>
        </div>

        {/* Botón Principal */}
        <div style={{ marginTop: '2.5rem', display: 'flex', justifyContent: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <button
            type="submit"
            className="btn-primary"
            style={{ padding: '0.8rem 2.5rem', fontSize: '1.05rem', borderRadius: 12 }}
            disabled={loading}
          >
            {loading ? (
              <>
                <div className="spinner" />
                <span>{config.has_api_key ? 'Analizando pauta con IA...' : 'Creando proyecto local...'}</span>
              </>
            ) : config.has_api_key ? (
              <>
                <Wand2 size={20} />
                <span>Analizar pauta y crear proyecto</span>
              </>
            ) : (
              <>
                <BookOpen size={20} />
                <span>Crear proyecto sin IA</span>
              </>
            )}
          </button>
          {config.has_api_key && (
            <button type="button" className="btn-secondary" onClick={createOffline} disabled={loading}
              style={{ padding: '0.8rem 1.4rem', fontSize: '0.95rem', borderRadius: 12 }}>
              <BookOpen size={18} /> Crear sin IA
            </button>
          )}
        </div>
      </form>
    </div>
  );
}
