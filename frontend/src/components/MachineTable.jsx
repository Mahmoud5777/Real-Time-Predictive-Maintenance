
function MachineTable({ machines }) {
  const statusLabels = {
    operational: "Opérationnelle",
    warning: "Attention",
    critical: "Critique",
    offline: "Hors service",
    idle: "Au repos",
    unknown: "Inconnu",
  };

  if (!machines || machines.length === 0) {
    return (
      <div className="machine-table-container">
        <div className="table-heading">
          <h2>Machines industrielles</h2>
          <span>0 machine</span>
        </div>
        <p>Aucune machine disponible.</p>
      </div>
    );
  }

  return (
    <div className="machine-table-container">
      <div className="table-heading">
        <h2>Machines industrielles</h2>
        <span>{machines.length} machines</span>
      </div>

      <table className="machine-table">
        <thead>
          <tr>
            <th>Identifiant</th>
            <th>Nom</th>
            <th>Type</th>
            <th>Zone</th>
            <th>Nœud Fog</th>
            <th>État</th>
          </tr>
        </thead>

        <tbody>
          {machines.map((machine) => {
            const status = machine.status ?? "unknown";

            return (
              <tr key={machine.machine_id}>
                <td>{machine.machine_id}</td>
                <td className="machine-name">
                  {machine.name ?? "Non renseigné"}
                </td>
                <td>{machine.machine_type ?? "Non renseigné"}</td>
                <td>
                  {machine.zone != null
                    ? `Zone ${machine.zone}`
                    : "Non renseignée"}
                </td>
                <td>{machine.fog_id ?? "Non affecté"}</td>
                <td>
                  <span className={`machine-status ${status}`}>
                    {statusLabels[status] ?? status}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default MachineTable;
