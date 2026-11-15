
import machinesData from "../data/machines.json";
import measurementsData from "../data/measurements.json";
import predictionsData from "../data/predictions.json";
import alertsData from "../data/alerts.json";
import fogNodesData from "../data/fogNodes.json";
import taskEventsData from "../data/taskEvents.json";

import { api } from "./api";

const DATA_SOURCE = import.meta.env.VITE_DATA_SOURCE || "mock";

// Récupération des données fictives
async function getMockData() {
  return {
    machines: machinesData.machines,
    measurements: measurementsData.measurements,
    predictions: predictionsData.predictions,
    alerts: alertsData.alerts,
    fogNodes: fogNodesData.fog_nodes,
    taskEvents: taskEventsData.task_events,
  };
}

// Vérification et extraction des éléments paginés
function getItems(response, resource) {
  if (!response || !Array.isArray(response.items)) {
    throw new Error(`Réponse API invalide pour ${resource}.`);
  }

  return response.items;
}

// Récupération des données depuis FastAPI
async function getApiData() {
  const [
    machinesResponse,
    measurementsResponse,
    predictionsResponse,
    alertsResponse,
    fogResponse,
    eventsResponse,
  ] = await Promise.all([
    api.get("/api/v1/machines?limit=1000"),
    api.get("/api/v1/measurements?limit=1000&sort=-timestamp"),
    api.get("/api/v1/predictions?limit=1000&sort=-timestamp"),
    api.get("/api/v1/alerts?limit=1000&sort=-timestamp"),
    api.get("/api/v1/fog/nodes?limit=1000"),
    api.get("/api/v1/tasks/events?limit=1000&sort=-created_at"),
  ]);

  const machines = getItems(machinesResponse, "machines");
  const measurements = getItems(measurementsResponse, "mesures");
  const predictions = getItems(predictionsResponse, "prédictions");
  const alerts = getItems(alertsResponse, "alertes");
  const fogNodes = getItems(fogResponse, "nœuds Fog");
  const taskEvents = getItems(eventsResponse, "événements");

  // Les réponses sont triées par date décroissante.
  // La première mesure/prédiction rencontrée est donc la plus récente.
  const latestMeasurements = new Map();
  for (const measurement of measurements) {
    if (!latestMeasurements.has(measurement.machine_id)) {
      latestMeasurements.set(measurement.machine_id, measurement);
    }
  }

  const latestPredictions = new Map();
  for (const prediction of predictions) {
    if (!latestPredictions.has(prediction.machine_id)) {
      latestPredictions.set(prediction.machine_id, prediction);
    }
  }

  const machineById = new Map(
    machines.map((machine) => [machine.machine_id, machine])
  );

  // Le backend ne fournit pas directement le statut de la machine.
  // On utilise la dernière prédiction, puis la dernière mesure en secours.
  const normalizedMachines = machines.map((machine) => {
    const prediction = latestPredictions.get(machine.machine_id);
    const measurement = latestMeasurements.get(machine.machine_id);

    
let status = "unknown";

const predictionSeverity = prediction?.severity?.toUpperCase();
const measurementState = measurement?.state?.toUpperCase();

if (predictionSeverity === "CRITICAL" || measurementState === "FAULT") {
  status = "critical";
  } else if (predictionSeverity === "WARNING") {
    status = "warning";
  } else if (measurementState === "STOPPED") {
    status = "offline";
  } else if (measurementState === "IDLE") {
    status = "idle";
  } else if (measurementState === "RUNNING") {
    status = "operational";
  } else if (predictionSeverity === "NORMAL") {
    status = "operational";
  }
    return { ...machine, status };
  });

  // Adaptation des mesures pour les composants React
  const normalizedMeasurements = measurements.map((measurement) => ({
    ...measurement,
    state: {
      RUNNING: "operational",
      IDLE: "idle",
      STOPPED: "offline",
      FAULT: "critical",
    }[measurement.state] ?? measurement.state,
  }));

  // Le backend fournit un score entre 0 et 1.
  // Le composant React attend un pourcentage entre 0 et 100.
  const normalizedPredictions = predictions.map((prediction) => ({
    ...prediction,
    risk_score: prediction.risk_score * 100,
    anomaly_detected: prediction.anomaly,
  }));

  // Adaptation des alertes
  const normalizedAlerts = alerts.map((alert) => ({
    ...alert,
    title: alert.type,
    description: alert.message,
    severity: alert.severity.toLowerCase(),
    status: alert.status.toLowerCase(),
    zone: machineById.get(alert.machine_id)?.zone ?? "Inconnue",
  }));

  // Adaptation des nœuds Fog
  const normalizedFogNodes = fogNodes.map((node) => ({
    ...node,
    node_id: node.fog_id,
    cpu_usage: node.cpu_percent,
    ram_usage: node.ram_percent,
    queue_length: node.queued_tasks,
    status: node.status.toLowerCase(),
  }));

  // Adaptation des événements de tâches
  const normalizedTaskEvents = taskEvents.map((event) => ({
    ...event,
    event_id: event.id,
    source_node: event.source_fog,
    destination_node: event.destination_fog,
    priority: event.priority.toLowerCase(),
    status: event.status.toLowerCase(),
    reason: event.reason ?? "Non précisée",
    timestamp: event.occurred_at ?? event.created_at,
  }));

  return {
    machines: normalizedMachines,
    measurements: normalizedMeasurements,
    predictions: normalizedPredictions,
    alerts: normalizedAlerts,
    fogNodes: normalizedFogNodes,
    taskEvents: normalizedTaskEvents,
  };
}

// Fonction principale
export async function getDashboardData() {
  if (DATA_SOURCE === "mock") {
    return await getMockData();
  }

  if (DATA_SOURCE === "api") {
    return await getApiData();
  }

  throw new Error(`Source de données inconnue : ${DATA_SOURCE}`);
}
