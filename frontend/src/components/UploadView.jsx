import React, { useState, useRef } from 'react';
import { UploadCloud, Wand2, BookOpen, User, GraduationCap, CheckCircle2 } from 'lucide-react';

const COMMON_SUBJECTS = [
  'Paradigma Orientado a Objetos',
  'Sistemas Operativos',
  'Modelamiento de Bases de Datos',
  'Programación de Bases de Datos',
  'Consulta de Datos',
  'Programación Web',
  'Diseño Web',
  'Modelamiento y Programación No SQL',
  'Red Hat Linux',
  'Inglés Técnico',
];

export default function UploadView({ onAnalyze, loading, config }) {
  const [file, setFile] = useState(null);
  const [pautaText, setPautaText] = useState('');
  const [subject, setSubject] = useState('');
  const [student, setStudent] = useState(config.default_student || 'Nicolás Javier Jara Guzmán');
  const [career, setCareer] = useState(config.default_career || 'Ingeniería en Informática');
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
      alert('Por favor sube un archivo (PDF o Word) o pega el texto de la pauta.');
      return;
    }
    onAnalyze({ file, pautaText, subject, student, career });
  };

  return (
    <div className="upload-card">
      <div style={{ maxWidth: 640, margin: '0 auto 1.5rem auto' }}>
        <h1 style={{ fontSize: '2rem', fontWeight: 800, letterSpacing: '-0.02em', marginBottom: '0.6rem' }}>
          Convierte una pauta en un proyecto verificable
        </h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem' }}>
          La IA separa criterios, entregables, código y capturas obligatorias. El trabajo queda guardado localmente con historial, fuentes y memoria del proyecto.
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
          <div className="form-group">
            <label><User size={13} style={{ display: 'inline', marginRight: 4 }} /> Nombre del Estudiante</label>
            <input
              type="text"
              className="form-input"
              value={student}
              onChange={(e) => setStudent(e.target.value)}
              placeholder="Nicolás Javier Jara Guzmán"
            />
          </div>

          <div className="form-group">
            <label><GraduationCap size={13} style={{ display: 'inline', marginRight: 4 }} /> Carrera</label>
            <input
              type="text"
              className="form-input"
              value={career}
              onChange={(e) => setCareer(e.target.value)}
              placeholder="Ingeniería en Informática"
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
        <div style={{ marginTop: '2.5rem', display: 'flex', justifyContent: 'center' }}>
          <button
            type="submit"
            className="btn-primary"
            style={{ padding: '0.8rem 2.5rem', fontSize: '1.05rem', borderRadius: 12 }}
            disabled={loading}
          >
            {loading ? (
              <>
                <div className="spinner" />
                <span>Analizando Pauta con IA...</span>
              </>
            ) : (
              <>
                <Wand2 size={20} />
                <span>Analizar pauta y crear proyecto</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
