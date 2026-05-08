import { useState } from "react";

export default function SearchPanel({ onSearch, onPaste, searching, pasting }) {
  const [activeTab, setActiveTab] = useState("search");

  // Search tab state
  const [query, setQuery] = useState(".NET Developer");
  const [location, setLocation] = useState("remote");
  const [limit, setLimit] = useState(5);

  // Paste tab state
  const [pasteInput, setPasteInput] = useState("");
  const [titleOverride, setTitleOverride] = useState("");
  const [companyOverride, setCompanyOverride] = useState("");
  const [locationOverride, setLocationOverride] = useState("");
  const [showOverrides, setShowOverrides] = useState(false);

  const handlePaste = () => {
    if (!pasteInput.trim()) return;
    onPaste(
      pasteInput.trim(),
      titleOverride.trim() || null,
      companyOverride.trim() || null,
      locationOverride.trim() || null,
    );
  };

  const isUrl = (text) =>
    text.trim().startsWith("http://") ||
    text.trim().startsWith("https://") ||
    text.trim().startsWith("www.");

  const inputIsUrl = isUrl(pasteInput);

  return (
    <div className="search-panel">
      <div className="panel-tabs">
        <button
          className={`panel-tab ${activeTab === "search" ? "active" : ""}`}
          onClick={() => setActiveTab("search")}
        >
          🔍 Search Jobs
        </button>
        <button
          className={`panel-tab ${activeTab === "paste" ? "active" : ""}`}
          onClick={() => setActiveTab("paste")}
        >
          📋 Paste Job
        </button>
      </div>

      {activeTab === "search" && (
        <div className="panel-body">
          <p className="panel-hint">
            Searches Himalayas, Remotive, Jobicy, Arbeitnow and Indeed simultaneously.
          </p>
          <div className="search-row">
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Job title or keywords"
              className="search-input"
              onKeyDown={(e) => e.key === "Enter" && onSearch(query, location, limit)}
            />
            <input
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="Location or remote"
              className="search-input"
              onKeyDown={(e) => e.key === "Enter" && onSearch(query, location, limit)}
            />
          </div>
          <div className="search-row">
            <label className="limit-label">
              Per source:
              <select
                value={limit}
                onChange={(e) => setLimit(Number(e.target.value))}
                className="limit-select"
              >
                <option value={3}>3</option>
                <option value={5}>5</option>
                <option value={10}>10</option>
              </select>
            </label>
            <button
              onClick={() => onSearch(query, location, limit)}
              disabled={searching}
              className="btn-search"
            >
              {searching ? "Searching..." : "Search →"}
            </button>
          </div>
        </div>
      )}

      {activeTab === "paste" && (
        <div className="panel-body">
          <p className="panel-hint">
            Found a job on <strong>LinkedIn, Indeed, Dice</strong> or any site?
            Paste the <strong>URL</strong> or the <strong>job description text</strong> below.
          </p>

          <textarea
            className="paste-textarea"
            value={pasteInput}
            onChange={(e) => setPasteInput(e.target.value)}
            placeholder={"Paste a job URL:\nhttps://www.linkedin.com/jobs/view/...\n\nOR paste the job description text:\n\nSoftware Engineer at Acme Corp\nWe are looking for a Full Stack .NET Developer..."}
            rows={7}
          />

          {pasteInput.trim() && (
            <div className="paste-detected">
              {inputIsUrl ? (
                <span className="detected-url">🔗 URL — will fetch job from page</span>
              ) : (
                <span className="detected-text">📄 Text — will parse directly</span>
              )}
            </div>
          )}

          <button
            className="btn-overrides-toggle"
            onClick={() => setShowOverrides(!showOverrides)}
          >
            {showOverrides ? "▲ Hide" : "▼ Override"} extracted fields (optional)
          </button>

          {showOverrides && (
            <div className="overrides-row">
              <input
                value={titleOverride}
                onChange={(e) => setTitleOverride(e.target.value)}
                placeholder="Job title override"
                className="search-input"
              />
              <input
                value={companyOverride}
                onChange={(e) => setCompanyOverride(e.target.value)}
                placeholder="Company name override"
                className="search-input"
              />
              <input
                value={locationOverride}
                onChange={(e) => setLocationOverride(e.target.value)}
                placeholder="Location override"
                className="search-input"
              />
            </div>
          )}

          <button
            onClick={handlePaste}
            disabled={pasting || !pasteInput.trim()}
            className="btn-paste"
          >
            {pasting ? "Processing..." : "Add Job + Score ATS →"}
          </button>
        </div>
      )}
    </div>
  );
}
