import { Sparkles, Plus, Trash2, Code2, Image as ImageIcon, ArrowLeft, CheckCircle, PackageCheck, PenLine } from 'lucide-react';

export default function OutlineView({
  analysisData,
  setAnalysisData,
  onUpdateOutline,
  onGenerate,
  onContinueOffline,
  onBack,
  generating
}) {
  const { title, subject, summary, key_requirements, deliverables = [], criteria = [], outline } = analysisData;

  const handleUpdateCard = (index, field, value) => {
    const updated = [...outline];
    updated[index] = { ...updated[index], [field]: value };
    if (onUpdateOutline) {
      onUpdateOutline(updated);
    } else {
      setAnalysisData({ ...analysisData, outline: updated });
    }
  };

  const handleDeleteCard = (index) => {
    if (outline.length <= 1) {
      alert('Debes mantener al menos una sección.');
      return;
    }
    const updated = outline.filter((_, i) => i !== index);
    if (onUpdateOutline) {
      onUpdateOutline(updated);
    } else {
      setAnalysisData({ ...analysisData, outline: updated });
    }
  };

  const handleAddCard = () => {
    const newId = `sec-${Date.now()}`;
    const newCard = {
      id: newId,
      title: `${outline.length + 1}. Nueva Sección de Desarrollo`,
      description: 'Detalle de los requerimientos y respuestas para esta sección.',
      type: 'development',
      needs_code: false,
      needs_evidence: false,
    };
    // Insertar antes de conclusión o al final
    const conclusionIdx = outline.findIndex((c) => c.type === 'conclusion');
    let updated;
    if (conclusionIdx !== -1) {
      updated = [...outline.slice(0, conclusionIdx), newCard, ...outline.slice(conclusionIdx)];
    } else {
      updated = [...outline, newCard];
    }
    if (onUpdateOutline) {
      onUpdateOutline(updated);
    } else {
      setAnalysisData({ ...analysisData, outline: updated });
    }
  };

  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      {/* Header del Esquema */}
      <div className="outline-header">
        <div>
          <button
            onClick={onBack}
            className="btn-secondary"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', marginBottom: '0.75rem', padding: '0.35rem 0.7rem' }}
          >
            <ArrowLeft size={14} /> Volver a Pauta
          </button>
          <h1 style={{ fontSize: '1.85rem', fontWeight: 800, letterSpacing: '-0.02em', color: 'var(--text-main)' }}>
            Esquema del Documento (Tipo Gamma)
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginTop: '0.2rem' }}>
            Revisa las tarjetas generadas según la pauta. Puedes renombrar títulos, agregar o quitar secciones antes de redactar.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.6rem', alignItems: 'center' }}>
          {onContinueOffline && (
            <button
              type="button"
              className="btn-secondary"
              onClick={onContinueOffline}
              disabled={generating}
              title="Abrir editor con este esquema sin redactar con IA"
              style={{ padding: '0.75rem 1.2rem', fontSize: '0.95rem' }}
            >
              <PenLine size={16} />
              <span>Continuar al Editor</span>
            </button>
          )}
          <button
            className="btn-primary"
            onClick={onGenerate}
            disabled={generating}
            style={{ padding: '0.75rem 1.6rem', fontSize: '0.95rem' }}
          >
            {generating ? (
              <>
                <div className="spinner" />
                <span>Redactando Informe...</span>
              </>
            ) : (
              <>
                <Sparkles size={18} />
                <span>Generar con IA</span>
              </>
            )}
          </button>
        </div>
      </div>

      {deliverables.length > 0 && (
        <section className="deliverables-strip">
          <div className="section-label"><PackageCheck size={15} /> Paquete de entrega detectado</div>
          <div className="deliverable-list">
            {deliverables.map((item) => <span key={item}>{item}</span>)}
          </div>
        </section>
      )}

      {/* Tarjeta de Metadatos Detectados */}
      <div className="outline-meta-card">
        <div>
          <div style={{ display: 'inline-block', background: 'rgba(59, 130, 246, 0.15)', color: 'var(--accent)', fontSize: '0.75rem', fontWeight: 700, padding: '0.2rem 0.6rem', borderRadius: 6, marginBottom: '0.4rem' }}>
            {subject || 'Asignatura / Área'}
          </div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.4rem' }}>
            {title || 'Evaluación Académica'}
          </h2>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', maxWidth: 680 }}>
            {summary}
          </p>
        </div>
      </div>

      {/* Requisitos clave detectados */}
      {((criteria && criteria.length > 0) || (key_requirements && key_requirements.length > 0)) && (
        <div style={{ background: 'var(--bg-sidebar)', border: '1px solid var(--border)', borderRadius: 12, padding: '1rem 1.25rem', marginBottom: '1.75rem' }}>
          <div style={{ fontSize: '0.8rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
            Criterios de Evaluación Identificados en la Pauta:
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
            {(criteria.length ? criteria : key_requirements).map((item, idx) => (
              <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', color: 'var(--text-main)' }}>
                <CheckCircle size={14} color="var(--success)" style={{ flexShrink: 0 }} />
                <span>{typeof item === 'string' ? item : item.indicator}</span>
                {typeof item !== 'string' && item.points != null && <strong className="points-badge">{item.points} pts</strong>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Lista de Tarjetas Estilo Gamma */}
      <div className="cards-container">
        {outline.map((card, idx) => (
          <div key={card.id || idx} className="outline-card-item">
            <div className="card-number">{idx + 1}</div>

            <div className="card-body">
              <input
                type="text"
                className="card-title-input"
                value={card.title}
                onChange={(e) => handleUpdateCard(idx, 'title', e.target.value)}
                placeholder="Título de la sección..."
              />
              <textarea
                className="card-desc-input"
                rows={2}
                value={card.description}
                onChange={(e) => handleUpdateCard(idx, 'description', e.target.value)}
                placeholder="¿Qué responder o demostrar en esta sección?"
              />

              <div className="card-badges">
                <button
                  type="button"
                  className={`badge ${card.needs_code ? 'badge-code' : ''}`}
                  onClick={() => handleUpdateCard(idx, 'needs_code', !card.needs_code)}
                  style={{ cursor: 'pointer', background: card.needs_code ? undefined : 'var(--bg-input)', border: '1px solid var(--border)', color: card.needs_code ? undefined : 'var(--text-dim)' }}
                >
                  <Code2 size={12} /> Requiere Código
                </button>

                <button
                  type="button"
                  className={`badge ${card.needs_evidence ? 'badge-evidence' : ''}`}
                  onClick={() => handleUpdateCard(idx, 'needs_evidence', !card.needs_evidence)}
                  style={{ cursor: 'pointer', background: card.needs_evidence ? undefined : 'var(--bg-input)', border: '1px solid var(--border)', color: card.needs_evidence ? undefined : 'var(--text-dim)' }}
                >
                  <ImageIcon size={12} /> Requiere Captura / Evidencia
                </button>
              </div>
            </div>

            <button
              onClick={() => handleDeleteCard(idx)}
              style={{ background: 'transparent', border: 'none', color: 'var(--text-dim)', cursor: 'pointer', padding: '0.4rem', borderRadius: 6 }}
              title="Eliminar tarjeta"
            >
              <Trash2 size={16} />
            </button>
          </div>
        ))}

        {/* Botón Agregar Tarjeta */}
        <button
          onClick={handleAddCard}
          className="btn-secondary"
          style={{ width: '100%', justifyContent: 'center', padding: '0.9rem', borderStyle: 'dashed', borderRadius: 14 }}
        >
          <Plus size={16} /> Agregar Nueva Sección al Informe
        </button>
      </div>

      {/* Botón inferior fijo/de acción */}
      <div style={{ display: 'flex', justifyContent: 'center', gap: '1rem', flexWrap: 'wrap', margin: '3rem 0 2rem' }}>
        {onContinueOffline && (
          <button
            type="button"
            className="btn-secondary"
            onClick={onContinueOffline}
            disabled={generating}
            style={{ padding: '0.9rem 2rem', fontSize: '1.05rem', borderRadius: 12 }}
          >
            <PenLine size={18} />
            <span>Continuar al Editor (sin IA)</span>
          </button>
        )}
        <button
          className="btn-primary"
          onClick={onGenerate}
          disabled={generating}
          style={{ padding: '0.9rem 2.5rem', fontSize: '1.05rem', borderRadius: 12 }}
        >
          {generating ? (
            <>
              <div className="spinner" />
              <span>Redactando Informe Completo con IA...</span>
            </>
          ) : (
            <>
              <Sparkles size={20} />
              <span>Generar Documento con IA</span>
            </>
          )}
        </button>
      </div>
    </div>
  );
}
