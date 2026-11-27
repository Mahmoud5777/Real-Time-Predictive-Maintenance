function StatCard({ title, value, subtitle, icon, color }) {
  return (
    <div className={`stat-card ${color}`}>
      <div className="stat-card-top">
        <span className="stat-card-title">{title}</span>
        <span className="stat-card-icon">{icon}</span>
      </div>

      <div className="stat-card-value">{value}</div>

      <p className="stat-card-subtitle">{subtitle}</p>
    </div>
  );
}

export default StatCard;