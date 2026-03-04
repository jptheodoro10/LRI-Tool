import React from "react";
import { useEffect, useMemo, useState } from 'react';
import { useParams } from 'react-router-dom';
import { api } from '../services/api';
import LoadingState from '../components/LoadingState';
import PhaseStepper from '../components/PhaseStepper';
import FieldEditor from '../components/FieldEditor';

const phaseFields = {
  F1: ['problem_outline', 'context', 'implications', 'stakeholders', 'evidence', 'objective', 'research_questions'],
  F2: ['alignment_notes', 'suggested_edits', 'conflicts_consensus'],
  F3: ['final_problem_statement'],
};

export default function ProjectHomePage({ token, me }) {
  const { id } = useParams();
  const projectId = Number(id);
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [entries, setEntries] = useState({});
  const [suggestions, setSuggestions] = useState({});
  const [pendingByField, setPendingByField] = useState({});
  const [inviteUrl, setInviteUrl] = useState('');
  const [summaryJob, setSummaryJob] = useState(null);
  const [exportInfo, setExportInfo] = useState(null);
  const [actionMessage, setActionMessage] = useState('');
  const [workspaceOpen, setWorkspaceOpen] = useState(false);

  const fields = useMemo(() => phaseFields[project?.current_phase] || [], [project?.current_phase]);
  const saveTimers = useMemo(() => ({}), []);

  useEffect(() => {
    loadProject();
  }, [projectId]);

  async function loadProject() {
    setLoading(true);
    setError('');
    try {
      const data = await api(`/projects/${projectId}`, 'GET', null, token);
      setProject(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function changeField(field, content) {
    setEntries((prev) => ({ ...prev, [field]: content }));
    clearTimeout(saveTimers[field]);
    saveTimers[field] = setTimeout(() => saveField(field, content), 800);
  }

  async function saveField(field, content) {
    if (!project) return;
    const res = await api(
      `/projects/${project.id}/phases/${project.current_phase}/entries`,
      'PATCH',
      { actor_type: 'researcher', actor_id: me.id, field_key: field, content },
      token
    );
    if (res.ai_job_id) {
      setPendingByField((prev) => ({ ...prev, [field]: true }));
      pollJob(res.ai_job_id, field);
    }
  }

  async function pollJob(jobId, field) {
    const started = Date.now();
    const poll = async () => {
      const status = await api(`/ai/jobs/${jobId}`, 'GET', null, token);
      if (status.status === 'completed') {
        const out = await api(
          `/projects/${projectId}/phases/${project.current_phase}/suggestions?field=${encodeURIComponent(field)}`,
          'GET',
          null,
          token
        );
        setSuggestions((prev) => ({ ...prev, [field]: out.suggestions?.[0] || null }));
        setPendingByField((prev) => ({ ...prev, [field]: false }));
        return;
      }
      if (['failed', 'timeout'].includes(status.status) || Date.now() - started > 30000) {
        setPendingByField((prev) => ({ ...prev, [field]: false }));
        return;
      }
      setTimeout(poll, 2000);
    };
    poll();
  }

  function acceptSuggestion(field, text) {
    setSuggestions((prev) => ({ ...prev, [field]: null }));
    changeField(field, `${entries[field] || ''}\n${text}`.trim());
  }

  function dismissSuggestion(field) {
    setSuggestions((prev) => ({ ...prev, [field]: null }));
  }

  async function advancePhase() {
    try {
      const data = await api(`/projects/${projectId}/advance-phase`, 'POST', {}, token);
      setProject(data);
      setActionMessage(`Project advanced to ${data.current_phase}.`);
    } catch (err) {
      setActionMessage(err.message);
    }
  }

  async function createInvite() {
    try {
      const data = await api(`/projects/${projectId}/invites`, 'POST', {}, token);
      setInviteUrl(data.invite_url);
      setActionMessage('Invite generated.');
    } catch (err) {
      setActionMessage(err.message);
    }
  }

  async function generateSummary() {
    try {
      const data = await api(`/projects/${projectId}/summary/generate`, 'POST', {}, token);
      setSummaryJob(data.job_id);
      setActionMessage(`Summary job started (#${data.job_id}).`);
    } catch (err) {
      setActionMessage(err.message);
    }
  }

  async function checkSummaryJob() {
    if (!summaryJob) {
      setActionMessage('No summary job started yet.');
      return;
    }
    try {
      const st = await api(`/ai/jobs/${summaryJob}`, 'GET', null, token);
      setActionMessage(`Summary job status: ${st.status}`);
    } catch (err) {
      setActionMessage(err.message);
    }
  }

  async function exportPdf() {
    try {
      const data = await api(`/projects/${projectId}/export/pdf`, 'POST', {}, token);
      setExportInfo(data);
      setActionMessage('PDF export generated.');
    } catch (err) {
      setActionMessage(err.message);
    }
  }

  if (loading) return <LoadingState label="Loading project..." />;
  if (error) return <div className="alert alert-error">{error}</div>;
  if (!project) return null;

  return (
    <div className="project-layout">
      <PhaseStepper currentPhase={project.current_phase} />

      <section className="project-main">
        <div className="card">
          <div className="section-header">
            <div>
              <h1>{project.title}</h1>
              <p className="muted">Project Home</p>
            </div>
            <div className="phase-chip">{project.current_phase}</div>
          </div>
          <p className="meta-line">
            Cycle: {project.current_cycle} {project.updated_at ? `• Updated: ${new Date(project.updated_at).toLocaleString()}` : ''}
          </p>
        </div>

        <div className="card">
          <h2>Actions</h2>
          <div className="action-group primary-group">
            <button className="btn btn-primary" onClick={() => setWorkspaceOpen(true)}>
              Continue / Open Current Phase
            </button>
          </div>
          <div className="action-group secondary-group">
            <button className="btn btn-secondary" onClick={advancePhase}>
              Advance Phase
            </button>
            <button className="btn btn-secondary" onClick={createInvite}>
              Invite
            </button>
            <button className="btn btn-secondary" onClick={generateSummary}>
              Generate Final Summary
            </button>
            <button className="btn btn-secondary" onClick={exportPdf}>
              Export PDF
            </button>
          </div>
          <div className="action-group tertiary-group">
            <button className="btn btn-tertiary" onClick={checkSummaryJob}>
              Check Summary Job
            </button>
          </div>

          {actionMessage && <p className="hint">{actionMessage}</p>}
          {inviteUrl && (
            <p className="invite-line">
              Invite URL: <a href={inviteUrl}>{inviteUrl}</a>
            </p>
          )}
          {exportInfo && <p className="hint">Export created: {exportInfo.file_path}</p>}
        </div>

        {workspaceOpen && (
          <div className="card">
            <h2>Current Phase Workspace</h2>
            {fields.length === 0 && (
              <p className="muted">No editable fields for {project.current_phase}. Use project actions for this phase.</p>
            )}
            {fields.map((f) => (
              <FieldEditor
                key={f}
                field={f}
                value={entries[f]}
                suggestion={suggestions[f]}
                pending={pendingByField[f]}
                onChange={changeField}
                onAccept={acceptSuggestion}
                onDismiss={dismissSuggestion}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
