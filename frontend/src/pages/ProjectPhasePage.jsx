import React, { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import FieldEditor from "../components/FieldEditor";
import LoadingState from "../components/LoadingState";
import PhaseStepper from "../components/PhaseStepper";
import {
  enumToPhaseNumber,
  phaseConfig,
  phaseLabels,
  phaseNumberToEnum,
} from "../config/phaseConfig";
import { useAI } from "../context/AIContext";
import { api } from "../services/api";

const phaseFields = {
  1: [
    "Describe the pain point",
    "Characterize the environment",
    "Consequences/Benefits",
    "Identify People Involved",
    "What scientific evidence?",
    "Define the objectives",
    "What research questions?",
  ],
  2: ["alignment_notes", "suggested_edits", "conflicts_consensus"],
  3: ["final_problem_statement", "consolidation_notes"],
  4: ["assessment_notes"],
  5: ["observations"],
};

export default function ProjectPhasePage({ token, me }) {
  const { id, phaseNumber } = useParams();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const { aiEnabled } = useAI();

  const projectId = Number(id);
  const routePhase = Number(phaseNumber);
  const isParticipant = searchParams.get("mode") === "participant";

  const participantSession = useMemo(() => {
    const raw = localStorage.getItem("participant");
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return null;
    }
  }, []);

  const participantId =
    Number(searchParams.get("participantId")) ||
    participantSession?.participant_id;

  const actorType = isParticipant ? "participant" : "researcher";
  const actorId = isParticipant ? participantId : me?.id;

  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionMessage, setActionMessage] = useState("");

  const [entries, setEntries] = useState({});
  const [suggestions, setSuggestions] = useState({});
  const [pendingByField, setPendingByField] = useState({});

  const [inviteUrl, setInviteUrl] = useState("");
  const [summaryJob, setSummaryJob] = useState(null);
  const [exportInfo, setExportInfo] = useState(null);

  const [assessment, setAssessment] = useState({
    valuable: 0,
    feasible: 0,
    applicable: 0,
    justification: "",
  });
  const [assessmentSaved, setAssessmentSaved] = useState({
    valuable: false,
    feasible: false,
    applicable: false,
  });
  const [completionInfo, setCompletionInfo] = useState({
    all_done: false,
    required_respondents: 0,
  });
  const [resultsInfo, setResultsInfo] = useState(null);
  const [decision, setDecision] = useState("go");

  const config = phaseConfig[routePhase] || phaseConfig[1];
  const fields = phaseFields[routePhase] || [];
  const saveTimers = useMemo(() => ({}), []);

  const currentPhaseNumber = enumToPhaseNumber(project?.current_phase);
  const canRenderPhase = routePhase >= 1 && routePhase <= 5;

  useEffect(() => {
    if (!canRenderPhase) {
      navigate(
        `/projects/${projectId}/phase/1${
          isParticipant ? "?mode=participant" : ""
        }`,
        { replace: true }
      );
      return;
    }
    loadProjectContext();
  }, [projectId, routePhase, isParticipant]);

  useEffect(() => {
    if (!project || isParticipant) return;
    const current = enumToPhaseNumber(project.current_phase);
    if (routePhase !== current) {
      navigate(`/projects/${projectId}/phase/${current}`, { replace: true });
    }
  }, [project]);

  async function loadProjectContext() {
    setLoading(true);
    setError("");

    try {
      if (isParticipant) {
        if (
          !participantSession ||
          participantSession.project_id !== projectId
        ) {
          throw new Error("Invalid participant session for this project.");
        }
        const defaultPhase =
          Number(searchParams.get("phase")) || routePhase || 2;
        setProject({
          id: projectId,
          title: `Workshop Project #${projectId}`,
          current_phase: phaseNumberToEnum(defaultPhase),
          current_cycle: 1,
        });
      } else {
        const data = await api(`/projects/${projectId}`, "GET", null, token);
        setProject(data);
      }

      if (routePhase === 4 && !isParticipant) {
        await refreshCompletion();
      }
      if (routePhase === 5 && !isParticipant) {
        await loadResults();
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  function fieldChange(field, content) {
    setEntries((prev) => ({ ...prev, [field]: content }));

    if (!config.collaborativeAutoSave || !actorId) return;

    clearTimeout(saveTimers[field]);
    saveTimers[field] = setTimeout(() => saveEntry(field, content), 700);
  }

  async function saveEntry(field, content, explicit = false) {
    if (!project || !actorId) return;

    try {
      const res = await api(
        `/projects/${project.id}/phases/${phaseNumberToEnum(
          routePhase
        )}/entries`,
        "PATCH",
        { actor_type: actorType, actor_id: actorId, field_key: field, content },
        token
      );

      if (aiEnabled && !isParticipant && routePhase <= 3 && res.ai_job_id) {
        setPendingByField((prev) => ({ ...prev, [field]: true }));
        pollJob(res.ai_job_id, field);
      }

      if (explicit) setActionMessage("Draft saved.");
    } catch (err) {
      setActionMessage(err.message);
    }
  }

  async function saveAllDraft() {
    for (const field of fields) {
      await saveEntry(field, entries[field] || "", true);
    }
  }

  async function pollJob(jobId, field) {
    const started = Date.now();
    const poll = async () => {
      try {
        const status = await api(`/ai/jobs/${jobId}`, "GET", null, token);
        if (status.status === "completed") {
          const out = await api(
            `/projects/${projectId}/phases/${phaseNumberToEnum(
              routePhase
            )}/suggestions?field=${encodeURIComponent(field)}`,
            "GET",
            null,
            token
          );
          setSuggestions((prev) => ({
            ...prev,
            [field]: out.suggestions?.[0] || null,
          }));
          setPendingByField((prev) => ({ ...prev, [field]: false }));
          return;
        }
        if (
          ["failed", "timeout"].includes(status.status) ||
          Date.now() - started > 30000
        ) {
          setPendingByField((prev) => ({ ...prev, [field]: false }));
          return;
        }
        setTimeout(poll, 2000);
      } catch {
        setPendingByField((prev) => ({ ...prev, [field]: false }));
      }
    };
    poll();
  }

  function acceptSuggestion(field, text) {
    setSuggestions((prev) => ({ ...prev, [field]: null }));
    fieldChange(field, `${entries[field] || ""}\n${text}`.trim());
  }

  function dismissSuggestion(field) {
    setSuggestions((prev) => ({ ...prev, [field]: null }));
  }

  async function advancePhase() {
    if (isParticipant) return;

    if (
      routePhase === 4 &&
      config.requiresAllParticipantsDone &&
      !completionInfo.all_done
    ) {
      setActionMessage(
        `Waiting for participants to complete evaluation (${completionInfo.required_respondents}).`
      );
      return;
    }

    try {
      const updated = await api(
        `/projects/${projectId}/advance-phase`,
        "POST",
        {},
        token
      );
      setProject(updated);
      const nextPhase = enumToPhaseNumber(updated.current_phase);

      if (routePhase === 1 && nextPhase === 2) {
        await generateInvite(nextPhase);
      }

      navigate(`/projects/${projectId}/phase/${nextPhase}`);
      setActionMessage(`Advanced to Phase ${nextPhase}.`);
    } catch (err) {
      setActionMessage(err.message);
    }
  }

  async function generateInvite(targetPhase = routePhase) {
    if (isParticipant || targetPhase < 2) return;
    try {
      const data = await api(
        `/projects/${projectId}/invites`,
        "POST",
        {},
        token
      );
      const suffix = `${data.invite_url}${
        data.invite_url.includes("?") ? "&" : "?"
      }phase=${targetPhase}`;
      setInviteUrl(suffix);
    } catch (err) {
      setActionMessage(err.message);
    }
  }

  async function generateSummary() {
    if (isParticipant) return;
    try {
      const data = await api(
        `/projects/${projectId}/summary/generate`,
        "POST",
        {},
        token
      );
      setSummaryJob(data.job_id);
      setActionMessage(`Summary job started (#${data.job_id}).`);
    } catch (err) {
      setActionMessage(err.message);
    }
  }

  async function checkSummaryJob() {
    if (!summaryJob || isParticipant) {
      setActionMessage("No summary job started yet.");
      return;
    }
    try {
      const st = await api(`/ai/jobs/${summaryJob}`, "GET", null, token);
      setActionMessage(`Summary job status: ${st.status}`);
    } catch (err) {
      setActionMessage(err.message);
    }
  }

  async function exportPdf() {
    if (isParticipant) return;
    try {
      const data = await api(
        `/projects/${projectId}/export/pdf`,
        "POST",
        {},
        token
      );
      setExportInfo(data);
      setActionMessage("PDF export generated.");
    } catch (err) {
      setActionMessage(err.message);
    }
  }

  async function refreshCompletion() {
    if (isParticipant) return;
    try {
      const data = await api(
        `/projects/${projectId}/assessment/consolidated`,
        "GET",
        null,
        token
      );
      setCompletionInfo({
        all_done: Boolean(data.all_done),
        required_respondents: data.required_respondents || 0,
      });
      setResultsInfo(data.criteria || null);
    } catch (err) {
      setCompletionInfo({ all_done: false, required_respondents: 0 });
      setActionMessage(`Completion status unavailable: ${err.message}`);
    }
  }

  async function saveAssessmentCriterion(criterion, value) {
    if (!actorId || !value) return;
    try {
      await api(
        `/projects/${projectId}/assessment/score`,
        "POST",
        {
          actor_type: actorType,
          actor_id: actorId,
          criterion,
          score: value,
          justification: assessment.justification,
        },
        token
      );
      setAssessmentSaved((prev) => ({ ...prev, [criterion]: true }));
      setActionMessage("Evaluation saved.");
    } catch (err) {
      if (String(err.message).toLowerCase().includes("already submitted")) {
        setAssessmentSaved((prev) => ({ ...prev, [criterion]: true }));
      } else {
        setActionMessage(err.message);
      }
    }
  }

  async function finalizePhase5() {
    if (isParticipant) return;
    try {
      await api(
        `/projects/${projectId}/decision`,
        "POST",
        { decision, justification: entries.observations || "" },
        token
      );
      setActionMessage("Workshop finalized.");
    } catch (err) {
      setActionMessage(err.message);
    }
  }

  if (loading) return <LoadingState label="Loading phase..." />;
  if (error) return <div className="alert alert-error">{error}</div>;
  if (!project) return null;

  const phaseTitle = phaseLabels[routePhase] || "Phase";
  const canAdvance = !isParticipant && config.canAdvance;
  const advanceDisabled =
    routePhase === 4 && config.requiresAllParticipantsDone
      ? !completionInfo.all_done
      : false;

  return (
    <div className="project-layout">
      <PhaseStepper
        currentPhaseNumber={currentPhaseNumber}
        activePhaseNumber={routePhase}
      />

      <section className="project-main">
        <div className="card">
          <div className="section-header">
            <div>
              <h1>{phaseTitle}</h1>
              <p className="muted">Project: {project.title}</p>
            </div>
            <div className="phase-chip">F{routePhase}</div>
          </div>

          {/*
          {routePhase === 1 && (
            <div className="metadata-card">
              <h3>Project Metadata</h3>
              <p>Title: {project.title}</p>
              <p>Creation date: {project.created_at ? new Date(project.created_at).toLocaleString() : 'N/A'}</p>
              <p>Main researcher: {me?.email || 'N/A'}</p>
              <p>Invited researchers: Not available in current API</p>
              <p>Status: {project.current_phase}</p>
            </div>
          )}*/}
        </div>

        <div className="card">
          {routePhase <= 3 && (
            <>
              <h2>
                {isParticipant ? "Workshop Contribution" : "Board Content"}
              </h2>
              {fields.map((f) => (
                <div key={f}>
                  <FieldEditor
                    field={f}
                    value={entries[f]}
                    suggestion={suggestions[f]}
                    pending={pendingByField[f]}
                    onChange={fieldChange}
                    onAccept={acceptSuggestion}
                    onDismiss={dismissSuggestion}
                  />
                  {aiEnabled && !isParticipant && routePhase === 1 && (
                    <div className="ai-assist-row">
                      <button
                        className="btn btn-tertiary"
                        onClick={() => saveEntry(f, entries[f] || "")}
                      >
                        AI Assist
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </>
          )}

          {routePhase === 4 && (
            <>
              <h2>Semantic Differential Assessment</h2>
              {isParticipant ? (
                <div className="assessment-grid">
                  {["valuable", "feasible", "applicable"].map((criterion) => (
                    <div className="field-card" key={criterion}>
                      <label>{criterion}</label>
                      <input
                        type="range"
                        min="1"
                        max="7"
                        value={assessment[criterion] || 1}
                        disabled={assessmentSaved[criterion]}
                        onChange={(e) => {
                          const value = Number(e.target.value);
                          setAssessment((prev) => ({
                            ...prev,
                            [criterion]: value,
                          }));
                          saveAssessmentCriterion(criterion, value);
                        }}
                      />
                      <p>Score: {assessment[criterion] || "-"}</p>
                      {assessmentSaved[criterion] && (
                        <span className="phase-badge">Completed</span>
                      )}
                    </div>
                  ))}
                  <div className="field-card">
                    <label>Justification (optional)</label>
                    <textarea
                      value={assessment.justification}
                      onChange={(e) =>
                        setAssessment((prev) => ({
                          ...prev,
                          justification: e.target.value,
                        }))
                      }
                    />
                  </div>
                </div>
              ) : (
                <div>
                  <p className="muted">
                    Advance is enabled only when all respondents complete their
                    assessments.
                  </p>
                  <button
                    className="btn btn-secondary"
                    onClick={refreshCompletion}
                  >
                    Refresh Completion Status
                  </button>
                  <p className="hint">
                    Status:{" "}
                    {completionInfo.all_done
                      ? "All participants completed"
                      : "Waiting for participants"}
                  </p>
                </div>
              )}
            </>
          )}

          {routePhase === 5 && (
            <>
              <h2>Results</h2>
              {resultsInfo ? (
                <div className="results-grid">
                  {Object.entries(resultsInfo).map(([criterion, info]) => (
                    <div className="field-card" key={criterion}>
                      <h3>{criterion}</h3>
                      <p>Median/Avg: {Number(info.avg || 0).toFixed(2)}</p>
                      <p>Responses: {info.count || 0}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="muted">No assessment aggregates available yet.</p>
              )}

              {!isParticipant ? (
                <div className="field-card">
                  <label>Go / Pivot / Abort</label>
                  <select
                    value={decision}
                    onChange={(e) => setDecision(e.target.value)}
                  >
                    <option value="go">Go</option>
                    <option value="pivot">Pivot</option>
                    <option value="abort">Abort</option>
                  </select>
                  <label>Observations</label>
                  <textarea
                    value={entries.observations || ""}
                    onChange={(e) =>
                      fieldChange("observations", e.target.value)
                    }
                  />
                </div>
              ) : (
                <p className="muted">Participant read-only view.</p>
              )}
            </>
          )}

          <div className="action-divider" />
          <div className="action-group primary-group">
            {config.canSaveDraft && !isParticipant && (
              <button className="btn btn-secondary" onClick={saveAllDraft}>
                Save draft
              </button>
            )}
            {canAdvance && (
              <button
                className="btn btn-primary"
                onClick={advancePhase}
                disabled={advanceDisabled}
              >
                {routePhase === 1
                  ? "Advance to Phase 2"
                  : routePhase === 2
                  ? "Advance to Phase 3"
                  : routePhase === 3
                  ? "Advance to Phase 4"
                  : "Advance to Phase 5"}
              </button>
            )}
            {config.canFinalize && !isParticipant && (
              <button className="btn btn-primary" onClick={finalizePhase5}>
                Finalize workshop
              </button>
            )}
          </div>

          <div className="action-group secondary-group">
            {config.showInviteLink && !isParticipant && (
              <button
                className="btn btn-secondary"
                onClick={() => generateInvite(routePhase)}
              >
                Generate Invite Link
              </button>
            )}
            {routePhase === 5 && !isParticipant && (
              <>
                <button className="btn btn-secondary" onClick={generateSummary}>
                  Generate Final Summary
                </button>
                <button className="btn btn-secondary" onClick={exportPdf}>
                  Export Project PDF
                </button>
              </>
            )}
          </div>

          {!isParticipant && summaryJob && (
            <div className="action-group tertiary-group">
              <button className="btn btn-tertiary" onClick={checkSummaryJob}>
                Check Summary Job
              </button>
            </div>
          )}

          {advanceDisabled && (
            <p className="hint">
              Waiting for all participants to complete evaluation before
              advancing to Phase 5.
            </p>
          )}

          {inviteUrl && (
            <p className="invite-line">
              Invite URL: <a href={inviteUrl}>{inviteUrl}</a>
            </p>
          )}
          {exportInfo && (
            <p className="hint">Export created: {exportInfo.file_path}</p>
          )}
          {actionMessage && <p className="hint">{actionMessage}</p>}
        </div>
      </section>
    </div>
  );
}
