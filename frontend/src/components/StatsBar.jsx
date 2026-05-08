export default function StatsBar({ stats }) {
  const cards = [
    { label: "Total Jobs", value: stats.total_jobs, color: "#1A2A4A" },
    { label: "High Fit (80+)", value: stats.high_fit_jobs, color: "#16a34a" },
    { label: "AI Analyzed", value: stats.analyzed_jobs, color: "#7c3aed" },
    { label: "Avg ATS Score", value: `${stats.average_ats_score}%`, color: "#1F5C9E" },
    { label: "Applied", value: stats.by_status?.applied || 0, color: "#d97706" },
    { label: "Interviewing", value: stats.by_status?.interviewing || 0, color: "#059669" },
  ];

  return (
    <div className="stats-bar">
      {cards.map((card) => (
        <div className="stat-card" key={card.label}>
          <div className="stat-value" style={{ color: card.color }}>{card.value}</div>
          <div className="stat-label">{card.label}</div>
        </div>
      ))}
    </div>
  );
}
