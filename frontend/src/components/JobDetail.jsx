import { useState, useEffect } from "react";
import axios from "axios";

const API = "http://localhost:8000";
const STATUSES = ["new", "applied", "interviewing", "rejected", "offered"];

export default function JobDetail({ job, onAnalyze, onStatusUpdate, onRefresh }) {
  const [activeTab, setActiveTab] = useState("overview");
  const [copied, setCopied] = useState("");

  // Editable content state — initialised from job props
  const [resumeText, setResumeText] = useState("");
  const [emailText, setEmailText] = useState("");
  const [strategyText, setStrategyText] = useState("");
  const [editMode, setEditMode] = useState({ resume: false, email: false, strategy: false });
  const [saving, setSaving] = useState("");
  const [saveMsg, setSaveMsg] = useState("");

  // When job changes (new selection), reset edit state
  useEffect(() => {
    setResumeText(job.tailored_resume_edited || job.tailored_resume || "");
    setEmailText(job.cold_email_edited || job.cold_email || "");
    setStrategyText(job.notes_edited || job.notes || "");
    setEditMode({ resume: false, email: false, strategy: false });
    setSaveMsg("");
  }, [job.id]);

  const copy = (text, label) => {
    navigator.clipboard.writeText(text);
    setCopied(label);
    setTimeout(() => setCopied(""), 2000);
  };

  const toggleEdit = (field) => {
    setEditMode(prev => ({ ...prev, [field]: !prev[field] }));
    setSaveMsg("");
  };

  const handleSave = async (field) => {
    setSaving(field);
    try {
      const payload = {};
      if (field === "resume") payload.tailored_resume_edited = resumeText;
      if (field === "email") payload.cold_email_edited = emailText;
      if (field === "strategy") payload.notes_edited = strategyText;

      await axios.patch(`${API}/api/jobs/${job.id}/edit`, payload);
      setSaveMsg(`${field} saved`);
      setEditMode(prev => ({ ...prev, [field]: false }));
      setTimeout(() => setSaveMsg(""), 3000);
      onRefresh();
    } catch (e) {
      setSaveMsg("Save failed");
    } finally {
      setSaving("");
    }
  };

  const handleRevert = async (field) => {
    // Reset to original AI output
    if (field === "resume") {
      setResumeText(job.tailored_resume || "");
      await axios.patch(`${API}/api/jobs/${job.id}/edit`, { tailored_resume_edited: null });
    }
    if (field === "email") {
      setEmailText(job.cold_email || "");
      await axios.patch(`${API}/api/jobs/${job.id}/edit`, { cold_email_edited: null });
    }
    if (field === "strategy") {
      setStrategyText(job.notes || "");
      await axios.patch(`${API}/api/jobs/${job.id}/edit`, { notes_edited: null });
    }
    setEditMode(prev => ({ ...prev, [field]: false }));
    onRefresh();
  };

  const isEdited = (field) => {
    if (field === "resume") return !!job.tailored_resume_edited;
    if (field === "email") return !!job.cold_email_edited;
    if (field === "strategy") return !!job.notes_edited;
    return false;
  };

  const tabs = [
    { id: "overview", label: "Overview" },
    { id: "resume", label: "Resume" },
    { id: "email", label: "Cold Email" },
    { id: "strategy", label: "Strategy" },
  ];

  const renderEditableTab = (field, label, aiValue, editedValue, currentText, setCurrentText) => {
    const hasContent = !!aiValue;
    const edited = isEdited(field);
    const isEditing = editMode[field];

    if (!hasContent) {
      return (
        <div className="no-ai-content">
          <p>No {label.toLowerCase()} generated yet.</p>
          <p>Click <strong>✨ Run AI Analysis</strong> above to generate this content.</p>
          <p className="note">⏱ Takes 30–90 seconds. Click ↺ Refresh after.</p>
        </div>
      );
    }

    return (
      <div>
        {/* Action Bar */}
        <div className="edit-action-bar">
          <div className="edit-status">
            {edited && <span className="edit-badge">✏ Edited</span>}
            {saveMsg && <span className="save-msg">{saveMsg}</span>}
          </div>
          <div className="edit-buttons">
            {!isEditing && (
              <>
                <button className="btn-copy" onClick={() => copy(currentText, field)}>
                  {copied === field ? "Copied!" : "Copy"}
                </button>
                <button className="btn-edit" onClick={() => toggleEdit(field)}>
                  ✏ Edit
                </button>
                {edited && (
                  <button className="btn-revert" onClick={() => handleRevert(field)}>
                    ↩ Revert to AI
                  </button>
                )}
              </>
            )}
            {isEditing && (
              <>
                <button
                  className="btn-save"
                  onClick={() => handleSave(field)}
                  disabled={saving === field}
                >
                  {saving === field ? "Saving..." : "Save"}
                </button>
                <button className="btn-cancel" onClick={() => {
                  setEditMode(prev => ({ ...prev, [field]: false }));
                  setCurrentText(editedValue || aiValue || "");
                }}>
                  Cancel
                </button>
              </>
            )}
          </div>
        </div>

        {/* Content — editable textarea or read-only pre */}
        {isEditing ? (
          <textarea
            className="ai-edit-textarea"
            value={currentText}
            onChange={(e) => setCurrentText(e.target.value)}
            spellCheck={true}
          />
        ) : (
          <pre className="ai-content">{currentText}</pre>
        )}
      </div>
    );
  };

  return (
    <div className="job-detail">
      {/* Header */}
      <div className="detail-header">
        <div>
          <h2 className="detail-title">{job.title}</h2>
          <p className="detail-company">{job.company} • {job.location}</p>
          {job.salary && <p className="detail-salary">💰 {job.salary}</p>}
        </div>
        <div className="detail-score">
          <div className="big-score">{job.ats_score}%</div>
          <div className="score-label">ATS Fit</div>
        </div>
      </div>

      {/* Actions */}
      <div className="detail-actions">
        <div className="status-select-row">
          <label>Status:</label>
          <select
            value={job.status}
            onChange={e => onStatusUpdate(e.target.value)}
            className="status-select"
          >
            {STATUSES.map(s => (
              <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
            ))}
          </select>
        </div>
        <div className="action-buttons">
          {job.url && (
            <a href={job.url} target="_blank" rel="noreferrer" className="btn-apply">
              Apply →
            </a>
          )}
          <button onClick={onAnalyze} className="btn-analyze">✨ Run AI Analysis</button>
          <button onClick={onRefresh} className="btn-refresh-detail">↺</button>
        </div>
      </div>

      {/* Keywords */}
      <div className="keywords-row">
        <div className="keyword-group">
          <span className="kw-label matched">✓ Matched:</span>
          {(job.matched_keywords || []).slice(0, 8).map(kw => (
            <span key={kw} className="kw-tag matched">{kw}</span>
          ))}
        </div>
        {(job.missing_keywords || []).length > 0 && (
          <div className="keyword-group">
            <span className="kw-label missing">✗ Missing:</span>
            {(job.missing_keywords || []).slice(0, 5).map(kw => (
              <span key={kw} className="kw-tag missing">{kw}</span>
            ))}
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="tabs">
        {tabs.map(tab => (
          <button
            key={tab.id}
            className={`tab ${activeTab === tab.id ? "active" : ""}`}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
            {tab.id === "resume" && job.tailored_resume && (isEdited("resume") ? " ✏" : " ✨")}
            {tab.id === "email" && job.cold_email && (isEdited("email") ? " ✏" : " ✨")}
            {tab.id === "strategy" && job.notes && (isEdited("strategy") ? " ✏" : " ✨")}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="tab-content">

        {activeTab === "overview" && (
          <div>
            <h4>Job Description</h4>
            <p className="jd-text">
              {job.description?.slice(0, 1500) || "No description available"}
            </p>
          </div>
        )}

        {activeTab === "resume" && renderEditableTab(
          "resume", "Resume",
          job.tailored_resume,
          job.tailored_resume_edited,
          resumeText, setResumeText,
        )}

        {activeTab === "email" && renderEditableTab(
          "email", "Cold Email",
          job.cold_email,
          job.cold_email_edited,
          emailText, setEmailText,
        )}

        {activeTab === "strategy" && renderEditableTab(
          "strategy", "Strategy",
          job.notes,
          job.notes_edited,
          strategyText, setStrategyText,
        )}

      </div>
    </div>
  );
}
