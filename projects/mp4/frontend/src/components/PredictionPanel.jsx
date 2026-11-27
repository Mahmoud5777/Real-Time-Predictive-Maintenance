import Pagination from "./Pagination";

function formatDate(value) {
  if (!value) return "Non disponible";

  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Non disponible"
    : date.toLocaleString("fr-FR");
}

function PredictionCard({ prediction }) {
  const rawScore = Number(prediction.risk_score);
  const hasValidScore =
    prediction.risk_score !== null &&
    prediction.risk_score !== undefined &&
    Number.isFinite(rawScore);
  const riskScore = hasValidScore
    ? Math.min(100, Math.max(0, rawScore))
    : null;
  const severity = prediction.severity?.toUpperCase();

  const getRiskLevel = () => {
    if (severity === "CRITICAL") return "high";
    if (severity === "WARNING") return "medium";
    if (severity === "NORMAL") return "low";
    if (riskScore === null) return "unknown";
    if (riskScore >= 70) return "high";
    if (riskScore >= 30) return "medium";
    return "low";
  };

  const riskLabels = {
    low: "Faible",
    medium: "Modéré",
    high: "Élevé",
    unknown: "Indéterminé",
  };
  const riskLevel = getRiskLevel();

  return (
    <article className="prediction-card">
      <div className="prediction-machine">
        <span>Machine</span>
        <strong>{prediction.machine_id ?? "Non renseignée"}</strong>
      </div>
      <div className="prediction-panel">
        <div className="prediction-heading">
          <div>
            <h2>Prédiction de panne</h2>
            <p>Évaluation du risque de défaillance</p>
          </div>
          <span className={`risk-badge ${riskLevel}`}>
            Risque {riskLabels[riskLevel]}
          </span>
        </div>

        <div className="risk-information">
          <div className="risk-score">
            <strong>
              {riskScore !== null ? `${riskScore.toFixed(1)}%` : "N/D"}
            </strong>
            <span>Score de risque</span>
          </div>
          <div className="risk-progress">
            <div
              className={`risk-progress-fill ${riskLevel}`}
              style={{ width: `${riskScore ?? 0}%` }}
            />
          </div>
        </div>

        <div className="prediction-details">
          <div className="prediction-item">
            <span>Anomalie détectée</span>
            <strong className={prediction.anomaly_detected ? "detected" : "normal"}>
              {prediction.anomaly_detected ? "Oui" : "Non"}
            </strong>
          </div>
          <div className="prediction-item">
            <span>Défaillance suspectée</span>
            <strong>
              {prediction.predicted_fault || "Aucune défaillance suspectée"}
            </strong>
          </div>
          <div className="prediction-item">
            <span>Date source</span>
            <strong>{formatDate(prediction.timestamp)}</strong>
          </div>
          <div className="prediction-item">
            <span>Modèle</span>
            <strong>{prediction.model_version ?? "Non renseigné"}</strong>
          </div>
        </div>
      </div>
    </article>
  );
}

function PredictionPanel({
  predictions = [],
  total = predictions.length,
  offset = 0,
  pageSize,
  onPageChange,
  filters,
  onFilterChange,
  machines = [],
  loading = false,
  error,
}) {
  return (
    <div className="predictions-list">
      {filters && onFilterChange && (
        <div className="data-filters" aria-label="Filtres des prédictions">
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
              <option value="NORMAL">Normale</option>
            </select>
          </label>
          <label>
            Anomalie
            <select
              value={filters.anomaly}
              onChange={(event) =>
                onFilterChange("anomaly", event.target.value)
              }
            >
              <option value="">Toutes</option>
              <option value="true">Détectée</option>
              <option value="false">Non détectée</option>
            </select>
          </label>
        </div>
      )}

      <div className="prediction-results-heading">
        <span>
          {total} prédiction{total === 1 ? "" : "s"} correspondant aux filtres
        </span>
      </div>
      {error && <p className="panel-error" role="alert">{error}</p>}
      {loading && predictions.length === 0 && (
        <p role="status">Chargement des prédictions…</p>
      )}
      {!loading && predictions.length === 0 && (
        <p>
          {error
            ? "Les prédictions n’ont pas pu être chargées."
            : "Aucune prédiction correspondant aux filtres."}
        </p>
      )}

      {predictions.length > 0 && (
        <div className="predictions-grid">
          {predictions.map((prediction) => (
            <PredictionCard
              key={prediction.id ?? prediction.message_id}
              prediction={prediction}
            />
          ))}
        </div>
      )}

      {pageSize && onPageChange && (
        <Pagination
          offset={offset}
          total={total}
          pageSize={pageSize}
          onPageChange={onPageChange}
          label="prédictions"
          singularLabel="prédiction"
        />
      )}
    </div>
  );
}

export default PredictionPanel;
