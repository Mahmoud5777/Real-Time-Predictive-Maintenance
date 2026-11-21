import Pagination from "./Pagination";

function AlertsPanel({
  alerts = [],
  total = alerts.length,
  offset = 0,
  pageSize,
  onPageChange,
  filters,
  onFilterChange,
  machines = [],
  loading = false,
  error,
  compact = false,
}) {
  const severityLabels = {
    warning: "Avertissement",
    critical: "Critique",
    normal: "Information",
  };

  const statusLabels = {
    open: "Active",
    acknowledged: "Active · prise en compte",
    resolved: "Résolue",
  };

  const formatDate = (date) => {
    if (!date) return "Non disponible";

    const parsedDate = new Date(date);
    return Number.isNaN(parsedDate.getTime())
      ? "Non disponible"
      : parsedDate.toLocaleString("fr-FR");
  };

  return (
    <div className={`alerts-panel ${compact ? "compact" : ""}`}>
      {!compact && (
        <div className="alerts-heading">
          <div>
            <h2>Centre des alertes</h2>
            <p>Incidents réels retournés par l’API</p>
          </div>
          <span className="alerts-count">
            {total} alerte{total === 1 ? "" : "s"} au total
          </span>
        </div>
      )}

      {!compact && onFilterChange && filters && (
        <div className="data-filters" aria-label="Filtres des alertes">
          <label>
            Machine
            <select
              value={filters.machineId}
              onChange={(event) =>
                onFilterChange("machineId", event.target.value)
              }
            >
              <option value="">Toutes</option>
              {machines.map((machine) => (
                <option key={machine.machine_id} value={machine.machine_id}>
                  {machine.machine_id}
                </option>
              ))}
            </select>
          </label>
          <label>
            Statut
            <select
              value={filters.status}
              onChange={(event) => onFilterChange("status", event.target.value)}
            >
              <option value="">Tous</option>
              <option value="OPEN">Active</option>
              <option value="ACKNOWLEDGED">Prise en compte</option>
              <option value="RESOLVED">Résolue</option>
            </select>
          </label>
          <label>
            Gravité
            <select
              value={filters.severity}
              onChange={(event) =>
                onFilterChange("severity", event.target.value)
              }
            >
              <option value="">Toutes</option>
              <option value="WARNING">Avertissement</option>
              <option value="CRITICAL">Critique</option>
              <option value="NORMAL">Information</option>
            </select>
          </label>
        </div>
      )}

      {error && <p className="panel-error" role="alert">{error}</p>}
      {loading && alerts.length === 0 && (
        <p role="status">Chargement des alertes…</p>
      )}
      {!loading && alerts.length === 0 && (
        <p>
          {error
            ? "Les alertes n’ont pas pu être chargées."
            : "Aucune alerte correspondant aux filtres."}
        </p>
      )}

      {alerts.length > 0 && (
        <div className="alerts-list">
          {alerts.map((alert) => {
            const severity = alert.severity?.toLowerCase() ?? "normal";
            const status = alert.status?.toLowerCase() ?? "open";
            const alertState = alert.alert_state ?? "unknown";

            return (
              <div
                className={`alert-card ${alertState} ${severity}`}
                key={alert.alert_id ?? alert.id}
              >
                <div className="alert-card-header">
                  <div className="alert-card-labels">
                    <span className={`severity-badge ${severity}`}>
                      {severityLabels[severity] ?? severity}
                    </span>
                    <span className="alert-id">
                      {alert.alert_id ?? "Identifiant indisponible"}
                    </span>
                  </div>
                  <span className={`alert-status ${alertState} ${severity}`}>
                    {statusLabels[status] ?? "Statut inconnu"}
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
                  <span>Machine : {alert.machine_id ?? "Non renseignée"}</span>
                  <span>Zone : {alert.zone ?? "Non renseignée"}</span>
                </div>
                <div className="alert-date">
                  Date : {formatDate(alert.timestamp)}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {!compact && pageSize && onPageChange && (
        <Pagination
          offset={offset}
          total={total}
          pageSize={pageSize}
          onPageChange={onPageChange}
          label="alertes"
          singularLabel="alerte"
        />
      )}
    </div>
  );
}

export default AlertsPanel;
