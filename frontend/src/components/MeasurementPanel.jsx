
function MeasurementPanel({ measurement }) {
  if (!measurement) {
    return (
      <div className="measurement-panel">
        <h2>Mesures de la machine</h2>
        <p>Aucune mesure disponible pour cette machine.</p>
      </div>
    );
  }

  const formatValue = (value, unit = "") => {
    if (value == null || value === "") {
      return "Non disponible";
    }

    return `${value}${unit}`;
  };

  const sensors = [
    {
      label: "Température",
      value: formatValue(measurement.temperature, " °C"),
    },
    {
      label: "Vibrations",
      value: formatValue(measurement.vibration),
    },
    {
      label: "Pression",
      value: formatValue(measurement.pressure),
    },
    {
      label: "Vitesse",
      value: formatValue(measurement.speed, " tr/min"),
    },
    {
      label: "Courant électrique",
      value: formatValue(measurement.current, " A"),
    },
    {
      label: "Puissance",
      value: formatValue(measurement.power, " kW"),
    },
    {
      label: "Fréquence",
      value: formatValue(measurement.frequency, " Hz"),
    },
  ];

  const stateLabels = {
    operational: "Opérationnel",
    warning: "Attention",
    critical: "Critique",
    offline: "Hors service",
    idle: "Au repos",
    RUNNING: "En fonctionnement",
    IDLE: "Au repos",
    STOPPED: "Arrêtée",
    FAULT: "En panne",
  };

  return (
    <div className="measurement-panel">
      <div className="measurement-heading">
        <h2>Mesures de la machine</h2>
        <span>Machine : {measurement.machine_id}</span>
      </div>

      <div className="sensor-grid">
        {sensors.map((sensor) => (
          <div className="sensor-card" key={sensor.label}>
            <span className="sensor-label">{sensor.label}</span>
            <strong className="sensor-value">{sensor.value}</strong>
          </div>
        ))}
      </div>

      <div className="measurement-state">
        État de fonctionnement :{" "}
        {stateLabels[measurement.state] ?? measurement.state ?? "Non disponible"}
      </div>
    </div>
  );
}

export default MeasurementPanel;
