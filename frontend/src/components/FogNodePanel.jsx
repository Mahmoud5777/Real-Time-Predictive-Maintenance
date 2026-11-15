function FogNodePanel({ nodes }) {
  if (!nodes || nodes.length === 0) {
    return (
      <div className="fog-panel">
        <h2>Surveillance des nœuds Fog</h2>
        <p>Aucun nœud Fog disponible.</p>
      </div>
    );
  }

  const getLoadLevel = (cpu) => {
    if (cpu == null) return "low";
    if (cpu >= 80) return "high";
    if (cpu >= 60) return "medium";
    return "low";
  };

  const formatPercent = (value) =>
    value == null ? "N/D" : `${value}%`;

  const getProgressWidth = (value) => {
    if (value == null || !Number.isFinite(Number(value))) return "0%";
    return `${Math.min(100, Math.max(0, Number(value)))}%`;
  };

  const formatDate = (date) => {
    if (!date) return "Non disponible";

    const parsedDate = new Date(date);

    if (Number.isNaN(parsedDate.getTime())) {
      return "Non disponible";
    }

    return parsedDate.toLocaleString("fr-FR");
  };

  const statusLabels = {
    online: "En ligne",
    offline: "Hors ligne",
    overloaded: "Surchargé",
    recovering: "En récupération",
  };

  return (
    <div className="fog-panel">
      <div className="fog-heading">
        <div>
          <h2>Surveillance des nœuds Fog</h2>
          <p>Utilisation des ressources et état des nœuds</p>
        </div>

        <span className="fog-count">
          {nodes.length} nœuds
        </span>
      </div>

      <div className="fog-grid">
        {nodes.map((node) => {
          const loadLevel = getLoadLevel(node.cpu_usage);
          const heartbeat = node.last_heartbeat ?? node.last_received_at;

          return (
            <div className="fog-card" key={node.node_id}>
              <div className="fog-card-header">
                <div>
                  <h3>{node.node_id}</h3>
                  <p>Zone {node.zone}</p>
                </div>

                <span className={`fog-status ${node.status}`}>
                  {statusLabels[node.status] ?? node.status}
                </span>
              </div>

              <div className="fog-resource">
                <div className="fog-resource-label">
                  <span>Utilisation du processeur</span>
                  <strong>{formatPercent(node.cpu_usage)}</strong>
                </div>

                <div className="fog-progress">
                  <div
                    className={`fog-progress-fill ${loadLevel}`}
                    style={{ width: getProgressWidth(node.cpu_usage) }}
                  />
                </div>
              </div>

              <div className="fog-resource">
                <div className="fog-resource-label">
                  <span>Utilisation de la mémoire RAM</span>
                  <strong>{formatPercent(node.ram_usage)}</strong>
                </div>

                <div className="fog-progress">
                  <div
                    className="fog-progress-fill low"
                    style={{ width: getProgressWidth(node.ram_usage) }}
                  />
                </div>
              </div>

              <div className="fog-metrics">
                <div>
                  <span>Tâches en attente</span>
                  <strong>{node.queue_length ?? "N/D"}</strong>
                </div>

                <div>
                  <span>Tâches actives</span>
                  <strong>{node.active_tasks ?? "N/D"}</strong>
                </div>
              </div>

              <div className="fog-heartbeat">
                Dernier signal : {formatDate(heartbeat)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default FogNodePanel;