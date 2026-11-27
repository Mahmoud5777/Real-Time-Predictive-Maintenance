import { api } from "./api";

export const DEFAULT_PAGE_SIZE = 20;

function normalizeAlert(alert, machineById) {
  const status =
    typeof alert.status === "string" ? alert.status.toLowerCase() : "unknown";
  const severity =
    typeof alert.severity === "string" ? alert.severity.toLowerCase() : "unknown";

  return {
    ...alert,
    title: alert.title ?? alert.type,
    description: alert.description ?? alert.message,
    severity,
    status,
    alert_state: {
      open: "active",
      acknowledged: "active",
      resolved: "resolved",
    }[status] ?? "unknown",
    zone: alert.zone ?? machineById?.get(alert.machine_id)?.zone ?? "Inconnue",
  };
}

function normalizeFogNode(node) {
  const rawStatus =
    typeof node.status === "string" ? node.status.toLowerCase() : "unknown";

  return {
    ...node,
    node_id: node.node_id ?? node.fog_id,
    cpu_usage: node.cpu_usage ?? node.cpu_percent,
    ram_usage: node.ram_usage ?? node.ram_percent,
    queue_length: node.queue_length ?? node.queued_tasks,
    status: rawStatus === "overloaded" ? "warning" : rawStatus,
  };
}

function normalizeTaskEvent(event) {
  const status =
    typeof event.status === "string" ? event.status.toLowerCase() : "unknown";
  const sourceNode = event.source_node ?? event.source_fog;
  const destinationNode = event.destination_node ?? event.destination_fog;
  const isMigration =
    status === "migrated" &&
    typeof sourceNode === "string" &&
    typeof destinationNode === "string" &&
    sourceNode !== destinationNode;
  const inferredType = {
    failed: "failure",
    recovered: "recovery",
    offline: "outage",
  }[status] ?? (isMigration ? "migration" : "task");
  const eventType = event.event_type ?? inferredType;

  return {
    ...event,
    event_id: event.event_id ?? event.id,
    event_type: eventType === "migration" && !isMigration ? "task" : eventType,
    source_node: sourceNode,
    destination_node: destinationNode,
    priority:
      typeof event.priority === "string"
        ? event.priority.toLowerCase()
        : event.priority,
    status,
    reason: event.reason ?? event.supervision_reason,
    timestamp:
      event.timestamp ??
      event.occurred_at ??
      event.observed_at ??
      event.created_at,
  };
}

function normalizeSupervisionEvent(event) {
  const supervisionStatus = event.supervision_status?.toUpperCase();
  const isOutage = supervisionStatus === "UNREACHABLE";
  const isRecovery =
    supervisionStatus === "REACHABLE" &&
    event.previous_supervision_status === "UNREACHABLE";
  const status = isOutage
    ? "offline"
    : supervisionStatus === "REACHABLE"
      ? "online"
      : supervisionStatus?.toLowerCase() ?? "unknown";

  return normalizeTaskEvent({
    ...event,
    event_id: `supervision-${event.id}`,
    event_type: isOutage ? "outage" : isRecovery ? "recovery" : "supervision",
    status,
    source_fog: event.fog_id,
    reason: event.supervision_reason,
    observed_at: event.observed_at,
  });
}

function readPage(response, resource) {
  if (
    !response ||
    !Array.isArray(response.items) ||
    !response.meta ||
    !Number.isInteger(response.meta.total)
  ) {
    throw new Error(`Réponse API invalide pour ${resource}.`);
  }

  return {
    items: response.items,
    total: response.meta.total,
    limit: response.meta.limit,
    offset: response.meta.offset,
  };
}

function toQueryString(parameters) {
  const query = new URLSearchParams();

  Object.entries(parameters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  });

  return query.toString();
}

async function getNormalizedPage(path, parameters, resource, normalizeItems) {
  const query = toQueryString(parameters);
  const response = await api.get(`${path}${query ? `?${query}` : ""}`);
  const page = readPage(response, resource);

  return {
    ...page,
    items: page.items.map(normalizeItems),
  };
}

function normalizeMeasurement(measurement) {
  return {
    ...measurement,
    state: {
      RUNNING: "operational",
      IDLE: "idle",
      STOPPED: "offline",
      FAULT: "critical",
    }[measurement.state] ?? measurement.state,
  };
}

function normalizePrediction(prediction) {
  return {
    ...prediction,
    risk_score:
      prediction.risk_score == null
        ? null
        : Number(prediction.risk_score) * 100,
    anomaly_detected: prediction.anomaly,
  };
}

