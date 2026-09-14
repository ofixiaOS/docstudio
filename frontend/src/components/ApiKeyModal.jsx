import React, { useState } from 'react';
import { Key, X, Check, ExternalLink, ShieldCheck } from 'lucide-react';
import { api } from '../api';

export default function ApiKeyModal({ isOpen, onClose, onSaved, currentKeyMasked }) {
  const [keyInput, setKeyInput] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  if (!isOpen) return null;

  const handleSave = async (e) => {
    e.preventDefault();
    if (!keyInput.trim()) {
      setError('Por favor ingresa una clave válida.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      await api('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ gemini_api_key: keyInput.trim() }),
      });
      setSuccess(true);
      setTimeout(() => {
        onSaved();
        onClose();
      }, 900);
    } catch (err) {
      setError(err.message || 'Error al conectar con el backend.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <div style={{ background: 'rgba(59, 130, 246, 0.15)', padding: '0.5rem', borderRadius: '10px', color: 'var(--accent)' }}>
              <Key size={20} />
            </div>
            <div>
              <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>Configurar Google Gemini API</h3>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Estado actual: {currentKeyMasked || 'No configurada'}
              </p>
            </div>
          </div>
          <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: 'var(--text-dim)', cursor: 'pointer' }}>
            <X size={20} />
          </button>
        </div>

        <form onSubmit={handleSave}>
          <div className="form-group" style={{ marginBottom: '1.2rem' }}>
            <label>Clave API de Gemini (AI Studio)</label>
            <input
              type="password"
              className="form-input"
              placeholder="Pega aquí tu clave de Gemini"
              value={keyInput}
              onChange={(e) => setKeyInput(e.target.value)}
              autoFocus
            />
          </div>

          {error && (
            <p style={{ color: 'var(--danger)', fontSize: '0.85rem', marginBottom: '1rem' }}>
              {error}
            </p>
          )}

          {success && (
            <p style={{ color: 'var(--success)', fontSize: '0.85rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
              <Check size={16} /> Clave guardada correctamente.
            </p>
          )}

          <div style={{ background: 'var(--bg-input)', padding: '0.85rem 1rem', borderRadius: '10px', marginBottom: '1.5rem', fontSize: '0.82rem', color: 'var(--text-muted)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: 'var(--text-main)', fontWeight: 600, marginBottom: '0.3rem' }}>
              <ShieldCheck size={16} color="var(--success)" /> Clave guardada localmente
            </div>
            La clave queda en tu archivo local <code>.env</code>. Las pautas y consultas enviadas a la IA se procesan mediante Gemini. Puedes obtener una clave en:
            <a
              href="https://aistudio.google.com/app/apikey"
              target="_blank"
              rel="noreferrer"
              style={{ color: 'var(--accent)', display: 'inline-flex', alignItems: 'center', gap: '0.2rem', marginLeft: '0.3rem', textDecoration: 'none' }}
            >
              Google AI Studio <ExternalLink size={12} />
            </a>
          </div>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
            <button type="button" className="btn-secondary" onClick={onClose}>
              Cancelar
            </button>
            <button type="submit" className="btn-primary" disabled={saving}>
              {saving ? <div className="spinner" /> : <><Check size={16} /> Guardar Clave</>}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
