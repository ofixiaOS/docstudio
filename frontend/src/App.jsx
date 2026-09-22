import React, { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { AlertCircle } from 'lucide-react';
import Header from './components/Header';
import ApiKeyModal from './components/ApiKeyModal';
import ProjectSidebar from './components/ProjectSidebar';
import { api } from './api';

const UploadView = lazy(() => import('./components/UploadView'));
const OutlineView = lazy(() => import('./components/OutlineView'));
const EditorView = lazy(() => import('./components/EditorView'));

const EMPTY_ANALYSIS = {
  project_id: null,
  title: '',
  subject: '',
  summary: '',
  deliverables: [],
  key_requirements: [],
  criteria: [],
  outline: [],
  raw_pauta_full: '',
};

export default function App() {
  const [step, setStep] = useState('upload');
  const [config, setConfig] = useState({
    has_api_key: false,
    api_key_masked: '',
    default_student: 'Autor',
    default_career: '',
    default_institution: '',
  });
  const [health, setHealth] = useState(null);
  const [projects, setProjects] = useState([]);
  const [activeProjectId, setActiveProjectId] = useState(null);
  const [projectData, setProjectData] = useState(null);
  const [messages, setMessages] = useState([]);
  const [memories, setMemories] = useState([]);
  const [analysisData, setAnalysisData] = useState(EMPTY_ANALYSIS);
  const [uploadParams, setUploadParams] = useState({
    student: 'Autor',
    career: '',
    subject: '',
  });
  const [docData, setDocData] = useState(null);
  const [versions, setVersions] = useState([]);
  const [auditResult, setAuditResult] = useState(null);
  const [isKeyModalOpen, setIsKeyModalOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportingPackage, setExportingPackage] = useState(false);
  const [refining, setRefining] = useState(false);
  const [chatting, setChatting] = useState(false);
  const [auditing, setAuditing] = useState(false);
  const [savingState, setSavingState] = useState('saved');
  const [errorMessage, setErrorMessage] = useState('');
  const saveTimer = useRef(null);

  const loadProjects = useCallback(async () => {
    const data = await api('/api/projects');
    setProjects(data);
  }, []);

  const loadVersions = useCallback(async (projectId) => {
    if (!projectId) {
      setVersions([]);
      return;
    }
    try {
      const data = await api(`/api/projects/${projectId}/versions`);
      setVersions(data);
    } catch {
      setVersions([]);
    }
  }, []);

  const loadMemories = useCallback(async (projectId) => {
    if (!projectId) {
      setMemories([]);
      return;
    }
    try {
      const data = await api(`/api/projects/${projectId}/memories`);
      setMemories(data || []);
    } catch {
      setMemories([]);
    }
  }, []);

  const openProject = useCallback(async (projectId) => {
    setErrorMessage('');
    try {
      const [project, history, versionList, memoryList] = await Promise.all([
        api(`/api/projects/${projectId}`),
        api(`/api/projects/${projectId}/messages`),
        api(`/api/projects/${projectId}/versions`).catch(() => []),
        api(`/api/projects/${projectId}/memories`).catch(() => []),
      ]);
      setActiveProjectId(projectId);
      setProjectData(project);
      setMessages(history);
      setVersions(versionList || []);
      setMemories(memoryList || []);
      setUploadParams({ student: project.student, career: project.career, subject: project.subject });
      setAnalysisData({
        project_id: project.id,
        title: project.title,
        subject: project.subject,
        summary: project.summary,
        deliverables: project.deliverables || [],
        key_requirements: project.criteria?.map((item) => item.indicator) || [],
        criteria: project.criteria || [],
        outline: project.outline || [],
        raw_pauta_full: project.rubric_text || '',
      });
      if (project.document_html) {
        setDocData({ ...project, html_content: project.document_html });
        setStep('editor');
      } else {
        setDocData(null);
        setStep('outline');
      }
      try {
        localStorage.setItem('docstudio_active_project', projectId);
        const url = new URL(window.location);
        url.searchParams.set('project', projectId);
        window.history.replaceState({}, '', url);
      } catch {
        // Ignore storage or history limitations
      }
    } catch (error) {
      setErrorMessage(error.message);
      try {
        localStorage.removeItem('docstudio_active_project');
        const url = new URL(window.location);
        url.searchParams.delete('project');
        window.history.replaceState({}, '', url);
      } catch {
        // Ignore
      }
    }
  }, []);

  const bootstrap = useCallback(async () => {
    try {
      const [configData, healthData, projectList] = await Promise.all([
        api('/api/config'),
        api('/api/health'),
        api('/api/projects'),
      ]);
      setConfig(configData);
      setHealth(healthData);
      setProjects(projectList);
      if (!configData.has_api_key) setIsKeyModalOpen(true);

      const urlParams = new URLSearchParams(window.location.search);
      const targetProjectId = urlParams.get('project') || localStorage.getItem('docstudio_active_project');
      if (targetProjectId && projectList.some((p) => p.id === targetProjectId)) {
        await openProject(targetProjectId);
      }
    } catch (error) {
      setErrorMessage(`No se pudo conectar con el backend: ${error.message}`);
    }
  }, [openProject]);

  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect -- synchronization with the local backend
    bootstrap();
    return () => clearTimeout(saveTimer.current);
  }, [bootstrap]);

  const newProject = () => {
    setActiveProjectId(null);
    setProjectData(null);
    setMessages([]);
    setVersions([]);
    setMemories([]);
    setAuditResult(null);
    setAnalysisData(EMPTY_ANALYSIS);
    setDocData(null);
    setStep('upload');
    try {
      localStorage.removeItem('docstudio_active_project');
      const url = new URL(window.location);
      url.searchParams.delete('project');
      window.history.replaceState({}, '', url);
    } catch {
      // Ignore
    }
  };

  const handleAnalyze = async ({ file, pautaText, subject, student, career }) => {
    setLoading(true);
    setErrorMessage('');
    setUploadParams({ student, career, subject });
    const formData = new FormData();
    if (file) formData.append('file', file);
    if (pautaText) formData.append('pauta_raw_text', pautaText);
    formData.append('subject', subject || '');
    formData.append('student', student);
    formData.append('career', career);
    try {
      const data = await api('/api/analyze-rubric', { method: 'POST', body: formData });
      setAnalysisData(data);
      setActiveProjectId(data.project_id);
      setProjectData(data);
      try {
        localStorage.setItem('docstudio_active_project', data.project_id);
        const url = new URL(window.location);
        url.searchParams.set('project', data.project_id);
        window.history.replaceState({}, '', url);
      } catch {
        // Ignore
      }
      await loadProjects();
      setStep('outline');
    } catch (error) {
      setErrorMessage(error.message);
      if (error.message.includes('GEMINI_API_KEY')) setIsKeyModalOpen(true);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateOffline = async ({ title, file, pautaText, subject, student, career }) => {
    setLoading(true);
    setErrorMessage('');
    setUploadParams({ student, career, subject });
    const formData = new FormData();
    formData.append('title', title);
    if (file) formData.append('file', file);
    if (pautaText) formData.append('pauta_raw_text', pautaText);
    formData.append('subject', subject || 'General');
    formData.append('student', student);
    formData.append('career', career);
    try {
      const data = await api('/api/projects/import', { method: 'POST', body: formData });
      const project = await api(`/api/projects/${data.project_id}`);
      setAnalysisData(data);
      setActiveProjectId(data.project_id);
      setProjectData(project);
      try {
        localStorage.setItem('docstudio_active_project', data.project_id);
        const url = new URL(window.location);
        url.searchParams.set('project', data.project_id);
        window.history.replaceState({}, '', url);
      } catch {
        // Ignore
      }
      setIsKeyModalOpen(false);
      await loadProjects();
      setStep('outline');
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    setErrorMessage('');
    try {
      const data = await api('/api/generate-document', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: activeProjectId,
          title: analysisData.title,
          subject: analysisData.subject,
          student: uploadParams.student,
          career: uploadParams.career,
          outline: analysisData.outline,
          pauta_text: analysisData.raw_pauta_full,
          mode: 'sectional',
        }),
      });
      setDocData(data);
      setStep('editor');
      await loadProjects();
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setGenerating(false);
    }
  };

  const handleUpdateOutline = async (newOutline) => {
    setAnalysisData((curr) => ({ ...curr, outline: newOutline }));
    if (activeProjectId) {
      try {
        await api(`/api/projects/${activeProjectId}/outline`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ outline: newOutline }),
        });
        setProjectData((curr) => (curr ? { ...curr, outline: newOutline } : curr));
      } catch (err) {
        console.error('Error saving outline:', err);
      }
    }
  };

  const handleContinueOffline = async () => {
    const outline = analysisData?.outline || [];
    if (activeProjectId && outline.length > 0) {
      try {
        await api(`/api/projects/${activeProjectId}/outline`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ outline }),
        });
      } catch (err) {
        console.error('Error saving outline on continue:', err);
      }
    }
    const outlineHtml = outline.length > 0
      ? outline.map((c) => `<h2>${c.title}</h2><p><em>${c.description || 'Redacta aquí esta sección...'}</em></p>`).join('\n')
      : '<h2>Introducción</h2><p>Documento listo para redactar.</p>';
    const currentHtml = projectData?.document_html || outlineHtml;
    if (activeProjectId && !projectData?.document_html) {
      try {
        await api(`/api/projects/${activeProjectId}/document`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ html_content: currentHtml }),
        });
      } catch (err) {
        console.error('Error saving initial document:', err);
      }
    }
    setDocData({
      project_id: activeProjectId,
      title: analysisData.title || projectData?.title || 'Nuevo Trabajo',
      subject: analysisData.subject || projectData?.subject || 'General',
      student: uploadParams.student,
      career: uploadParams.career,
      html_content: currentHtml,
    });
    setStep('editor');
    await loadProjects();
  };

  const handleDocumentChange = (htmlContent) => {
    if (!activeProjectId) return;
    setSavingState('saving');
    clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(async () => {
      try {
        await api(`/api/projects/${activeProjectId}/document`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ html_content: htmlContent }),
        });
        setSavingState('saved');
      } catch {
        setSavingState('error');
      }
    }, 900);
  };

  const handleSnapshot = async (htmlContent) => {
    const result = await api(`/api/projects/${activeProjectId}/snapshots`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ html_content: htmlContent, reason: 'manual' }),
    });
    setSavingState(`v${result.version}`);
    await loadVersions(activeProjectId);
  };

  const handleRestoreVersion = async (versionNumber, currentHtmlContent) => {
    try {
      const result = await api(`/api/projects/${activeProjectId}/versions/${versionNumber}/restore`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ current_html_content: currentHtmlContent }),
      });
      setDocData((current) => ({ ...current, html_content: result.html_content }));
      setSavingState(`v${result.version_number}`);
      await loadVersions(activeProjectId);
      return result.html_content;
    } catch (error) {
      setErrorMessage(error.message);
      return null;
    }
  };

  const handleRefineText = async (selectedText, instruction) => {
    setRefining(true);
    try {
      const data = await api('/api/refine-text', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: activeProjectId, selected_text: selectedText, instruction,
          subject: analysisData.subject }),
      });
      return data.refined_text;
    } catch (error) {
      setErrorMessage(error.message);
      return null;
    } finally {
      setRefining(false);
    }
  };

  const handleChat = async (message, documentExcerpt) => {
    setChatting(true);
    const optimistic = { id: `local-${Date.now()}`, role: 'user', content: message };
    setMessages((current) => [...current, optimistic]);
    try {
      const result = await api(`/api/projects/${activeProjectId}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, document_excerpt: documentExcerpt }),
      });
      setMessages((current) => [
        ...current,
        {
          id: `reply-${Date.now()}`,
          role: 'assistant',
          content: result.answer,
          suggested_actions: result.suggested_actions || [],
          memories_to_store: result.memories_to_store || [],
        },
      ]);
      await loadMemories(activeProjectId);
      return result;
    } catch (error) {
      setErrorMessage(error.message);
      return null;
    } finally {
      setChatting(false);
    }
  };

  const handleAddMemory = async ({ kind, content, importance = 0.8 }) => {
    if (!activeProjectId || !content.trim()) return;
    try {
      await api(`/api/projects/${activeProjectId}/memories`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind, content: content.trim(), importance }),
      });
      await loadMemories(activeProjectId);
    } catch (error) {
      setErrorMessage(error.message);
    }
  };

  const handleDeleteMemory = async (memoryId) => {
    try {
      await api(`/api/memories/${memoryId}`, { method: 'DELETE' });
      setMemories((curr) => curr.filter((m) => m.id !== memoryId));
    } catch (error) {
      setErrorMessage(error.message);
    }
  };

  const handleDeleteProject = async (projectId) => {
    try {
      await api(`/api/projects/${projectId}`, { method: 'DELETE' });
      if (activeProjectId === projectId) {
        newProject();
      }
      await loadProjects();
    } catch (error) {
      setErrorMessage(error.message);
    }
  };

  const handleDeleteSource = async (sourceId) => {
    if (!activeProjectId) return;
    try {
      await api(`/api/projects/${activeProjectId}/sources/${sourceId}`, { method: 'DELETE' });
      const project = await api(`/api/projects/${activeProjectId}`);
      setProjectData(project);
    } catch (error) {
      setErrorMessage(error.message);
    }
  };

  const handleDeleteEvidence = async (evidenceId) => {
    if (!activeProjectId) return;
    try {
      await api(`/api/projects/${activeProjectId}/evidence/${evidenceId}`, { method: 'DELETE' });
      const project = await api(`/api/projects/${activeProjectId}`);
      setProjectData(project);
    } catch (error) {
      setErrorMessage(error.message);
    }
  };

  const handleAudit = async (htmlContent) => {
    setAuditing(true);
    try {
      const result = await api(`/api/projects/${activeProjectId}/audit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ html_content: htmlContent, use_ai: true }),
      });
      setAuditResult(result);
      const project = await api(`/api/projects/${activeProjectId}`);
      setProjectData(project);
      return result;
    } catch (error) {
      setErrorMessage(error.message);
      return null;
    } finally {
      setAuditing(false);
    }
  };

  const handleUploadEvidence = async (file, caption, criterionId = '', watermark = false, watermarkText = '') => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('caption', caption);
    if (criterionId) formData.append('criterion_id', criterionId);
    if (watermark) {
      formData.append('watermark', 'true');
      if (watermarkText) formData.append('watermark_text', watermarkText);
    }
    const result = await api(`/api/projects/${activeProjectId}/evidence`, { method: 'POST', body: formData });
    const project = await api(`/api/projects/${activeProjectId}`);
    setProjectData(project);
    return result;
  };

  const handleUploadSources = async (files) => {
    const formData = new FormData();
    [...files].forEach((file) => formData.append('files', file));
    const result = await api(`/api/projects/${activeProjectId}/sources`, { method: 'POST', body: formData });
    const project = await api(`/api/projects/${activeProjectId}`);
    setProjectData(project);
    return result;
  };

  const handleExportDocx = async (currentHtml) => {
    setExporting(true);
    try {
      const response = await api('/api/export-docx', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ project_id: activeProjectId, title: docData?.title || analysisData.title,
          subject: docData?.subject || analysisData.subject, student: uploadParams.student,
          career: uploadParams.career, html_content: currentHtml }),
      });
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `${(docData?.title || 'Documento DocStudio').replace(/[\\/*?:"<>|]/g, '')}.docx`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setExporting(false);
    }
  };

  const handleExportPackage = async (currentHtml) => {
    if (!activeProjectId) return;
    setExportingPackage(true);
    try {
      const response = await api(`/api/projects/${activeProjectId}/package-submission`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ html_content: currentHtml, include_sources: true }),
      });
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `${(docData?.title || 'Trabajo').replace(/[\\/*?:"<>|]/g, '')}_Entrega_Final.zip`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      setErrorMessage(error.message);
    } finally {
      setExportingPackage(false);
    }
  };

  const [regeneratingSection, setRegeneratingSection] = useState(null);

  const handleRegenerateSection = async (heading, instruction = '', currentHtml = null) => {
    if (!activeProjectId) return null;
    clearTimeout(saveTimer.current);
    setRegeneratingSection(heading);
    try {
      const result = await api(`/api/projects/${activeProjectId}/regenerate-section`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          heading,
          instruction,
          current_html_content: currentHtml,
        }),
      });
      setDocData((current) => ({ ...current, html_content: result.html_content }));
      setSavingState(`v${result.version}`);
      await loadVersions(activeProjectId);
      return result;
    } catch (error) {
      setErrorMessage(error.message);
      return null;
    } finally {
      setRegeneratingSection(null);
    }
  };

  return (
    <div className="app-container">
      <Header currentStep={step} setStep={setStep} config={config}
        onOpenKeyModal={() => setIsKeyModalOpen(true)} onReset={newProject} />
      <div className="workspace-shell">
        <ProjectSidebar projects={projects} activeProjectId={activeProjectId}
          onOpenProject={openProject} onNewProject={newProject} onDeleteProject={handleDeleteProject} health={health} />
        <main className="main-content">
          {errorMessage && (
            <div className="error-banner"><AlertCircle size={18} /><span>{errorMessage}</span></div>
          )}
          <Suspense fallback={<div className="page-loading"><div className="spinner" /> Cargando espacio de trabajo…</div>}>
            {step === 'upload' && <UploadView onAnalyze={handleAnalyze} onCreateOffline={handleCreateOffline}
              loading={loading} config={config} />}
            {step === 'outline' && <OutlineView analysisData={analysisData} setAnalysisData={setAnalysisData}
              onUpdateOutline={handleUpdateOutline}
              onGenerate={handleGenerate} onContinueOffline={handleContinueOffline} onBack={() => setStep('upload')} generating={generating} />}
            {step === 'editor' && (
              <EditorView key={activeProjectId} docData={docData} projectData={projectData} analysisData={analysisData}
                messages={messages} versions={versions} auditResult={auditResult} savingState={savingState}
                memories={memories} onAddMemory={handleAddMemory} onDeleteMemory={handleDeleteMemory} config={config}
                onDocumentChange={handleDocumentChange} onSnapshot={handleSnapshot}
                onRestoreVersion={handleRestoreVersion}
                onExportDocx={handleExportDocx} exporting={exporting}
                onExportPackage={handleExportPackage} exportingPackage={exportingPackage}
                onRefineText={handleRefineText} refining={refining}
                onChat={handleChat} chatting={chatting} onAudit={handleAudit} auditing={auditing}
                onUploadEvidence={handleUploadEvidence} onUploadSources={handleUploadSources}
                onDeleteSource={handleDeleteSource} onDeleteEvidence={handleDeleteEvidence}
                onRegenerateSection={handleRegenerateSection} regeneratingSection={regeneratingSection} />
            )}
          </Suspense>
        </main>
      </div>
      <ApiKeyModal isOpen={isKeyModalOpen} onClose={() => setIsKeyModalOpen(false)}
        onSaved={bootstrap} currentKeyMasked={config.api_key_masked} />
    </div>
  );
}
