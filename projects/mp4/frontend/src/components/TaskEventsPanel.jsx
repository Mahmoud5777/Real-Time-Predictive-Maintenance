import { useState } from "react";
import Pagination from "./Pagination";

function formatDate(value) {
  if (!value) return "Non disponible";

  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Non disponible"
    : date.toLocaleString("fr-FR");
}

function TaskEventCard({ event }) {
  const status = event.status?.toLowerCase() ?? "unknown";
  const priority = event.priority?.toLowerCase() ?? "unknown";
  const eventType = event.event_type ?? "task";
  const sourceNode = event.source_node;
  const destinationNode = event.destination_node;
  const isMigration =
    eventType === "migration" &&
    sourceNode &&
    destinationNode &&
    sourceNode !== destinationNode;
  const isNodeEvent = ["outage", "recovery", "supervision"].includes(eventType);
  const isLocalTask =
    !isNodeEvent &&
    sourceNode &&
    destinationNode &&
    sourceNode === destinationNode;
  const reason =
    typeof event.reason === "string" && event.reason.trim()
      ? event.reason.trim()
      : null;
  const statusLabels = {
    created: "Créée",
    queued: "En attente",
    running: "En cours",
    migrated: "Migrée",
    completed: "Terminée",
    failed: "Échouée",
    recovered: "Récupérée",
    offline: "Hors ligne",
    online: "En ligne",
    reachable: "Joignable",
    unreachable: "Injoignable",
    unknown: "Inconnu",
  };
  const eventTypeLabels = {
    outage: "Panne Fog",
    migration: "Migration",
    recovery: "Récupération",
    failure: "Échec de tâche",
    task: "Traitement de tâche",
    supervision: "Supervision Fog",
  };
  const priorityLabels = {
    low: "Faible",
    medium: "Moyenne",
    high: "Haute",
    critical: "Critique",
  };
  const statusLabel =
    status === "migrated" && !isMigration
      ? "Transfert non confirmé"
      : statusLabels[status] ?? status;

  return (
    <article className={`task-event-card ${eventType}`}>
      <div className="task-event-header">
        <div className="task-event-title">
          <strong>{eventTypeLabels[eventType] ?? eventTypeLabels.task}</strong>
          {event.task_id && (
            <span className="task-event-id">Tâche : {event.task_id}</span>
          )}
          {event.task_type && (
            <span className="task-event-id">Type : {event.task_type}</span>
          )}
        </div>
        <span className={`task-event-status ${status}`}>{statusLabel}</span>
      </div>

      <div className="task-event-route">
        <div className="task-node">
          <span>{isNodeEvent ? "Nœud concerné" : "Source"}</span>
          <strong>{sourceNode ?? "Non renseignée"}</strong>
        </div>
        {!isNodeEvent && isMigration && (
          <span className="task-route-arrow">→</span>
        )}
        {!isNodeEvent && (
          <div className="task-node">
            <span>
              {isMigration
                ? "Destination"
                : isLocalTask
                  ? "Nœud de traitement"
                  : "Destination déclarée"}
            </span>
            <strong>{destinationNode ?? "Non renseignée"}</strong>
          </div>
        )}
      </div>

      <div className="task-event-details">
        {event.priority && (
          <div>
            <span>Priorité</span>
            <strong className={`task-priority ${priority}`}>
              {priorityLabels[priority] ?? priority}
            </strong>
          </div>
        )}
        {event.machine_id && (
          <div>
            <span>Machine</span>
            <strong>{event.machine_id}</strong>
          </div>
        )}
        <div>
          <span>Raison</span>
          <strong>{reason ?? "Non précisée"}</strong>
        </div>
        {event.previous_supervision_status && (
          <div>
            <span>Statut précédent</span>
            <strong>{event.previous_supervision_status}</strong>
          </div>
        )}
        {event.evidence_heartbeat_at && (
          <div>
            <span>Heartbeat observé</span>
            <strong>{formatDate(event.evidence_heartbeat_at)}</strong>
          </div>
        )}
        {event.evidence_received_at && (
          <div>
            <span>Heartbeat reçu</span>
            <strong>{formatDate(event.evidence_received_at)}</strong>
          </div>
        )}
        {event.timeout_seconds != null && (
          <div>
            <span>Timeout</span>
            <strong>{event.timeout_seconds} s</strong>
          </div>
        )}
        {event.gap_start && (
          <div>
            <span>Début d’interruption</span>
            <strong>{formatDate(event.gap_start)}</strong>
          </div>
        )}
        {event.gap_end && (
          <div>
            <span>Fin d’interruption</span>
            <strong>{formatDate(event.gap_end)}</strong>
          </div>
        )}
      </div>

      <div className="task-event-footer">
        Événement : {event.event_id ?? "Non disponible"}
        {" — "}
        <span>Date : {formatDate(event.timestamp)}</span>
      </div>
    </article>
  );
}

