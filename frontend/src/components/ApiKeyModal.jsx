import React, { useState, useEffect } from 'react';
import { Settings, X, Check, ExternalLink, ShieldCheck, User, Building2, Sparkles } from 'lucide-react';
import { api } from '../api';

export default function ApiKeyModal({ isOpen, onClose, onSaved, config = {} }) {
  const [keyInput, setKeyInput] = useState('');
  const [modelInput, setModelInput] = useState(config.model || 'gemini-2.5-flash');
  const [authorInput, setAuthorInput] = useState(config.default_student || '');
  const [institutionInput, setInstitutionInput] = useState(config.default_institution || '');
  const [careerInput, setCareerInput] = useState(config.default_career || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    if (isOpen) {
      // oxlint-disable-next-line react/set-state-in-effect -- sync form fields when modal opens
      setModelInput(config.model || 'gemini-2.5-flash');
      setAuthorInput(config.default_student || '');
      setInstitutionInput(config.default_institution || '');
      setCareerInput(config.default_career || '');
      setKeyInput('');
      setError('');
      setSuccess(false);
    }
  }, [isOpen, config]);

  if (!isOpen) return null;

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    const payload = {};
    if (keyInput.trim()) payload.gemini_api_key = keyInput.trim();
    if (modelInput.trim()) payload.gemini_model = modelInput.trim();
    payload.author_name = authorInput.trim();
    payload.institution = institutionInput.trim();
    payload.career = careerInput.trim();

    try {
      await api('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      setSuccess(true);
      setTimeout(() => {
        onSaved();
        onClose();
      }, 700);
    } catch (err) {
      setError(err.message || 'Error al conectar con el backend.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" style={{ maxWidth: 540 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <div style={{ background: 'rgba(59, 130, 246, 0.15)', padding: '0.5rem', borderRadius: '10px', color: 'var(--accent)' }}>
              <Settings size={20} />
            </div>
            <div>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>Ajustes del Estudio</h3>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Personaliza tu perfil de autor y la configuración de IA.
              </p>
            </div>
          </div>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: 'var(--text-dim)', cursor: 'pointer' }}>
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSave}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.8rem', marginBottom: '1rem' }}>
            <div className="form-group" style={{ gridColumn: 'span 2' }}>
              <label><User size={13} style={{ display: 'inline', marginRight: 4 }} /> Tu Nombre (Autor)</label>
              <input
                type="text"
                className="form-input"
                placeholder="Ej: Nicolás Jara"
                value={authorInput}
                onChange={(e) => setAuthorInput(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label><Building2 size={13} style={{ display: 'inline', marginRight: 4 }} /> Institución / Universidad</label>
              <input
                type="text"
                className="form-input"
                placeholder="Opcional (o deja en blanco)"
                value={institutionInput}
                onChange={(e) => setInstitutionInput(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label>Área / Carrera</label>
              <input
                type="text"
                className="form-input"
                placeholder="Ej: Ingeniería en Informática"
                value={careerInput}
                onChange={(e) => setCareerInput(e.target.value)}
              />
            </div>
          </div>

          <div style={{ borderTop: '1px solid var(--border)', paddingTop: '1rem', marginBottom: '1rem' }}>
            <div className="form-group" style={{ marginBottom: '0.8rem' }}>
              <label><Sparkles size={13} style={{ display: 'inline', marginRight: 4 }} /> Modelo Gemini</label>
              <select
                className="form-input"
                value={modelInput}
                onChange={(e) => setModelInput(e.target.value)}
              >
                <option value="gemini-2.5-flash">Gemini 2.5 Flash (Recomendado - Rápido y preciso)</option>
                <option value="gemini-2.0-flash">Gemini 2.0 Flash</option>
                <option value="gemini-1.5-flash">Gemini 1.5 Flash</option>
                <option value="gemini-1.5-pro">Gemini 1.5 Pro (Razonamiento profundo)</option>
              </select>
            </div>

            <div className="form-group">
              <label>Clave API de Gemini ({config.has_api_key ? `Configurada: ${config.api_key_masked}` : 'No configurada'})</label>
              <input
                type="password"
                className="form-input"
                placeholder={config.has_api_key ? 'Deja en blanco para conservar la clave actual' : 'Pega aquí tu clave de AI Studio'}
                value={keyInput}
                onChange={(e) => setKeyInput(e.target.value)}
              />
            </div>
          </div>

          {error && (
            <p style={{ color: 'var(--danger)', fontSize: '0.85rem', marginBottom: '1rem' }}>
              {error}
            </p>
          )}

          {success && (
            <p style={{ color: 'var(--success)', fontSize: '0.85rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <Check size={16} /> Ajustes guardados correctamente.
            </p>
          )}

          <div style={{ background: 'var(--bg-input)', padding: '0.75rem 0.9rem', borderRadius: '10px', marginBottom: '1.25rem', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-main)', fontWeight: 600, marginBottom: '0.2rem' }}>
              <ShieldCheck size={15} color="var(--success)" /> Configuración local en .env
            </div>
            Los datos quedan en tu máquina. Obtén tu clave gratuita en{' '}
            <a
              href="https://aistudio.google.com/app/apikey"
              target="_blank"
              rel="noreferrer"
              style={{ color: 'var(--accent)', textDecoration: 'none' }}
            >
              Google AI Studio <ExternalLink size={11} style={{ display: 'inline' }} />
            </a>.
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
            <button type="button" className="btn-secondary" onClick={onClose}>
              Cancelar
            </button>
            <button type="submit" className="btn-primary" disabled={saving}>
              {saving ? <div className="spinner" /> : <><Check size={16} /> Guardar Ajustes</>}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
