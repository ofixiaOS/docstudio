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
    default_student: 'Nicolás Javier Jara Guzmán',
    default_career: 'Ingeniería en Informática',
  });
  const [health, setHealth] = useState(null);
  const [projects, setProjects] = useState([]);
  const [activeProjectId, setActiveProjectId] = useState(null);
  const [projectData, setProjectData] = useState(null);
  const [messages, setMessages] = useState([]);
  const [analysisData, setAnalysisData] = useState(EMPTY_ANALYSIS);
  const [uploadParams, setUploadParams] = useState({
    student: 'Nicolás Javier Jara Guzmán',
    career: 'Ingeniería en Informática',
    subject: '',
  });
  const [docData, setDocData] = useState(null);
  const [auditResult, setAuditResult] = useState(null);
  const [isKeyModalOpen, setIsKeyModalOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [exporting, setExporting] = useState(false);
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
    } catch (error) {
      setErrorMessage(`No se pudo conectar con el backend: ${error.message}`);
    }
  }, []);

  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect -- synchronization with the local backend
    bootstrap();
    return () => clearTimeout(saveTimer.current);
  }, [bootstrap]);

  const openProject = async (projectId) => {
    setErrorMessage('');
    try {
      const [project, history] = await Promise.all([
        api(`/api/projects/${projectId}`),
        api(`/api/projects/${projectId}/messages`),
      ]);
      setActiveProjectId(projectId);
      setProjectData(project);
      setMessages(history);
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
    } catch (error) {
      setErrorMessage(error.message);
    }
  };

  const newProject = () => {
    setActiveProjectId(null);
    setProjectData(null);
    setMessages([]);
    setAuditResult(null);
    setAnalysisData(EMPTY_ANALYSIS);
    setDocData(null);
    setStep('upload');
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
      await loadProjects();
      setStep('outline');
    } catch (error) {
      setErrorMessage(error.message);
      if (error.message.includes('GEMINI_API_KEY')) setIsKeyModalOpen(true);
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
      setMessages((current) => [...current, { id: `reply-${Date.now()}`, role: 'assistant', content: result.answer }]);
      return result;
    } catch (error) {
      setErrorMessage(error.message);
      return null;
    } finally {
      setChatting(false);
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

  const handleUploadEvidence = async (file, caption, criterionId = '') => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('caption', caption);
    if (criterionId) formData.append('criterion_id', criterionId);
    return api(`/api/projects/${activeProjectId}/evidence`, { method: 'POST', body: formData });
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
      anchor.download = `${(docData?.title || 'Trabajo Iplacex').replace(/[\\/*?:"<>|]/g, '')}.docx`;
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

  return (
    <div className="app-container">
      <Header currentStep={step} setStep={setStep} config={config}
        onOpenKeyModal={() => setIsKeyModalOpen(true)} onReset={newProject} />
      <div className="workspace-shell">
        <ProjectSidebar projects={projects} activeProjectId={activeProjectId}
          onOpenProject={openProject} onNewProject={newProject} health={health} />
        <main className="main-content">
          {errorMessage && (
            <div className="error-banner"><AlertCircle size={18} /><span>{errorMessage}</span></div>
          )}
          <Suspense fallback={<div className="page-loading"><div className="spinner" /> Cargando espacio de trabajo…</div>}>
            {step === 'upload' && <UploadView onAnalyze={handleAnalyze} loading={loading} config={config} />}
            {step === 'outline' && <OutlineView analysisData={analysisData} setAnalysisData={setAnalysisData}
              onGenerate={handleGenerate} onBack={() => setStep('upload')} generating={generating} />}
            {step === 'editor' && (
              <EditorView docData={docData} projectData={projectData} analysisData={analysisData}
                messages={messages} auditResult={auditResult} savingState={savingState}
                onDocumentChange={handleDocumentChange} onSnapshot={handleSnapshot}
                onExportDocx={handleExportDocx} exporting={exporting}
                onRefineText={handleRefineText} refining={refining}
                onChat={handleChat} chatting={chatting} onAudit={handleAudit} auditing={auditing}
                onUploadEvidence={handleUploadEvidence} onUploadSources={handleUploadSources} />
            )}
          </Suspense>
        </main>
      </div>
      <ApiKeyModal isOpen={isKeyModalOpen} onClose={() => setIsKeyModalOpen(false)}
        onSaved={bootstrap} currentKeyMasked={config.api_key_masked} />
    </div>
  );
}