function TaskEventsPanel({
  events = [],
  total = events.length,
  offset = 0,
  pageSize,
  onPageChange,
  loading = false,
  error,
  migrationEvents = [],
  migrationTotal = migrationEvents.length,
  migrationOffset = 0,
  onMigrationPageChange,
  migrationLoading = false,
  migrationError,
  supervisionEvents = [],
  supervisionTotal = supervisionEvents.length,
  supervisionOffset = 0,
  onSupervisionPageChange,
  supervisionLoading = false,
  supervisionError,
}) {
  const [activeTab, setActiveTab] = useState("tasks");
  const showingTasks = activeTab === "tasks";
  const showingSupervision = activeTab === "supervision";
  const showingMigrations = activeTab === "migrations";
  const items = showingSupervision
    ? supervisionEvents
    : showingMigrations
      ? migrationEvents
      : events;
  const itemTotal = showingSupervision
    ? supervisionTotal
    : showingMigrations
      ? migrationTotal
      : total;
  const itemOffset = showingSupervision
    ? supervisionOffset
    : showingMigrations
      ? migrationOffset
      : offset;
  const isLoading = showingSupervision
    ? supervisionLoading
    : showingMigrations
      ? migrationLoading
      : loading;
  const currentError = showingSupervision
    ? supervisionError
    : showingMigrations
      ? migrationError
      : error;
  const handlePageChange = showingSupervision
    ? onSupervisionPageChange
    : showingMigrations
      ? onMigrationPageChange
      : onPageChange;
  const paginationLabel = showingSupervision
    ? "enregistrements de supervision"
    : showingMigrations
      ? "événements MIGRATED"
      : "événements";
  const paginationSingularLabel = showingSupervision
    ? "enregistrement de supervision"
    : showingMigrations
      ? "événement MIGRATED"
      : "événement";

  return (
    <div className="task-events-panel">
      <div className="task-events-heading">
        <div>
          <h2>Événements Fog et tâches</h2>
          <p>Les événements et l’historique de supervision sont paginés séparément.</p>
        </div>
      </div>

      <div className="event-tabs" role="tablist" aria-label="Type d’historique">
        <button
          type="button"
          role="tab"
          aria-selected={showingTasks}
          className={showingTasks ? "active" : ""}
          onClick={() => setActiveTab("tasks")}
        >
          Tous les événements de tâches ({total})
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={showingMigrations}
          className={showingMigrations ? "active" : ""}
          onClick={() => setActiveTab("migrations")}
        >
          Événements MIGRATED ({migrationTotal})
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={showingSupervision}
          className={showingSupervision ? "active" : ""}
          onClick={() => setActiveTab("supervision")}
        >
          Supervision ({supervisionTotal})
        </button>
      </div>

      <span className="task-events-count">
        {itemTotal} {itemTotal === 1 ? paginationSingularLabel : paginationLabel}
      </span>
      {currentError && <p className="panel-error" role="alert">{currentError}</p>}
      {isLoading && items.length === 0 && (
        <p role="status">Chargement de l’historique…</p>
      )}
      {!isLoading && items.length === 0 && (
        <p>
          {currentError
            ? "L’historique n’a pas pu être chargé."
            : "Aucun événement correspondant."}
        </p>
      )}

      {items.length > 0 && (
        <div className="task-events-list">
          {items.map((event) => (
            <TaskEventCard key={event.event_id} event={event} />
          ))}
        </div>
      )}

      {pageSize && handlePageChange && (
        <Pagination
          offset={itemOffset}
          total={itemTotal}
          pageSize={pageSize}
          onPageChange={handlePageChange}
          label={paginationLabel}
          singularLabel={paginationSingularLabel}
        />
      )}
    </div>
  );
}

export default TaskEventsPanel;
