
function TaskEventsPanel({ events }) {
  if (!events || events.length === 0) {
    return (
      <div className="task-events-panel">
        <h2>Événements de migration</h2>
        <p>Aucun événement disponible.</p>
      </div>
    );
  }

  const statusLabels = {
    created: "Créée",
    queued: "En attente",
    running: "En cours",
    migrated: "Migrée",
    completed: "Terminée",
    failed: "Échouée",
    recovered: "Récupérée",

    // Compatibilité avec les anciennes données mock
    in_progress: "En cours",
    local: "Locale",
  };

  const priorityLabels = {
    low: "Faible",
    medium: "Moyenne",
    high: "Haute",
    critical: "Critique",
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
    <div className="task-events-panel">
      <div className="task-events-heading">
        <div>
          <h2>Événements de migration</h2>
          <p>Répartition des tâches entre les nœuds Fog</p>
        </div>

        <span className="task-events-count">
          {events.length} événements
        </span>
      </div>

      <div className="task-events-list">
        {events.map((event) => {
          const status = event.status?.toLowerCase() ?? "unknown";
          const priority = event.priority?.toLowerCase() ?? "unknown";

          return (
            <div className="task-event-card" key={event.event_id}>
              <div className="task-event-header">
                <strong>{event.task_id ?? "Tâche inconnue"}</strong>

                <span className={`task-event-status ${status}`}>
                  {statusLabels[status] ?? status}
                </span>
              </div>

              <div className="task-event-route">
                <div className="task-node">
                  <span>Source</span>
                  <strong>{event.source_node ?? "Non renseignée"}</strong>
                </div>

                <span className="task-route-arrow">→</span>

                <div className="task-node">
                  <span>Destination</span>
                  <strong>
                    {event.destination_node ?? "Traitement local"}
                  </strong>
                </div>
              </div>

              <div className="task-event-details">
                <div>
                  <span>Priorité</span>
                  <strong className={`task-priority ${priority}`}>
                    {priorityLabels[priority] ?? priority}
                  </strong>
                </div>

                <div>
                  <span>Raison</span>
                  <strong>{event.reason ?? "Non précisée"}</strong>
                </div>
              </div>

              <div className="task-event-footer">
  		Événement : {event.event_id ?? "Non disponible"}
  		{" — "}
  		<span>{formatDate(event.timestamp)}</span>
	      </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default TaskEventsPanel;
