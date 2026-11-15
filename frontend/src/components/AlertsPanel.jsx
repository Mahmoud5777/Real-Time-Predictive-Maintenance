
function AlertsPanel({ alerts, compact = false }) {
  if (!alerts || alerts.length === 0) {
    return (
      <div className={`alerts-panel ${compact ? "compact" : ""}`}>
        {!compact && <h2>Centre des alertes</h2>}
        <p>Aucune alerte disponible.</p>
      </div>
    );
  }

  const severityLabels = {
    warning: "Avertissement",
    critical: "Critique",
    normal: "Information",
  };

  const statusLabels = {
    open: "Ouverte",
    acknowledged: "Prise en compte",
    resolved: "Résolue",
  };

  const formatDate = (date) => {
    if (!date) return "Non disponible";

    const parsedDate = new Date(date);

    if (Number.isNaN(parsedDate.getTime())) {
      return "Non disponible";
    }

    return parsedDate.toLocaleString("fr-FR");
  };

  return (
    <div className={`alerts-panel ${compact ? "compact" : ""}`}>
      {!compact && (
        <div className="alerts-heading">
          <div>
            <h2>Centre des alertes</h2>
            <p>Incidents détectés dans l'usine</p>
          </div>

          <span className="alerts-count">
            {alerts.length} alertes
          </span>
        </div>
      )}

      <div className="alerts-list">
        {alerts.map((alert) => {
          const severity = alert.severity?.toLowerCase() ?? "normal";
          const status = alert.status?.toLowerCase() ?? "open";

          return (
            <div className="alert-card" key={alert.alert_id ?? alert.id}>
              <div className="alert-card-header">
                <div className="alert-card-labels">
                  <span className={`severity-badge ${severity}`}>
                    {severityLabels[severity] ?? severity}
                  </span>

                  <span className="alert-id">
                    {alert.alert_id ?? "Identifiant indisponible"}
                  </span>
                </div>

                <span className={`alert-status ${status}`}>
                  {statusLabels[status] ?? status}
                </span>
              </div>

              <h3>{alert.title ?? alert.type ?? "Alerte"}</h3>

              <p className="alert-description">
                {alert.description ?? alert.message ?? "Aucune description disponible."}
              </p>

              {alert.recommended_action && (
                <p className="alert-description">
                  Action recommandée : {alert.recommended_action}
                </p>
              )}

              <div className="alert-footer">
                <span>
                  Machine : {alert.machine_id ?? "Non renseignée"}
                </span>
                <span>
                  Zone : {alert.zone ?? "Non renseignée"}
                </span>
              </div>

              <div className="alert-date">
                Date : {formatDate(alert.timestamp)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default AlertsPanel;
