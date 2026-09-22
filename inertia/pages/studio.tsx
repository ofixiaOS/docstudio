import { useState } from 'react'
import { Head } from '@inertiajs/react'
import {
  FileText,
  CheckCircle2,
  Cpu,
  Database,
  Layers,
  Sparkles,
  BookOpen,
} from 'lucide-react'
import type { StudioProps } from '#types/page_props/studio'

export default function StudioPage(props: StudioProps) {
  const { currentProject, allProjects, aiModels, selectedModel } = props
  const [activeTab, setActiveTab] = useState<'editor' | 'rubric' | 'memories'>('editor')
  const [currentAiModel, setCurrentAiModel] = useState<string>(selectedModel)

  return (
    <>
      <Head title="Studio - DocStudio" />

      <div className="flex h-screen w-screen overflow-hidden bg-slate-900 text-slate-100 font-sans">
        {/* Barra lateral de Proyectos (Progressive Disclosure) */}
        <aside className="w-64 border-r border-slate-800 bg-slate-950/80 p-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 mb-6">
              <div className="h-8 w-8 rounded-lg bg-blue-600 flex items-center justify-center font-bold text-white shadow-lg shadow-blue-500/30">
                DS
              </div>
              <div>
                <h1 className="text-sm font-bold tracking-tight text-white flex items-center gap-1.5">
                  DocStudio
                  <span className="text-[10px] uppercase font-semibold px-1.5 py-0.5 rounded bg-blue-500/20 text-blue-400 border border-blue-500/30">
                    Local-First
                  </span>
                </h1>
                <p className="text-[11px] text-slate-400">AdonisJS 7 + Sidecar Engine</p>
              </div>
            </div>

            <nav className="space-y-1">
              <button
                type="button"
                onClick={() => setActiveTab('editor')}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                  activeTab === 'editor'
                    ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                }`}
              >
                <FileText className="h-4 w-4" />
                Editor Documental
              </button>

              <button
                type="button"
                onClick={() => setActiveTab('rubric')}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                  activeTab === 'rubric'
                    ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                }`}
              >
                <CheckCircle2 className="h-4 w-4" />
                Rúbrica & Checklist
              </button>

              <button
                type="button"
                onClick={() => setActiveTab('memories')}
                className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                  activeTab === 'memories'
                    ? 'bg-blue-600/20 text-blue-400 border border-blue-500/30'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                }`}
              >
                <BookOpen className="h-4 w-4" />
                Memoria Semántica
              </button>
            </nav>

            <div className="mt-8">
              <h2 className="text-[11px] font-semibold uppercase tracking-wider text-slate-500 px-3 mb-2">
                Proyectos Locales ({allProjects.length})
              </h2>
              <div className="space-y-1 max-h-48 overflow-y-auto">
                {allProjects.map((p) => (
                  <div
                    key={p.id}
                    className={`px-3 py-2 rounded-lg text-xs cursor-pointer truncate ${
                      currentProject?.id === p.id
                        ? 'bg-slate-800 text-white font-medium'
                        : 'text-slate-400 hover:bg-slate-900'
                    }`}
                  >
                    {p.title}
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Estado de Arquitectura Host & Sidecar */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-3 text-[11px] space-y-2">
            <div className="flex items-center justify-between text-slate-400">
              <span className="flex items-center gap-1.5">
                <Layers className="h-3.5 w-3.5 text-blue-400" /> Host:
              </span>
              <span className="font-mono text-emerald-400">AdonisJS 7</span>
            </div>
            <div className="flex items-center justify-between text-slate-400">
              <span className="flex items-center gap-1.5">
                <Cpu className="h-3.5 w-3.5 text-purple-400" /> Sidecar:
              </span>
              <span className="font-mono text-emerald-400">Python 3.12</span>
            </div>
            <div className="flex items-center justify-between text-slate-400">
              <span className="flex items-center gap-1.5">
                <Database className="h-3.5 w-3.5 text-amber-400" /> Storage:
              </span>
              <span className="font-mono text-slate-300">SQLite (WAL)</span>
            </div>
          </div>
        </aside>

        {/* Área Central de Trabajo */}
        <main className="flex-1 flex flex-col overflow-hidden bg-slate-950">
          {/* Header Superior */}
          <header className="h-14 border-b border-slate-800 px-6 flex items-center justify-between bg-slate-900/30 backdrop-blur">
            <div className="flex items-center gap-3">
              <h2 className="text-sm font-semibold text-white">
                {currentProject ? currentProject.title : 'Nuevo Proyecto Técnico'}
              </h2>
              {currentProject?.institution && (
                <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                  {currentProject.institution}
                </span>
              )}
            </div>

            <div className="flex items-center gap-3">
              <div className="flex items-center gap-1.5 text-xs text-slate-400 bg-slate-900 px-2.5 py-1.5 rounded-lg border border-slate-800">
                <Sparkles className="h-3.5 w-3.5 text-purple-400" />
                <span>Modelo:</span>
                <select
                  value={currentAiModel}
                  onChange={(e) => setCurrentAiModel(e.target.value)}
                  className="bg-transparent text-slate-200 font-mono text-xs focus:outline-none cursor-pointer"
                >
                  {aiModels.map((m) => (
                    <option key={m} value={m} className="bg-slate-900 text-slate-200">
                      {m}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </header>

          {/* Contenido Principal */}
          <div className="flex-1 overflow-y-auto p-8">
            <div className="max-w-4xl mx-auto space-y-6">
              {/* Banner de Garantía Factual y Anti-Slop (Regla de Oro OFIXIA) */}
              <div className="rounded-xl border border-blue-900/40 bg-blue-950/20 p-4 flex items-start gap-3">
                <CheckCircle2 className="h-5 w-5 text-blue-400 shrink-0 mt-0.5" />
                <div>
                  <h3 className="text-xs font-semibold text-blue-200">
                    Protocolo de Grounding Factual Activo
                  </h3>
                  <p className="text-xs text-blue-300/80 mt-0.5 leading-relaxed">
                    Toda afirmación técnica debe anclarse en archivos de evidencia reales o fuentes catalogadas.
                    Los requisitos no sustentados se marcan explícitamente con{' '}
                    <code className="bg-blue-950 px-1 py-0.5 rounded text-blue-200 font-mono text-[11px]">
                      EVIDENCIA PENDIENTE
                    </code>.
                  </p>
                </div>
              </div>

              {/* Contenedor del Editor */}
              <div className="rounded-2xl border border-slate-800 bg-slate-900/40 p-6 min-h-[500px]">
                <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-6">
                  <div>
                    <h3 className="text-base font-semibold text-white">Documento Principal</h3>
                    <p className="text-xs text-slate-400">
                      Soporta jerarquía completa de títulos (H1-H6) y exportación DOCX fiel.
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow transition-all"
                    >
                      Exportar DOCX
                    </button>
                  </div>
                </div>

                <div className="prose prose-invert max-w-none text-slate-300 text-sm">
                  <p className="leading-relaxed">
                    Bienvenido a <strong>DocStudio</strong>. El entorno host en{' '}
                    <span className="text-blue-400 font-semibold">AdonisJS 7</span> está activo y conectado al motor de cómputo en{' '}
                    <span className="text-purple-400 font-semibold">Python</span> mediante el protocolo de sidecar local.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </main>
      </div>
    </>
  )
}
