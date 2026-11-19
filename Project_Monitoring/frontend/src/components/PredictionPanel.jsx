
function PredictionPanel({ prediction }) {
  if (!prediction) {
    return (
      <div className="prediction-panel">
        <h2>Prédiction de panne</h2>
        <p>Aucune prédiction disponible pour cette machine.</p>
      </div>
    );
  }

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
      </div>
    </div>
  );
}

export default PredictionPanel;
