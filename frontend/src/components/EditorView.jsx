import React, { useMemo, useRef, useState } from 'react';
import { useEditor, EditorContent } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import Highlight from '@tiptap/extension-highlight';
import Placeholder from '@tiptap/extension-placeholder';
import Image from '@tiptap/extension-image';
import { Table, TableRow, TableHeader, TableCell } from '@tiptap/extension-table';
import {
  Bold, Italic, Heading1, Heading2, Heading3, List, ListOrdered, Quote, Code,
  FileDown, Printer, Wand2, Undo, Redo, Sparkles, Save, ImagePlus, BookOpenCheck,
  MessageSquareText, Paperclip, Send, CircleCheck, CircleDashed, TriangleAlert,
  History, RotateCcw, X, BrainCircuit, Trash2, Plus, Upload, Archive,
  Table as TableIcon, Rows3, Columns3, PackageCheck,
} from 'lucide-react';

const TABS = [
  { id: 'rubric', label: 'Pauta', icon: BookOpenCheck },
  { id: 'chat', label: 'Copiloto', icon: MessageSquareText },
  { id: 'memories', label: 'Memoria', icon: BrainCircuit },
  { id: 'sources', label: 'Fuentes', icon: Paperclip },
];

export default function EditorView({
  docData, projectData, analysisData, messages, versions = [], auditResult, savingState,
  memories = [], onAddMemory, onDeleteMemory, config,
  onDocumentChange, onSnapshot, onRestoreVersion, onExportDocx, exporting, onRefineText, refining,
  onChat, chatting, onAudit, auditing, onUploadEvidence, onUploadSources,
  onDeleteSource, onDeleteEvidence,
  onRegenerateSection, regeneratingSection,
  onExportPackage, exportingPackage,
}) {
  const [aiPrompt, setAiPrompt] = useState('');
  const [chatPrompt, setChatPrompt] = useState('');
  const [activeTab, setActiveTab] = useState('rubric');
  const [uploading, setUploading] = useState(false);
  const [isVersionModalOpen, setIsVersionModalOpen] = useState(false);
  const [evidenceModalFile, setEvidenceModalFile] = useState(null);
  const [evidenceCaption, setEvidenceCaption] = useState('');
  const [evidenceCriterionId, setEvidenceCriterionId] = useState('');
  const [enableWatermark, setEnableWatermark] = useState(true);
  const [watermarkCustomText, setWatermarkCustomText] = useState('');
  const [memoryContent, setMemoryContent] = useState('');
  const [memoryKind, setMemoryKind] = useState('preference');
  const [savingMemory, setSavingMemory] = useState(false);
  const evidenceInputRef = useRef(null);
  const sourceInputRef = useRef(null);

  const handleEvidenceFileSelected = (file) => {
    if (!file) return;
    setEvidenceModalFile(file);
    const baseName = file.name ? file.name.replace(/\.[^/.]+$/, '').replace(/[-_]/g, ' ') : '';
    const caption = (baseName && !/^image(\d+)?$/i.test(baseName.trim()))
      ? baseName
      : `Captura ${new Date().toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' })}`;
    setEvidenceCaption(caption);
    setEvidenceCriterionId('');
    const author = projectData?.student || docData?.student || config?.default_student || 'Autor';
    const inst = projectData?.institution || docData?.institution || config?.default_institution || '';
    setWatermarkCustomText(inst ? `${author} - ${inst}` : author);
  };

  const editor = useEditor({
    extensions: [
      StarterKit.configure({ heading: { levels: [1, 2, 3] } }),
      Highlight,
      Image.configure({ inline: false, allowBase64: false }),
      Table.configure({ resizable: true }),
      TableRow,
      TableHeader,
      TableCell,
      Placeholder.configure({ placeholder: 'Redacta aquí o trabaja con el copiloto…' }),
    ],
    editorProps: {
      handlePaste: (_view, event) => {
        const items = event.clipboardData?.items;
        if (!items) return false;
        for (let i = 0; i < items.length; i++) {
          const item = items[i];
          if (item.type && item.type.startsWith('image/')) {
            const file = item.getAsFile();
            if (file) {
              event.preventDefault();
              handleEvidenceFileSelected(file);
              return true;
            }
          }
        }
        return false;
      },
    },
    content: docData?.html_content || '<h1>Introducción</h1><p>Documento listo para redactar.</p>',
    onUpdate: ({ editor: currentEditor }) => onDocumentChange(currentEditor.getHTML()),
  }, [docData?.project_id]);

  const outline = projectData?.outline || analysisData?.outline || [];
  const criteria = projectData?.criteria || analysisData?.criteria || [];
  const deliverables = projectData?.deliverables || analysisData?.deliverables || [];
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
    if (selected.trim().length < 5) {
      alert('Por favor selecciona en el documento el texto específico que deseas mejorar con IA.');
      return;
    }
    const refined = await onRefineText(selected, instruction || aiPrompt);
    if (!refined) return;
    editor.chain().focus().deleteSelection().insertContent(refined).run();
    setAiPrompt('');
  };

  const sendChat = async () => {
    const message = chatPrompt.trim();
    if (!message) return;
    setChatPrompt('');
    await onChat(message, editor.getText().slice(-12000));
  };

  const confirmUploadEvidence = async () => {
    if (!evidenceModalFile) return;
    setUploading(true);
    try {
      const caption = evidenceCaption.trim() || evidenceModalFile.name;
      const result = await onUploadEvidence(
        evidenceModalFile,
        caption,
        evidenceCriterionId,
        enableWatermark,
        watermarkCustomText.trim(),
      );
      editor.chain().focus().setImage({ src: result.url, alt: caption, title: caption }).run();
      editor.chain().focus().insertContent(`<p><em>Figura: ${caption}</em></p>`).run();
      setEvidenceModalFile(null);
      setEvidenceCaption('');
      setEvidenceCriterionId('');
    } finally {
      setUploading(false);
      if (evidenceInputRef.current) evidenceInputRef.current.value = '';
    }
  };

  const handleCreateMemory = async (e) => {
    e?.preventDefault();
    if (!memoryContent.trim() || savingMemory) return;
    setSavingMemory(true);
    try {
      await onAddMemory?.({ kind: memoryKind, content: memoryContent.trim() });
      setMemoryContent('');
    } finally {
      setSavingMemory(false);
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
            <button
              className="btn-secondary"
              onClick={() => onExportPackage?.(editor.getHTML())}
              disabled={exportingPackage}
              title="Descargar paquete completo (.zip con informe Word, código y capturas de evidencia)"
            >
              {exportingPackage ? <div className="spinner" /> : <Archive size={15} />} Entrega (.zip)
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
          <div className="toolbar-divider" />
          <button
            onClick={() => editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run()}
            className={`toolbar-btn ${editor.isActive('table') ? 'is-active' : ''}`}
            title="Insertar tabla (3x3 con encabezado)"
          >
            <TableIcon size={16} />
          </button>
          {editor.isActive('table') && (
            <>
              <button
                onClick={() => editor.chain().focus().addRowAfter().run()}
                className="toolbar-btn"
                title="Agregar fila después"
              >
                <Rows3 size={15} />
              </button>
              <button
                onClick={() => editor.chain().focus().addColumnAfter().run()}
                className="toolbar-btn"
                title="Agregar columna después"
              >
                <Columns3 size={15} />
              </button>
              <button
                onClick={() => editor.chain().focus().deleteTable().run()}
                className="toolbar-btn"
                title="Eliminar tabla"
                style={{ color: '#ef4444' }}
              >
                <Trash2 size={15} />
              </button>
            </>
          )}
          <div className="toolbar-divider" />
          <button onClick={() => evidenceInputRef.current?.click()} className="toolbar-btn" title="Insertar captura"><ImagePlus size={17} /></button>
          <input ref={evidenceInputRef} type="file" accept="image/png,image/jpeg,image/webp" hidden onChange={(event) => handleEvidenceFileSelected(event.target.files?.[0])} />
          <div className="toolbar-divider" />
          <button onClick={() => editor.chain().focus().undo().run()} disabled={!editor.can().undo()} className="toolbar-btn" title="Deshacer"><Undo size={15} /></button>
          <button onClick={() => editor.chain().focus().redo().run()} disabled={!editor.can().redo()} className="toolbar-btn" title="Rehacer"><Redo size={15} /></button>
        </div>

        <article className="document-page" id="printable-document">
          <header className="document-cover-inline">
            {(docData?.institution || projectData?.institution || config?.default_institution) && (
              <div className="document-institution">
                {docData?.institution || projectData?.institution || config?.default_institution}
              </div>
            )}
            <h1>{docData?.title || analysisData?.title || 'Documento de Trabajo'}</h1>
            <p>Tema / Asignatura: {docData?.subject || analysisData?.subject || 'General'}</p>
            <span>Autor: {docData?.student || projectData?.student || config?.default_student || 'Autor'}</span>
            {(docData?.career || projectData?.career || config?.default_career) && (
              <span style={{ marginLeft: '12px' }}>· {docData?.career || projectData?.career || config?.default_career}</span>
            )}
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
              <div><span className="eyebrow">Estructura y Cobertura</span><h3>Lista de Verificación</h3></div>
              <button className="btn-primary compact" onClick={() => onAudit(editor.getHTML())} disabled={auditing}>
                {auditing ? <div className="spinner" /> : <BookOpenCheck size={14} />} Auditar
              </button>
            </div>
            {auditResult && (
              <div className="score-summary">
                <strong>{Math.round(auditResult.estimated_score)}%</strong>
                <span>{auditResult.summary}</span>
              </div>
            )}

            {deliverables.length > 0 && (
              <div style={{ marginBottom: '1.25rem' }}>
                <h4 style={{ fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-dim)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <PackageCheck size={14} /> Entregables Requeridos ({deliverables.length})
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {deliverables.map((item, idx) => (
                    <div key={idx} style={{
                      display: 'flex', alignItems: 'flex-start', gap: '8px',
                      padding: '8px 10px', background: 'var(--bg-input)', borderRadius: '8px',
                      border: '1px solid var(--border)', fontSize: '0.85rem'
                    }}>
                      <CircleCheck size={15} style={{ color: 'var(--accent)', marginTop: '2px', flexShrink: 0 }} />
                      <span style={{ color: 'var(--text-main)', lineHeight: '1.3' }}>{item}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {outline.length > 0 && (
              <div style={{ marginBottom: '1.5rem' }}>
                <h4 style={{ fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-dim)', marginBottom: '0.5rem' }}>
                  Secciones del Trabajo ({outline.length})
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  {outline.map((sec) => (
                    <div key={sec.id || sec.title} style={{
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '8px 10px', background: 'var(--bg-input)', borderRadius: '8px',
                      border: '1px solid var(--border)', fontSize: '0.85rem'
                    }}>
                      <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginRight: '8px' }}>
                        <strong style={{ color: 'var(--text-main)', display: 'block' }}>{sec.title}</strong>
                        <small style={{ color: 'var(--text-dim)', fontSize: '0.75rem' }}>{sec.description?.slice(0, 40)}{sec.description?.length > 40 ? '…' : ''}</small>
                      </div>
                      <button
                        className="btn-secondary compact"
                        style={{ fontSize: '0.75rem', padding: '4px 8px', flexShrink: 0 }}
                        onClick={async () => {
                          if (onRegenerateSection) {
                            const res = await onRegenerateSection(sec.title, '', editor.getHTML());
                            if (res?.html_content) {
                              editor.commands.setContent(res.html_content);
                            }
                          }
                        }}
                        disabled={regeneratingSection === sec.title}
                        title="Regenerar esta sección con IA"
                      >
                        {regeneratingSection === sec.title ? (
                          <div className="spinner" style={{ width: 12, height: 12 }} />
                        ) : (
                          <Wand2 size={12} />
                        )}
                        <span>{regeneratingSection === sec.title ? 'Regenerando…' : 'Regenerar'}</span>
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <h4 style={{ fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-dim)', marginBottom: '0.5rem' }}>
              Criterios de Pauta ({criteria.length})
            </h4>
            <div className="criterion-list">
              {criteria.map((criterion) => {
                const result = auditById[criterion.id];
                const status = result?.status || criterion.status || 'pending';
                const StatusIcon = status === 'complete' ? CircleCheck : status === 'partial' ? TriangleAlert : CircleDashed;
                return (
                  <div className={`criterion-item ${status}`} key={criterion.id}>
                    <StatusIcon size={16} />
                    <div>
                      <strong>{criterion.indicator}</strong>
                      <span>{criterion.points != null ? `${criterion.points} pts` : 'Criterio sugerido'}{criterion.requires_evidence ? ' · requiere captura' : ''}</span>
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
              {messages.length === 0 && (
                <p className="panel-empty">
                  Pregunta por la pauta, fuentes o qué falta. El copiloto recuerda preferencias y acuerdos en memoria de largo plazo.
                </p>
              )}
              {messages.map((message) => (
                <div key={message.id} className={`chat-message ${message.role}`}>
                  <div>{message.content}</div>
                  {message.suggested_actions && message.suggested_actions.length > 0 && (
                    <div className="suggested-actions">
                      <span className="suggested-actions-label">Sugerencias:</span>
                      <div className="suggested-actions-btns">
                        {message.suggested_actions.map((act, i) => (
                          <button
                            key={i}
                            className="btn-action-insert"
                            onClick={() => {
                              if (act.tool === 'replace_selection' && editor.state.selection.from !== editor.state.selection.to) {
                                editor.chain().focus().deleteSelection().insertContent(act.content).run();
                              } else {
                                editor.chain().focus().insertContent(act.content).run();
                              }
                            }}
                            title={act.content}
                          >
                            <Sparkles size={11} />
                            <span>{act.title || 'Insertar en documento'}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  {message.memories_to_store && message.memories_to_store.length > 0 && (
                    <div className="suggested-actions" style={{ marginTop: '8px' }}>
                      <span className="suggested-actions-label">Memoria propuesta:</span>
                      <div className="suggested-actions-btns">
                        {message.memories_to_store.map((mem, i) => (
                          <button
                            key={i}
                            className="btn-action-insert"
                            onClick={async (e) => {
                              const btn = e.currentTarget;
                              btn.disabled = true;
                              await onAddMemory?.({ kind: 'decision', content: mem });
                              btn.textContent = '✓ Guardado en memoria';
                            }}
                            title={`Guardar en memoria del proyecto: "${mem}"`}
                          >
                            <BrainCircuit size={11} />
                            <span>Recordar: "{mem.length > 40 ? `${mem.slice(0, 40)}…` : mem}"</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
            <div className="chat-composer">
              <textarea placeholder="Pregunta o pide redactar una sección..." value={chatPrompt} onChange={(event) => setChatPrompt(event.target.value)}
                onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); sendChat(); } }} />
              <button onClick={sendChat} disabled={chatting || !chatPrompt.trim()} title="Enviar al copiloto">{chatting ? <div className="spinner" /> : <Send size={16} />}</button>
            </div>
          </div>
        )}

        {activeTab === 'memories' && (
          <div className="panel-content memory-panel">
            <div className="panel-heading">
              <div><span className="eyebrow">Memoria del Proyecto</span><h3>Preferencias y Acuerdos</h3></div>
            </div>

            <form className="memory-form" onSubmit={handleCreateMemory}>
              <textarea
                placeholder="Escribe una regla, preferencia o hecho del proyecto que la IA deba recordar..."
                value={memoryContent}
                onChange={(e) => setMemoryContent(e.target.value)}
              />
              <div className="memory-form-row">
                <select value={memoryKind} onChange={(e) => setMemoryKind(e.target.value)}>
                  <option value="preference">Preferencia (estilo, tono)</option>
                  <option value="decision">Decisión técnica</option>
                  <option value="fact">Dato o contexto</option>
                </select>
                <button type="submit" className="btn-primary compact" disabled={savingMemory || !memoryContent.trim()}>
                  {savingMemory ? <div className="spinner" /> : <Plus size={13} />} Guardar
                </button>
              </div>
            </form>

            <div className="memory-list">
              {memories.length === 0 ? (
                <p className="panel-empty" style={{ margin: '14px 0' }}>
                  No hay memorias guardadas todavía. El copiloto aprenderá automáticamente durante el chat, o puedes agregar reglas aquí.
                </p>
              ) : (
                memories.map((m) => (
                  <div className="memory-item" key={m.id}>
                    <div className="memory-item-header">
                      <span className={`memory-badge ${m.kind || 'fact'}`}>
                        {m.kind === 'preference' ? 'Preferencia' : m.kind === 'decision' ? 'Decisión' : 'Dato'}
                      </span>
                      {onDeleteMemory && (
                        <button
                          className="btn-icon-danger"
                          onClick={() => onDeleteMemory(m.id)}
                          title="Eliminar esta memoria"
                        >
                          <Trash2 size={13} />
                        </button>
                      )}
                    </div>
                    <p>{m.content}</p>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {activeTab === 'sources' && (
          <div className="panel-content">
            <div className="panel-heading"><div><span className="eyebrow">RAG del proyecto</span><h3>Fuentes y evidencias</h3></div></div>
            <button className="source-drop" onClick={() => sourceInputRef.current?.click()} disabled={uploading}>
              <Paperclip size={17} /><strong>Adjuntar material de estudio</strong><span>PDF, DOCX, XLSX, TXT o código</span>
            </button>
            <input ref={sourceInputRef} type="file" multiple hidden accept=".pdf,.docx,.xlsx,.txt,.md,.csv,.sql,.py,.java,.cs" onChange={(event) => uploadSources(event.target.files)} />
            <div className="source-list">
              {sources.length === 0 ? (
                <p className="panel-empty" style={{ margin: '8px 0' }}>Sin fuentes adjuntas.</p>
              ) : (
                sources.map((source) => (
                  <div key={source.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0, flex: 1 }}>
                      <BookOpenCheck size={14} style={{ flexShrink: 0 }} />
                      <div style={{ minWidth: 0, overflow: 'hidden' }}>
                        <strong style={{ display: 'block', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>{source.filename}</strong>
                        <small>{source.kind} · {source.text_size ? `${Math.round(source.text_size / 1024)} KB` : 'indexado'}</small>
                      </div>
                    </div>
                    {onDeleteSource && (
                      <button
                        type="button"
                        className="btn-icon-danger"
                        style={{ padding: '4px', background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-dim)', flexShrink: 0 }}
                        onClick={() => {
                          if (window.confirm(`¿Eliminar la fuente "${source.filename}"? Se borrará del conocimiento del proyecto.`)) {
                            onDeleteSource(source.id);
                          }
                        }}
                        title="Eliminar fuente"
                      >
                        <Trash2 size={13} />
                      </button>
                    )}
                  </div>
                ))
              )}
            </div>
            <h4>Capturas insertadas ({evidence.length})</h4>
            <div className="source-list">
              {evidence.length === 0 ? (
                <p className="panel-empty" style={{ margin: '8px 0' }}>Sin capturas registradas.</p>
              ) : (
                evidence.map((item) => (
                  <div key={item.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0, flex: 1 }}>
                      <ImagePlus size={14} style={{ flexShrink: 0 }} />
                      <div style={{ minWidth: 0, overflow: 'hidden' }}>
                        <strong style={{ display: 'block', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap' }}>{item.filename}</strong>
                        <small>{item.caption || 'Sin leyenda'}</small>
                      </div>
                    </div>
                    {onDeleteEvidence && (
                      <button
                        type="button"
                        className="btn-icon-danger"
                        style={{ padding: '4px', background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--text-dim)', flexShrink: 0 }}
                        onClick={() => {
                          if (window.confirm(`¿Eliminar la captura "${item.filename}" de las evidencias?`)) {
                            onDeleteEvidence(item.id);
                          }
                        }}
                        title="Eliminar evidencia"
                      >
                        <Trash2 size={13} />
                      </button>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </aside>

      {evidenceModalFile && (
        <div className="modal-backdrop" onClick={() => setEvidenceModalFile(null)}>
          <div className="modal-card" style={{ maxWidth: 480 }} onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <ImagePlus size={20} color="var(--accent)" />
                <h3 style={{ fontSize: '1.1rem', fontWeight: 700 }}>Insertar Captura / Evidencia</h3>
              </div>
              <button onClick={() => setEvidenceModalFile(null)} style={{ background: 'transparent', border: 'none', color: 'var(--text-dim)', cursor: 'pointer' }}>
                <X size={18} />
              </button>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginBottom: '1.25rem' }}>
              <div className="form-group">
                <label>Archivo seleccionado</label>
                <div style={{ fontSize: '0.85rem', color: 'var(--text-main)', background: 'var(--bg-input)', padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--border)' }}>
                  {evidenceModalFile.name} ({(evidenceModalFile.size / 1024).toFixed(1)} KB)
                </div>
              </div>

              <div className="form-group">
                <label>Leyenda / ¿Qué demuestra esta captura?</label>
                <input
                  className="form-input"
                  value={evidenceCaption}
                  onChange={(e) => setEvidenceCaption(e.target.value)}
                  placeholder="Ej: Ejecución exitosa de migraciones en terminal"
                />
              </div>

              {criteria.length > 0 && (
                <div className="form-group">
                  <label>Asociar a criterio de pauta (opcional)</label>
                  <select
                    className="form-input"
                    value={evidenceCriterionId}
                    onChange={(e) => setEvidenceCriterionId(e.target.value)}
                  >
                    <option value="">-- Sin asociar a criterio específico --</option>
                    {criteria.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.indicator.slice(0, 60)}{c.indicator.length > 60 ? '…' : ''}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="form-group" style={{ background: 'var(--bg-input)', padding: '10px 12px', borderRadius: '8px', border: '1px solid var(--border)' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', marginBottom: enableWatermark ? '8px' : 0, fontWeight: 600 }}>
                  <input
                    type="checkbox"
                    checked={enableWatermark}
                    onChange={(e) => setEnableWatermark(e.target.checked)}
                    style={{ width: 16, height: 16, accentColor: 'var(--accent)', cursor: 'pointer' }}
                  />
                  <span>Aplicar marca de agua académica translúcida</span>
                </label>
                {enableWatermark && (
                  <input
                    className="form-input"
                    value={watermarkCustomText}
                    onChange={(e) => setWatermarkCustomText(e.target.value)}
                    placeholder="Ej: Nicolás Jara - Informe Técnico - DocStudio"
                    style={{ fontSize: '0.82rem' }}
                  />
                )}
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
              <button className="btn-secondary" onClick={() => setEvidenceModalFile(null)}>
                Cancelar
              </button>
              <button className="btn-primary" onClick={confirmUploadEvidence} disabled={uploading}>
                {uploading ? <div className="spinner" /> : <Upload size={14} />} Insertar en Documento
              </button>
            </div>
          </div>
        </div>
      )}

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
                          const restored = await onRestoreVersion(v.version_number, editor.getHTML());
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
