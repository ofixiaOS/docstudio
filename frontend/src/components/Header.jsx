import React from 'react';
import { BrainCircuit, FileText, LayoutList, PenLine, Settings, Plus } from 'lucide-react';

export default function Header({ currentStep, setStep, config, onOpenKeyModal, onReset }) {
  const steps = [
    { id: 'upload', label: '1. Inicio / Guía', icon: FileText },
    { id: 'outline', label: '2. Esquema', icon: LayoutList },
    { id: 'editor', label: '3. Editor & Word', icon: PenLine },
  ];

  return (
    <header className="navbar">
      <div className="brand" onClick={onReset} style={{ cursor: 'pointer' }}>
        <div style={{
          width: 34,
          height: 34,
          borderRadius: 10,
          background: 'linear-gradient(135deg, #2563eb, #0284c7)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: '#fff',
          boxShadow: '0 4px 12px rgba(37, 99, 235, 0.4)'
        }}>
          <BrainCircuit size={18} />
        </div>
        <span>DocStudio</span>
        <span className="brand-badge">Local & MCP</span>
      </div>

      <div className="stepper">
        {steps.map((s) => {
          const Icon = s.icon;
          const isActive = currentStep === s.id;
          return (
            <button
              key={s.id}
              className={`step-btn ${isActive ? 'active' : ''}`}
              onClick={() => setStep(s.id)}
            >
              <Icon size={15} />
              <span>{s.label}</span>
            </button>
          );
        })}
      </div>

      <div className="nav-actions">
        <button
          className="btn-secondary"
          onClick={onOpenKeyModal}
          title={`Ajustes de Perfil e IA (${config.model || 'Gemini'})`}
        >
          <Settings size={15} color={config.has_api_key ? 'var(--success)' : 'var(--warning)'} />
          <span>{config.has_api_key ? 'Ajustes' : 'Configurar'}</span>
        </button>

        <button
          className="btn-secondary"
          onClick={onReset}
          title="Nuevo Documento"
        >
          <Plus size={15} />
          <span>Nuevo</span>
        </button>
      </div>
    </header>
  );
}
