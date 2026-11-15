import Sidebar from "./components/Sidebar";
import Header from "./components/Header";
import StatCard from "./components/StatCard";
import AlertsPanel from "./components/AlertsPanel";

import MachineTable from "./components/MachineTable";
import MeasurementPanel from "./components/MeasurementPanel";


import PredictionPanel from "./components/PredictionPanel";
import FogNodePanel from "./components/FogNodePanel";
import TaskEventsPanel from "./components/TaskEventsPanel";

import { useState, useEffect } from "react";
import { getDashboardData } from "./services/dashboardService";

import "./App.css";

function App() {
  const [activePage, setActivePage] = useState("overview");
  const [selectedMachineId, setSelectedMachineId] = useState("");

  // État des données du dashboard
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  
  // Chargement des données du dashboard
  useEffect(() => {
    async function loadData() {
      try {
        const data = await getDashboardData();
        setDashboardData(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    loadData();
  }, []);

  // Sélection automatique de la première machine disponible
  useEffect(() => {
    const availableMachines = dashboardData?.machines ?? [];

    if (
      availableMachines.length > 0 &&
      !availableMachines.some(
        (machine) => machine.machine_id === selectedMachineId
      )
    ) {
      setSelectedMachineId(availableMachines[0].machine_id);
    }
  }, [dashboardData, selectedMachineId]);


  // Affichage pendant le chargement
  if (loading) {
    return <div className="dashboard-loading">Chargement du dashboard...</div>;
  }

  // Affichage en cas d'erreur
  if (error) {
    return <div className="dashboard-error">Erreur : {error}</div>;
  }

  // Récupération des données
  const machines = dashboardData.machines;
  const measurements = dashboardData.measurements;
  const predictions = dashboardData.predictions;
  const alerts = dashboardData.alerts;
  const fogNodes = dashboardData.fogNodes;
  const taskEvents = dashboardData.taskEvents;

  const selectedMeasurement = measurements.find(
    (measurement) => measurement.machine_id === selectedMachineId
  );

  const totalMachines = machines.length;

  const operationalMachines = machines.filter(
    (machine) => machine.status === "operational"
  ).length;

  const warningMachines = machines.filter(
    (machine) => machine.status === "warning"
  ).length;

  const criticalMachines = machines.filter(
    (machine) => machine.status === "critical"
  ).length;

  const idleMachines = machines.filter(
    (machine) => machine.status === "idle"
  ).length;

  const unknownMachines = machines.filter(
    (machine) => machine.status === "unknown"
  ).length;
  
  const zones = [...new Set(
  machines
    .map((machine) => machine.zone)
    .filter((zone) => zone != null)
)].sort().map((zone) => {
  const zoneMachines = machines.filter(
    (machine) => machine.zone === zone
  );

  return {
    name: zone,
    operational: zoneMachines.filter(
      (machine) => machine.status === "operational"
    ).length,
    warning: zoneMachines.filter(
      (machine) => machine.status === "warning"
    ).length,
    critical: zoneMachines.filter(
      (machine) => machine.status === "critical"
    ).length,
    other: zoneMachines.filter(
      (machine) =>
        machine.status === "idle" ||
        machine.status === "unknown" ||
        !machine.status
      ).length,
  };
});

  const recentAlerts = [...alerts]
    .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp))
    .slice(0, 2);
  return (
    <div className="dashboard">
      <Sidebar
        activePage={activePage}
        setActivePage={setActivePage}
      />

      <main className="main-content">
        <Header activePage={activePage} />

        {activePage === "overview" && (
          <div className="dashboard-content">

            {/* Indicateurs clés */}
            <section className="stats-grid">
              <StatCard
                title="Nombre total de machines"
                value={totalMachines}
                subtitle={`Réparties sur ${zones.length} zones`}
                icon="⚙"
                color="blue"
              />

              <StatCard
                title="Opérationnelles"
                value={operationalMachines}
                subtitle={`${idleMachines} au repos, ${unknownMachines} inconnues`}
                icon="✓"
                color="green"
              />

              <StatCard
                title="En alerte"
                value={warningMachines}
                subtitle="Nécessitent une attention"
                icon="!"
                color="orange"
              />

              <StatCard
                title="Critiques"
                value={criticalMachines}
                subtitle="Intervention immédiate requise"
                icon="⚠"
                color="red"
              />
            </section>

            {/* État des zones */}
            <section className="overview-section">
              <div className="overview-section-heading">
                <h2>État des zones industrielles</h2>
                <span>{zones.length} zones</span>
              </div>

              <div className="zones-grid">
                {zones.map((zone) => (
                  <div className="zone-card" key={zone.name}>
                    <h3>Zone {zone.name}</h3>

                    <div className="zone-status-bar">
                      {zone.operational > 0 && (
                        <div
                          className="zone-bar-operational"
                          style={{
                            flex: zone.operational,
                          }}
                        />
                      )}

                      {zone.warning > 0 && (
                        <div
                          className="zone-bar-warning"
                          style={{
                            flex: zone.warning,
                          }}
                        />
                      )}

                      {zone.critical > 0 && (
                        <div
                          className="zone-bar-critical"
                          style={{
                            flex: zone.critical,
                          }}
                        />
                      )}
                    </div>

                    <div className="zone-details">
                      <span>{zone.operational} opérationnelles</span>
                      <span>{zone.warning} en alerte</span>
                      <span>{zone.critical} critiques</span>
                      <span>{zone.other} au repos ou inconnues</span>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            {/* Alertes récentes */}
            <section className="overview-section">
              <div className="overview-section-heading">
                <h2>Alertes récentes</h2>
                <span>{recentAlerts.length} alertes affichées</span>
              </div>

              <AlertsPanel alerts={recentAlerts} compact />
            </section>

          </div>
        )}

        {activePage === "machines" && (
          <div className="dashboard-content">

            <section className="machines-section">
              <MachineTable machines={machines} />
            </section>

            <section className="measurement-section">
              <div className="section-heading">
                <h2>Mesures des capteurs</h2>
                <select
                  value={selectedMachineId}
                  onChange={(e) => setSelectedMachineId(e.target.value)}
                  disabled={machines.length === 0}
                >
                {machines.map((machine) => (
                <option
                  key={machine.machine_id}
                  value={machine.machine_id}
                >
                  {machine.machine_id} - {machine.name}
                </option>
                ))}
                </select>
              </div>

              <MeasurementPanel measurement={selectedMeasurement} />
            </section>

          </div>
        )}
        {activePage === "predictions" && (
          <div className="dashboard-content">
            <section className="predictions-section">
              <div className="section-heading">
                <h2>Analyse des risques de défaillance</h2>
                <span>{predictions.length} prédictions disponibles</span>
              </div>

              <div className="predictions-grid">
                {predictions.map((prediction) => (
                  <div className="prediction-card" key={prediction.machine_id}>
                    <div className="prediction-machine">
                      <span>Machine</span>
                        <strong>{prediction.machine_id}</strong>
                    </div>

                    <PredictionPanel prediction={prediction} />
                  </div>
                ))}
              </div>
            </section>
          </div>
        )}
        {activePage === "alerts" && (
          <div className="dashboard-content">

            <section className="alerts-page-section">

              <div className="section-heading">
                <h2>Alertes industrielles</h2>
                <span>{alerts.length} alertes détectées</span>
              </div>

              <AlertsPanel alerts={alerts} />

            </section>

          </div>
        )}
        {activePage === "fog" && (
          <div className="dashboard-content">
            <section className="fog-section">
              <div className="section-heading">
                <h2>État des nœuds Fog</h2>
                <span>{fogNodes.length} nœuds disponibles</span>
              </div>

              <FogNodePanel nodes={fogNodes} />
            </section>
          </div>
        )}
        {activePage === "events" && (
          <div className="dashboard-content">
            <section className="events-section">
              <div className="section-heading">
                <h2>Historique des événements</h2>
                <span>{taskEvents.length} événements enregistrés</span>
              </div>

              <TaskEventsPanel events={taskEvents} />
            </section>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
