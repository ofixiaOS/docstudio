import React, { useMemo, useRef, useState } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Highlight from '@tiptap/extension-highlight';
import Placeholder from '@tiptap/extension-placeholder';
import Image from '@tiptap/extension-image';
import {
  Bold, Italic, Heading1, Heading2, Heading3, List, ListOrdered, Quote, Code,
  FileDown, Printer, Wand2, Undo, Redo, Sparkles, Save, ImagePlus, BookOpenCheck,
  MessageSquareText, Paperclip, Send, CircleCheck, CircleDashed, TriangleAlert,
  History, RotateCcw, X,
} from 'lucide-react';

const TABS = [
  { id: 'rubric', label: 'Pauta', icon: BookOpenCheck },
  { id: 'chat', label: 'Copiloto', icon: MessageSquareText },
  { id: 'sources', label: 'Fuentes', icon: Paperclip },
];

export default function EditorView({
  docData, projectData, analysisData, messages, versions = [], auditResult, savingState,
  onDocumentChange, onSnapshot, onRestoreVersion, onExportDocx, exporting, onRefineText, refining,
  onChat, chatting, onAudit, auditing, onUploadEvidence, onUploadSources,
}) {
  const [aiPrompt, setAiPrompt] = useState('');
  const [chatPrompt, setChatPrompt] = useState('');
  const [activeTab, setActiveTab] = useState('rubric');
  const [uploading, setUploading] = useState(false);
  const [isVersionModalOpen, setIsVersionModalOpen] = useState(false);
  const evidenceInputRef = useRef(null);
  const sourceInputRef = useRef(null);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({ heading: { levels: [1, 2, 3] } }),
      Highlight,
      Image.configure({ inline: false, allowBase64: false }),
      Placeholder.configure({ placeholder: 'Redacta aquí o trabaja con el copiloto…' }),
    ],
    content: docData?.html_content || '<h1>Introducción</h1><p>Documento listo para redactar.</p>',
    onUpdate: ({ editor: currentEditor }) => onDocumentChange(currentEditor.getHTML()),
  }, [docData?.project_id]);

  const criteria = projectData?.criteria || analysisData?.criteria || [];
  const sources = projectData?.sources || [];
  const evidence = projectData?.evidence || [];
  const auditById = useMemo(() => Object.fromEntries((auditResult?.items || []).map((item) => [item.criterion_id, item])), [auditResult]);

  if (!editor) return null;

  const text = editor.getText();
  const wordCount = text.trim() ? text.trim().split(/\s+/).length : 0;
  const readTimeMin = Math.max(1, Math.ceil(wordCount / 200));

  const applyAi = async (instruction) => {
    const { from, to } = editor.state.selection;
    const selected = editor.state.doc.textBetween(from, to, ' ');
    const targetText = selected.trim().length > 5 ? selected : editor.getText().slice(-1800);
    const refined = await onRefineText(targetText, instruction || aiPrompt);
    if (!refined) return;
    if (selected.trim().length > 5) editor.chain().focus().deleteSelection().insertContent(refined).run();
    else editor.chain().focus().insertContent(refined).run();
    setAiPrompt('');
  };

  const sendChat = async () => {
    const message = chatPrompt.trim();
    if (!message) return;
    setChatPrompt('');
    await onChat(message, editor.getText().slice(-12000));
  };

  const uploadEvidence = async (file) => {
    if (!file) return;
    const caption = window.prompt('¿Qué demuestra esta captura?', file.name) || file.name;
    setUploading(true);
    try {
      const result = await onUploadEvidence(file, caption);
      editor.chain().focus().setImage({ src: result.url, alt: caption, title: caption }).run();
      editor.chain().focus().insertContent(`<p><em>Figura: ${caption}</em></p>`).run();
    } finally {
      setUploading(false);
      if (evidenceInputRef.current) evidenceInputRef.current.value = '';
    }
  };

  const uploadSources = async (files) => {
    if (!files?.length) return;
    setUploading(true);
    try {
      await onUploadSources(files);
    } finally {
      setUploading(false);
      if (sourceInputRef.current) sourceInputRef.current.value = '';
    }
  };

  return (
    <div className="editor-layout">
      <section className="editor-main">
        <div className="editor-actionbar">
          <div className="document-stats">
            <span><strong>{wordCount}</strong> palabras</span>
            <span>{readTimeMin} min</span>
            <span className={`save-state ${savingState === 'error' ? 'error' : ''}`}>
              {savingState === 'saving' ? 'Guardando…' : savingState === 'error' ? 'Error al guardar' : `Guardado ${savingState.startsWith('v') ? savingState : ''}`}
            </span>
          </div>
          <div className="action-group">
            <button className="btn-secondary" onClick={() => onSnapshot(editor.getHTML())} title="Guardar snapshot"><Save size={15} /> Versión</button>
            <button className="btn-secondary" onClick={() => setIsVersionModalOpen(true)} title="Historial de versiones"><History size={15} /> Historial ({versions.length})</button>
            <button className="btn-secondary" onClick={() => window.print()}><Printer size={15} /> PDF</button>
            <button className="btn-primary" onClick={() => onExportDocx(editor.getHTML())} disabled={exporting}>
              {exporting ? <div className="spinner" /> : <FileDown size={16} />} Word
            </button>
          </div>
        </div>

        <div className="editor-toolbar">
          <button onClick={() => editor.chain().focus().toggleBold().run()} className={`toolbar-btn ${editor.isActive('bold') ? 'is-active' : ''}`} title="Negrita"><Bold size={16} /></button>
          <button onClick={() => editor.chain().focus().toggleItalic().run()} className={`toolbar-btn ${editor.isActive('italic') ? 'is-active' : ''}`} title="Cursiva"><Italic size={16} /></button>
          <div className="toolbar-divider" />
          {[1, 2, 3].map((level) => {
            const Icon = [Heading1, Heading2, Heading3][level - 1];
            return <button key={level} onClick={() => editor.chain().focus().toggleHeading({ level }).run()}
              className={`toolbar-btn ${editor.isActive('heading', { level }) ? 'is-active' : ''}`} title={`Título ${level}`}><Icon size={17} /></button>;
          })}
          <div className="toolbar-divider" />
          <button onClick={() => editor.chain().focus().toggleBulletList().run()} className={`toolbar-btn ${editor.isActive('bulletList') ? 'is-active' : ''}`} title="Lista"><List size={16} /></button>
          <button onClick={() => editor.chain().focus().toggleOrderedList().run()} className={`toolbar-btn ${editor.isActive('orderedList') ? 'is-active' : ''}`} title="Lista numerada"><ListOrdered size={16} /></button>
          <button onClick={() => editor.chain().focus().toggleBlockquote().run()} className={`toolbar-btn ${editor.isActive('blockquote') ? 'is-active' : ''}`} title="Evidencia o cita"><Quote size={16} /></button>
          <button onClick={() => editor.chain().focus().toggleCodeBlock().run()} className={`toolbar-btn ${editor.isActive('codeBlock') ? 'is-active' : ''}`} title="Código"><Code size={16} /></button>
          <button onClick={() => evidenceInputRef.current?.click()} className="toolbar-btn" title="Insertar captura"><ImagePlus size={17} /></button>
          <input ref={evidenceInputRef} type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={(event) => uploadEvidence(event.target.files?.[0])} />
          <div className="toolbar-divider" />
          <button onClick={() => editor.chain().focus().undo().run()} disabled={!editor.can().undo()} className="toolbar-btn" title="Deshacer"><Undo size={15} /></button>
          <button onClick={() => editor.chain().focus().redo().run()} disabled={!editor.can().redo()} className="toolbar-btn" title="Rehacer"><Redo size={15} /></button>
        </div>

        <article className="document-page" id="printable-document">
          <header className="document-cover-inline">
            <div className="document-institution">INSTITUTO PROFESIONAL IPLACEX</div>
            <h1>{docData?.title || analysisData?.title || 'Evaluación Académica'}</h1>
            <p>Asignatura: {docData?.subject || analysisData?.subject || 'General'}</p>
            <span>Estudiante: {docData?.student || 'Nicolás Javier Jara Guzmán'}</span>
          </header>
          <EditorContent editor={editor} />
        </article>

        <div className="floating-ai-bar">
          <Wand2 size={18} />
          <input className="ai-input" placeholder="Mejora la selección o amplía el último bloque…" value={aiPrompt}
            onChange={(event) => setAiPrompt(event.target.value)} onKeyDown={(event) => {
              if (event.key === 'Enter' && aiPrompt.trim()) applyAi(aiPrompt);
            }} />
          <button className="btn-primary compact" onClick={() => applyAi(aiPrompt)} disabled={refining || !aiPrompt.trim()}>
            {refining ? <div className="spinner" /> : <><Sparkles size={14} /> Aplicar</>}
          </button>
        </div>
      </section>

      <aside className="copilot-panel">
        <div className="copilot-tabs">
          {TABS.map(({ id, label, icon: Icon }) => (
            <button key={id} className={activeTab === id ? 'active' : ''} onClick={() => setActiveTab(id)}>
              <Icon size={14} /> {label}
            </button>
          ))}
        </div>

        {activeTab === 'rubric' && (
          <div className="panel-content">
            <div className="panel-heading">
              <div><span className="eyebrow">Control de calidad</span><h3>Criterios de evaluación</h3></div>
              <button className="btn-primary compact" onClick={() => onAudit(editor.getHTML())} disabled={auditing}>
                {auditing ? <div className="spinner" /> : <BookOpenCheck size={14} />} Auditar
              </button>
            </div>
            {auditResult && <div className="score-summary"><strong>{Math.round(auditResult.estimated_score)}%</strong><span>{auditResult.summary}</span></div>}
            <div className="criterion-list">
              {criteria.map((criterion) => {
                const result = auditById[criterion.id];
                const status = result?.status || criterion.status || 'pending';
                const StatusIcon = status === 'complete' ? CircleCheck : status === 'partial' ? TriangleAlert : CircleDashed;
                return (
                  <div className={`criterion-item ${status}`} key={criterion.id}>
                    <StatusIcon size={16} />
                    <div><strong>{criterion.indicator}</strong>
                      <span>{criterion.points != null ? `${criterion.points} puntos` : 'Sin puntaje explícito'}{criterion.requires_evidence ? ' · requiere captura' : ''}</span>
                      {(result?.feedback || criterion.feedback) && <p>{result?.feedback || criterion.feedback}</p>}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {activeTab === 'chat' && (
          <div className="panel-content chat-panel">
            <div className="message-list">
              {messages.length === 0 && <p className="panel-empty">Pregunta por la pauta, las fuentes o qué falta. El historial queda guardado.</p>}
              {messages.map((message) => <div key={message.id} className={`chat-message ${message.role}`}>{message.content}</div>)}
            </div>
            <div className="chat-composer">
              <textarea placeholder="¿Qué falta para cumplir la pauta?" value={chatPrompt} onChange={(event) => setChatPrompt(event.target.value)}
                onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendChat(); } }} />
              <button onClick={sendChat} disabled={chatting || !chatPrompt.trim()}>{chatting ? <div className="spinner" /> : <Send size={16} />}</button>
            </div>
          </div>
        )}

        {activeTab === 'sources' && (
          <div className="panel-content">
            <div className="panel-heading"><div><span className="eyebrow">RAG del proyecto</span><h3>Fuentes y evidencias</h3></div></div>
            <button className="source-drop" onClick={() => sourceInputRef.current?.click()} disabled={uploading}>
              <Paperclip size={17} /><strong>Adjuntar material de estudio</strong><span>PDF, DOCX, TXT o código</span>
            </button>
            <input ref={sourceInputRef} type="file" multiple hidden accept=".pdf,.docx,.txt,.md,.csv,.sql,.py,.java,.cs" onChange={(event) => uploadSources(event.target.files)} />
            <div className="source-list">
              {sources.map((source) => <div key={source.id}><BookOpenCheck size={14} /><span><strong>{source.filename}</strong><small>{source.kind}</small></span></div>)}
            </div>
            <h4>Capturas insertadas ({evidence.length})</h4>
            <div className="source-list">
              {evidence.map((item) => <div key={item.id}><ImagePlus size={14} /><span><strong>{item.filename}</strong><small>{item.caption}</small></span></div>)}
            </div>
          </div>
        )}
      </aside>

      {isVersionModalOpen && (
        <div className="modal-backdrop" onClick={() => setIsVersionModalOpen(false)}>
          <div className="modal-card" style={{ maxWidth: 580 }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                <div style={{ background: 'rgba(59, 130, 246, 0.15)', padding: '0.5rem', borderRadius: '10px', color: 'var(--accent)' }}>
                  <History size={20} />
                </div>
                <div>
                  <h3 style={{ fontSize: '1.15rem', fontWeight: 700 }}>Historial de Versiones</h3>
                  <p style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                    Restaura cualquier punto de guardado previo del documento.
                  </p>
                </div>
              </div>
              <button onClick={() => setIsVersionModalOpen(false)} style={{ background: 'transparent', border: 'none', color: 'var(--text-dim)', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '380px', overflowY: 'auto', marginBottom: '1.25rem' }}>
              {versions.length === 0 ? (
                <p style={{ textAlign: 'center', color: 'var(--text-dim)', padding: '2rem 0', fontSize: '0.9rem' }}>
                  No hay versiones guardadas todavía. Haz clic en "Versión" para crear la primera.
                </p>
              ) : (
                versions.map((v) => (
                  <div key={v.id || v.version_number} style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    padding: '10px 14px', border: '1px solid var(--border)', borderRadius: '10px',
                    background: 'var(--bg-input)'
                  }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '3px' }}>
                        <strong style={{ color: 'var(--text-main)', fontSize: '0.95rem' }}>Versión {v.version_number}</strong>
                        <span className="brand-badge" style={{ fontSize: '10px', textTransform: 'uppercase' }}>{v.reason}</span>
                      </div>
                      <span style={{ fontSize: '0.78rem', color: 'var(--text-dim)' }}>
                        {new Date(v.created_at).toLocaleString('es-CL')} · {(v.size / 1024).toFixed(1)} KB
                      </span>
                    </div>

                    <button
                      className="btn-primary compact"
                      onClick={async () => {
                        if (window.confirm(`¿Seguro que deseas restaurar la Versión ${v.version_number}? Se creará un nuevo snapshot con tu contenido actual antes de restaurar.`)) {
                          const restored = await onRestoreVersion(v.version_number);
                          if (restored) {
                            editor.commands.setContent(restored);
                            setIsVersionModalOpen(false);
                          }
                        }
                      }}
                      title="Restaurar este contenido en el editor"
                    >
                      <RotateCcw size={13} /> Restaurar
                    </button>
                  </div>
                ))
              )}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button className="btn-secondary" onClick={() => setIsVersionModalOpen(false)}>
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

