
function Header({ activePage }) {
  const pageTitles = {
    overview: {
      title: "Vue d'ensemble",
      description: "Surveillez vos machines et anticipez les pannes.",
    },
    machines: {
      title: "Machines industrielles",
      description: "Consultez l'état et les mesures de vos équipements.",
    },
    predictions: {
      title: "Maintenance prédictive",
      description: "Détectez les anomalies et anticipez les défaillances.",
    },
    alerts: {
      title: "Centre des alertes",
      description: "Consultez les incidents et suivez leur résolution.",
    },
    fog: {
      title: "Surveillance Fog",
      description: "Suivez les ressources et les tâches des nœuds Fog.",
    },
    events: {
      title: "Événements et migrations",
      description: "Suivez les déplacements des tâches entre les nœuds Fog.",
    },
  };

  const currentPage = pageTitles[activePage] || pageTitles.overview;

  return (
    <header className="dashboard-header">
      <div>
        <h1>{currentPage.title}</h1>
        <p>{currentPage.description}</p>
      </div>

      <div className="header-right">
        <div className="system-status">
          <span className="status-dot"></span>
          Système actif
        </div>

        <div className="header-date">
          {new Date().toLocaleDateString("fr-FR", {
            day: "2-digit",
            month: "short",
            year: "numeric",
          })}
        </div>
      </div>
    </header>
  );
}

export default Header;