export async function getDashboardData() {
  let machinesResponse;
  let measurementsResponse;
  let predictionsResponse;
  let recentAlertsResponse;
  let openAlertsResponse;
  let acknowledgedAlertsResponse;
  let resolvedAlertsResponse;
  let fogResponse;

  try {
    [
      machinesResponse,
      measurementsResponse,
      predictionsResponse,
      recentAlertsResponse,
      openAlertsResponse,
      acknowledgedAlertsResponse,
      resolvedAlertsResponse,
      fogResponse,
    ] = await Promise.all([
      api.get("/api/v1/machines?limit=1000"),
      api.get("/api/v1/measurements?limit=1000&sort=-timestamp"),
      api.get("/api/v1/predictions?limit=1000&sort=-timestamp"),
      api.get("/api/v1/alerts?limit=2&sort=-timestamp"),
      api.get("/api/v1/alerts?status=OPEN&limit=1"),
      api.get("/api/v1/alerts?status=ACKNOWLEDGED&limit=1"),
      api.get("/api/v1/alerts?status=RESOLVED&limit=1"),
      api.get("/api/v1/fog/nodes?limit=1000"),
    ]);
  } catch (err) {
    throw new Error(
      `Connexion au backend MP3 (FastAPI) impossible : ${err.message}. ` +
      `Vérifiez que l'API Cloud MP3 est démarrée et accessible sur le réseau Docker.`
    );
  }

  const machinesPage = readPage(machinesResponse, "machines");
  const measurementsPage = readPage(measurementsResponse, "mesures");
  const predictionsPage = readPage(predictionsResponse, "prédictions");
  const recentAlertsPage = readPage(recentAlertsResponse, "alertes récentes");
  const openAlertsPage = readPage(openAlertsResponse, "alertes ouvertes");
  const acknowledgedAlertsPage = readPage(
    acknowledgedAlertsResponse,
    "alertes prises en compte"
  );
  const resolvedAlertsPage = readPage(
    resolvedAlertsResponse,
    "alertes résolues"
  );
  const fogPage = readPage(fogResponse, "nœuds Fog");

  const measurements = measurementsPage.items.map(normalizeMeasurement);
  const predictions = predictionsPage.items.map(normalizePrediction);
  const latestMeasurements = new Map();
  const latestPredictions = new Map();

  for (const measurement of measurements) {
    if (!latestMeasurements.has(measurement.machine_id)) {
      latestMeasurements.set(measurement.machine_id, measurement);
    }
  }

  for (const prediction of predictions) {
    if (!latestPredictions.has(prediction.machine_id)) {
      latestPredictions.set(prediction.machine_id, prediction);
    }
  }

  const machineById = new Map(
    machinesPage.items.map((machine) => [machine.machine_id, machine])
  );
  const machines = machinesPage.items.map((machine) => {
    const prediction = latestPredictions.get(machine.machine_id);
    const measurement = latestMeasurements.get(machine.machine_id);
    const predictionSeverity = prediction?.severity?.toUpperCase();
    const measurementState = measurement?.state?.toUpperCase();
    let status = "unknown";

    if (
      predictionSeverity === "CRITICAL" ||
      measurementState === "FAULT" ||
      measurementState === "CRITICAL"
    ) {
      status = "critical";
    } else if (predictionSeverity === "WARNING") {
      status = "warning";
    } else if (measurementState === "STOPPED" || measurementState === "OFFLINE") {
      status = "offline";
    } else if (measurementState === "IDLE") {
      status = "idle";
    } else if (
      measurementState === "RUNNING" ||
      measurementState === "OPERATIONAL"
    ) {
      status = "operational";
    } else if (predictionSeverity === "NORMAL") {
      status = "operational";
    }

    return { ...machine, status };
  });

  return {
    machines,
    machineTotal: machinesPage.total,
    recentAlerts: recentAlertsPage.items.map((alert) =>
      normalizeAlert(alert, machineById)
    ),
    alertCounts: {
      active:
        openAlertsPage.total + acknowledgedAlertsPage.total,
      resolved: resolvedAlertsPage.total,
      total: recentAlertsPage.total,
    },
    fogNodes: fogPage.items.map(normalizeFogNode),
    fogNodeTotal: fogPage.total,
  };
}

export function getMeasurementPage({ machineId, limit, offset }) {
  return getNormalizedPage(
    "/api/v1/measurements",
    {
      machine_id: machineId,
      sort: "-timestamp",
      limit,
      offset,
    },
    "historique des mesures",
    normalizeMeasurement
  );
}

export function getPredictionPage({ filters, limit, offset }) {
  return getNormalizedPage(
    "/api/v1/predictions",
    {
      machine_id: filters.machineId,
      severity: filters.severity,
      anomaly: filters.anomaly,
      sort: "-timestamp",
      limit,
      offset,
    },
    "prédictions",
    normalizePrediction
  );
}

export function getAlertPage({ filters, limit, offset, machines = [] }) {
  const machineById = new Map(
    machines.map((machine) => [machine.machine_id, machine])
  );

  return getNormalizedPage(
    "/api/v1/alerts",
    {
      machine_id: filters.machineId,
      status: filters.status,
      severity: filters.severity,
      sort: "-timestamp",
      limit,
      offset,
    },
    "alertes",
    (alert) => normalizeAlert(alert, machineById)
  );
}

export function getTaskEventPage({ limit, offset, status }) {
  return getNormalizedPage(
    "/api/v1/tasks/events",
    {
      status,
      sort: "-created_at",
      limit,
      offset,
    },
    "événements de tâches",
    normalizeTaskEvent
  );
}

export function getMigrationPage({ limit, offset }) {
  return getTaskEventPage({ limit, offset, status: "MIGRATED" });
}

export function getSupervisionPage({ limit, offset }) {
  return getNormalizedPage(
    "/api/v1/fog/supervision-history",
    {
      sort: "-observed_at",
      limit,
      offset,
    },
    "historique de supervision",
    normalizeSupervisionEvent
  );
}
