
function Sidebar({ activePage, setActivePage }) {
  const menuItems = [
    { id: "overview", label: "Vue d'ensemble", icon: "▦" },
    { id: "machines", label: "Machines", icon: "⚙" },
    { id: "predictions", label: "Maintenance Prédictive", icon: "◉" },
    { id: "alerts", label: "Alertes", icon: "⚠" },
    { id: "fog", label: "Surveillance Fog", icon: "☁" },
    { id: "events", label: "Événements et migrations", icon: "⇄" },
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="brand-icon">⚡</div>
        <div>
          <h2>FogMonitor</h2>
          <p>Plateforme industrielle</p>
        </div>
      </div>

      <p className="sidebar-section-title">MENU PRINCIPAL</p>

      <nav className="sidebar-nav">
        {menuItems.map((item) => (
          <button
            key={item.id}
            className={`sidebar-link ${
              activePage === item.id ? "active" : ""
            }`}
            onClick={() => setActivePage(item.id)}
          >
            <span className="sidebar-icon">{item.icon}</span>
            <span>{item.label}</span>
          </button>
        ))}
      </nav>

      <div className="sidebar-footer">
        <span className="status-dot"></span>
        Surveillance du système active
      </div>
    </aside>
  );
}

export default Sidebar;
