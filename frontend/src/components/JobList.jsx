const STATUS_COLORS = {
  new: "#94a3b8",
  applied: "#f59e0b",
  interviewing: "#10b981",
  rejected: "#ef4444",
  offered: "#6366f1",
};

const scoreColor = (score) => {
  if (score >= 80) return "#16a34a";
  if (score >= 60) return "#d97706";
  return "#dc2626";
};

export default function JobList({ jobs, selectedId, onSelect, onFavorite }) {
  if (jobs.length === 0) {
    return (
      <div className="empty-list">
        <p>No jobs found. Try searching above.</p>
      </div>
    );
  }

  return (
    <div className="job-list">
      <div className="job-count">{jobs.length} jobs</div>
      {jobs.map((job) => (
        <div
          key={job.id}
          className={`job-card ${selectedId === job.id ? "selected" : ""}`}
          onClick={() => onSelect(job)}
        >
          <div className="job-card-top">
            <div className="job-card-title">{job.title}</div>
            <div className="job-score" style={{ color: scoreColor(job.ats_score) }}>
              {job.ats_score}%
            </div>
          </div>

          <div className="job-card-company">
            {job.company} • {job.location}
          </div>

          <div className="job-card-bottom">
            <span
              className="status-badge"
              style={{ backgroundColor: STATUS_COLORS[job.status] || "#94a3b8" }}
            >
              {job.status}
            </span>
            <span className="source-badge">{job.source}</span>
            {job.tailored_resume && <span className="ai-badge">✨ AI</span>}
            <button
              className={`fav-btn ${job.is_favorite ? "fav-active" : ""}`}
              onClick={(e) => { e.stopPropagation(); onFavorite(job.id, !job.is_favorite); }}
            >
              {job.is_favorite ? "★" : "☆"}
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
