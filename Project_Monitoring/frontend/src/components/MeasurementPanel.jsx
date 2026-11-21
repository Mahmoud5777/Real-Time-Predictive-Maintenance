import Pagination from "./Pagination";

function formatDate(value) {
  if (!value) return "Non disponible";

  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Non disponible"
    : date.toLocaleString("fr-FR");
}

function formatValue(value, unit = "") {
  return value == null || value === ""
    ? "Non disponible"
    : `${value}${unit}`;
}

function MeasurementPanel({
  measurement,
  measurements,
  total,
  offset,
  pageSize,
  onPageChange,
  loading,
  error,
}) {
  const sensors = [
    { label: "Température", key: "temperature", unit: " °C" },
    { label: "Vibrations", key: "vibration", unit: "" },
    { label: "Pression", key: "pressure", unit: "" },
    { label: "Vitesse", key: "speed", unit: " tr/min" },
    { label: "Courant électrique", key: "current", unit: " A" },
    { label: "Puissance", key: "power", unit: " kW" },
    { label: "Fréquence", key: "frequency", unit: " Hz" },
  ];

  const stateLabels = {
    operational: "En fonctionnement",
    running: "En fonctionnement",
    normal: "Normal",
    warning: "Warning",
    critical: "Critical",
    offline: "Hors service",
    idle: "Au repos",
    stopped: "Arrêtée",
    fault: "Défaut",
  };

  return (
    <div className="measurement-panel">
      <div className="measurement-heading">
        <h2>Dernière mesure</h2>
        <span>
          Machine : {measurement?.machine_id ?? measurements[0]?.machine_id ?? "Non renseignée"}
        </span>
      </div>

      {measurement ? (
        <>
          <div className="measurement-timestamps">
            <div>
              <span>Date source</span>
              <strong>{formatDate(measurement.timestamp)}</strong>
            </div>
            <div>
              <span>Reçue par l’API</span>
              <strong>{formatDate(measurement.received_at)}</strong>
            </div>
          </div>

          <div className="sensor-grid">
            {sensors.map((sensor) => (
              <div className="sensor-card" key={sensor.key}>
                <span className="sensor-label">{sensor.label}</span>
                <strong className="sensor-value">
                  {formatValue(measurement[sensor.key], sensor.unit)}
                </strong>
              </div>
            ))}
          </div>

          <div className={`measurement-state ${measurement.state ?? ""}`}>
            État de fonctionnement :{" "}
            {stateLabels[measurement.state?.toLowerCase()] ??
              measurement.state ??
              "Non disponible"}
          </div>
        </>
      ) : (
        <p>Aucune mesure disponible pour cette machine.</p>
      )}

      <section className="measurement-history" aria-labelledby="measurement-history-title">
        <div className="measurement-history-heading">
          <div>
            <h3 id="measurement-history-title">Historique des mesures</h3>
            <p>Mesures réelles retournées par l’API pour cette machine.</p>
          </div>
        </div>

        {error && <p className="panel-error" role="alert">{error}</p>}
        {loading && measurements.length === 0 && (
          <p role="status">Chargement de l’historique…</p>
        )}
        {!loading && !error && measurements.length === 0 && (
          <p>Aucune mesure historique disponible.</p>
        )}

        {measurements.length > 0 && (
          <div className="measurement-history-scroll">
            <table className="measurement-history-table">
              <thead>
                <tr>
                  <th>Date source</th>
                  <th>Réception</th>
                  <th>Température</th>
                  <th>Vibrations</th>
                  <th>Pression</th>
                  <th>Vitesse</th>
                  <th>Courant</th>
                  <th>Puissance</th>
                  <th>Fréquence</th>
                  <th>État</th>
                </tr>
              </thead>
              <tbody>
                {measurements.map((item) => (
                  <tr key={item.id ?? item.message_id}>
                    <td>{formatDate(item.timestamp)}</td>
                    <td>{formatDate(item.received_at)}</td>
                    <td>{formatValue(item.temperature, " °C")}</td>
                    <td>{formatValue(item.vibration)}</td>
                    <td>{formatValue(item.pressure)}</td>
                    <td>{formatValue(item.speed, " tr/min")}</td>
                    <td>{formatValue(item.current, " A")}</td>
                    <td>{formatValue(item.power, " kW")}</td>
                    <td>{formatValue(item.frequency, " Hz")}</td>
                    <td>
                      {stateLabels[item.state?.toLowerCase()] ??
                        item.state ??
                        "Non disponible"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <Pagination
          offset={offset}
          total={total}
          pageSize={pageSize}
          onPageChange={onPageChange}
          label="mesures"
          singularLabel="mesure"
        />
      </section>
    </div>
  );
}

export default MeasurementPanel;
