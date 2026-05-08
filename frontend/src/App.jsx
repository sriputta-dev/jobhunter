import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import JobList from "./components/JobList";
import JobDetail from "./components/JobDetail";
import SearchPanel from "./components/SearchPanel";
import StatsBar from "./components/StatsBar";
import ResumeUploader from "./components/ResumeUploader";
import "./App.css";

const API = "http://localhost:8000";

export default function App() {
  const [jobs, setJobs] = useState([]);
  const [selectedJob, setSelectedJob] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [pasting, setPasting] = useState(false);
  const [filter, setFilter] = useState({ status: "", min_score: 0, source: "" });
  const [notification, setNotification] = useState(null);

  const notify = (msg, type = "success") => {
    setNotification({ msg, type });
    setTimeout(() => setNotification(null), 4000);
  };

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    try {
      const params = {};
      if (filter.status) params.status = filter.status;
      if (filter.min_score > 0) params.min_score = filter.min_score;
      if (filter.source) params.source = filter.source;
      const { data } = await axios.get(`${API}/api/jobs`, { params });
      setJobs(data.jobs || []);
    } catch (e) {
      notify("Failed to load jobs — is the backend running?", "error");
    } finally {
      setLoading(false);
    }
  }, [filter]);

  const fetchStats = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/api/stats`);
      setStats(data);
    } catch (e) {}
  }, []);

  useEffect(() => {
    fetchJobs();
    fetchStats();
  }, [fetchJobs, fetchStats]);

  // ── Handlers ────────────────────────────────────────────────────────────────

  const handleSearch = async (query, location, limitPerSource) => {
    setSearching(true);
    try {
      const { data } = await axios.post(`${API}/api/search`, {
        query,
        location,
        limit_per_source: limitPerSource,
        min_ats_score: 40,
      });
      notify(`Found ${data.jobs_found} jobs, saved ${data.jobs_saved} new`);
      await fetchJobs();
      await fetchStats();
    } catch (e) {
      notify("Search failed — is the backend running?", "error");
    } finally {
      setSearching(false);
    }
  };

  const handlePaste = async (input, title, company, location) => {
    setPasting(true);
    try {
      const payload = { input };
      if (title) payload.title = title;
      if (company) payload.company = company;
      if (location) payload.location = location;

      const { data } = await axios.post(`${API}/api/jobs/paste`, payload);

      if (data.duplicate) {
        notify("Job already in your tracker — selecting it");
      } else {
        notify(`Job added! ATS Score: ${data.job.ats_score}% — click it then run AI Analysis`);
      }

      await fetchJobs();
      await fetchStats();

      // Auto-select the newly added job
      if (data.job) {
        setSelectedJob(data.job);
      }
    } catch (e) {
      const detail = e.response?.data?.detail;
      if (detail) {
        notify(detail, "error");
      } else {
        notify("Failed to add job — check backend is running", "error");
      }
    } finally {
      setPasting(false);
    }
  };

  const handleAnalyze = async (jobId) => {
    try {
      await axios.post(`${API}/api/jobs/${jobId}/analyze`);
      notify("AI analysis started — refresh in 30-60 seconds");
    } catch (e) {
      notify("Analysis failed — check ANTHROPIC_API_KEY is set in .env", "error");
    }
  };

  const handleStatusUpdate = async (jobId, status) => {
    try {
      await axios.patch(`${API}/api/jobs/${jobId}`, { status });
      setJobs((prev) => prev.map((j) => (j.id === jobId ? { ...j, status } : j)));
      if (selectedJob?.id === jobId) setSelectedJob((prev) => ({ ...prev, status }));
      notify(`Status → ${status}`);
    } catch (e) {
      notify("Update failed", "error");
    }
  };

  const handleFavorite = async (jobId, isFavorite) => {
    try {
      await axios.patch(`${API}/api/jobs/${jobId}`, { is_favorite: isFavorite });
      setJobs((prev) =>
        prev.map((j) => (j.id === jobId ? { ...j, is_favorite: isFavorite } : j))
      );
    } catch (e) {}
  };

  const handleJobClick = async (job) => {
    try {
      const { data } = await axios.get(`${API}/api/jobs/${job.id}`);
      setSelectedJob(data);
    } catch (e) {
      setSelectedJob(job);
    }
  };

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="app">
      {notification && (
        <div className={`toast toast-${notification.type}`}>{notification.msg}</div>
      )}

      <header className="header">
        <div className="header-left">
          <h1>🤖 JobHunter <span>Agent</span></h1>
        </div>
        <div className="header-right">
          <button className="btn-refresh" onClick={() => { fetchJobs(); fetchStats(); }}>
            ↺ Refresh
          </button>
        </div>
      </header>

      {stats && <StatsBar stats={stats} />}

      <div className="main-layout">
        <div className="left-panel">
          <ResumeUploader onUploadSuccess={fetchStats} />
          <SearchPanel
            onSearch={handleSearch}
            onPaste={handlePaste}
            searching={searching}
            pasting={pasting}
          />

          <div className="filters">
            <select
              value={filter.status}
              onChange={(e) => setFilter((f) => ({ ...f, status: e.target.value }))}
            >
              <option value="">All Status</option>
              <option value="new">New</option>
              <option value="applied">Applied</option>
              <option value="interviewing">Interviewing</option>
              <option value="rejected">Rejected</option>
              <option value="offered">Offered</option>
            </select>

            <select
              value={filter.source}
              onChange={(e) => setFilter((f) => ({ ...f, source: e.target.value }))}
            >
              <option value="">All Sources</option>
              <option value="manual">Pasted</option>
              <option value="linkedin">LinkedIn</option>
              <option value="indeed">Indeed</option>
              <option value="dice">Dice</option>
              <option value="glassdoor">Glassdoor</option>
              <option value="greenhouse">Greenhouse</option>
              <option value="lever">Lever</option>
              <option value="company_careers">Company Site</option>
              <option value="himalayas">Himalayas</option>
              <option value="remotive">Remotive</option>
              <option value="jobicy">Jobicy</option>
              <option value="arbeitnow">Arbeitnow</option>
            </select>

            <select
              value={filter.min_score}
              onChange={(e) => setFilter((f) => ({ ...f, min_score: Number(e.target.value) }))}
            >
              <option value={0}>All Scores</option>
              <option value={50}>50+ ATS</option>
              <option value={70}>70+ ATS</option>
              <option value={80}>80+ ATS</option>
            </select>
          </div>

          {loading ? (
            <div className="loading">Loading jobs...</div>
          ) : (
            <JobList
              jobs={jobs}
              selectedId={selectedJob?.id}
              onSelect={handleJobClick}
              onFavorite={handleFavorite}
            />
          )}
        </div>

        <div className="right-panel">
          {selectedJob ? (
            <JobDetail
              job={selectedJob}
              onAnalyze={() => handleAnalyze(selectedJob.id)}
              onStatusUpdate={(status) => handleStatusUpdate(selectedJob.id, status)}
              onRefresh={() => handleJobClick(selectedJob)}
            />
          ) : (
            <div className="empty-detail">
              <div className="empty-icon">🎯</div>
              <h3>Select a job to view details</h3>
              <p>
                Use <strong>Search Jobs</strong> to find remote tech roles, or use{" "}
                <strong>Paste Job</strong> to add any job from LinkedIn, Indeed, Dice,
                or any company careers page.
              </p>
              <div className="empty-steps">
                <div className="empty-step">
                  <span className="step-num">1</span>
                  <span>Paste a LinkedIn/Indeed/Dice job URL or description text</span>
                </div>
                <div className="empty-step">
                  <span className="step-num">2</span>
                  <span>Get instant ATS score — see matched and missing keywords</span>
                </div>
                <div className="empty-step">
                  <span className="step-num">3</span>
                  <span>Run AI Analysis — get tailored resume, cold email, interview strategy</span>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
