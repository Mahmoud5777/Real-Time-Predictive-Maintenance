
function MachineTable({ machines, total = machines.length }) {
  const statusLabels = {
    normal: "Normal",
    warning: "Warning",
    critical: "Critical",
    offline: "Hors service",
    idle: "Au repos",
    unknown: "Inconnu",
  };

  if (!machines || machines.length === 0) {
    return (
      <div className="machine-table-container">
        <div className="table-heading">
          <h2>Machines industrielles</h2>
          <span>{total} machine{total === 1 ? "" : "s"}</span>
        </div>
        <p>Aucune machine disponible.</p>
      </div>
    );
  }

  return (
    <div className="machine-table-container">
      <div className="table-heading">
        <h2>Machines industrielles</h2>
        <span>
          {machines.length === total
            ? `${total} machines`
            : `${machines.length} affichées sur ${total}`}
        </span>
      </div>

      <table className="machine-table">
        <thead>
          <tr>
            <th>Identifiant</th>
            <th>Nom</th>
            <th>Zone</th>
            <th>Nœud Fog</th>
            <th>État</th>
          </tr>
        </thead>

        <tbody>
          {machines.map((machine) => {
            const rawStatus = machine.status?.toLowerCase() ?? "unknown";
            const status = rawStatus === "operational" ? "normal" : rawStatus;

            return (
              <tr key={machine.machine_id}>
                <td>{machine.machine_id}</td>
                <td className="machine-name">
                  {machine.name ?? "Non renseigné"}
                </td>
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
