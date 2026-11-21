import { useEffect, useState } from "react";
import Sidebar from "./components/Sidebar";
import Header from "./components/Header";
import StatCard from "./components/StatCard";
import AlertsPanel from "./components/AlertsPanel";
import MachineTable from "./components/MachineTable";
import MeasurementPanel from "./components/MeasurementPanel";
import PredictionPanel from "./components/PredictionPanel";
import FogNodePanel from "./components/FogNodePanel";
import TaskEventsPanel from "./components/TaskEventsPanel";
import {
  DEFAULT_PAGE_SIZE,
  getAlertPage,
  getDashboardData,
  getMigrationPage,
  getMeasurementPage,
  getPredictionPage,
  getSupervisionPage,
  getTaskEventPage,
} from "./services/dashboardService";
import "./App.css";

const EMPTY_PAGE = {
  items: [],
  total: 0,
  limit: DEFAULT_PAGE_SIZE,
  offset: 0,
};
const EMPTY_MACHINES = [];

function getMachineHealthStatus(machine) {
  const status = machine.status?.toLowerCase();
  return status === "operational" ? "normal" : status ?? "unknown";
}

function correctOffset(page, offset, setOffset) {
  if (offset > 0 && offset >= page.total) {
    const lastOffset = Math.max(
      0,
      Math.floor((page.total - 1) / DEFAULT_PAGE_SIZE) * DEFAULT_PAGE_SIZE
    );
    setOffset(lastOffset);
  }
}

function App() {
  const [activePage, setActivePage] = useState("overview");
  const [selectedMachineIdState, setSelectedMachineIdState] = useState("");
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [refreshVersion, setRefreshVersion] = useState(0);

  const [latestMeasurement, setLatestMeasurement] = useState(null);
  const [measurementPage, setMeasurementPage] = useState(EMPTY_PAGE);
  const [measurementOffset, setMeasurementOffset] = useState(0);
  const [measurementLoading, setMeasurementLoading] = useState(true);
  const [measurementError, setMeasurementError] = useState(null);

  const [predictionPage, setPredictionPage] = useState(EMPTY_PAGE);
  const [predictionOffset, setPredictionOffset] = useState(0);
  const [predictionFilters, setPredictionFilters] = useState({
    machineId: "",
    severity: "",
    anomaly: "",
  });
  const [predictionLoading, setPredictionLoading] = useState(true);
  const [predictionError, setPredictionError] = useState(null);

  const [alertPage, setAlertPage] = useState(EMPTY_PAGE);
  const [alertOffset, setAlertOffset] = useState(0);
  const [alertFilters, setAlertFilters] = useState({
    machineId: "",
    status: "",
    severity: "",
  });
  const [alertLoading, setAlertLoading] = useState(true);
  const [alertError, setAlertError] = useState(null);

  const [taskEventPage, setTaskEventPage] = useState(EMPTY_PAGE);
  const [taskEventOffset, setTaskEventOffset] = useState(0);
  const [taskEventLoading, setTaskEventLoading] = useState(true);
  const [taskEventError, setTaskEventError] = useState(null);
  const [migrationPage, setMigrationPage] = useState(EMPTY_PAGE);
  const [migrationOffset, setMigrationOffset] = useState(0);
  const [migrationLoading, setMigrationLoading] = useState(true);
  const [migrationError, setMigrationError] = useState(null);
  const [supervisionPage, setSupervisionPage] = useState(EMPTY_PAGE);
  const [supervisionOffset, setSupervisionOffset] = useState(0);
  const [supervisionLoading, setSupervisionLoading] = useState(true);
  const [supervisionError, setSupervisionError] = useState(null);

  useEffect(() => {
    let active = true;
    let requestInFlight = false;

    async function refreshData() {
      if (requestInFlight) return;
      requestInFlight = true;

      try {
        const data = await getDashboardData();
        if (!active) return;
        const availableMachines = data?.machines ?? [];
        if (availableMachines.length > 0) {
          setSelectedMachineIdState((currentMachineId) =>
            availableMachines.some(
              (machine) => machine.machine_id === currentMachineId
            )
              ? currentMachineId
              : availableMachines[0].machine_id
          );
        }
        setDashboardData(data);
        setLastUpdated(new Date());
        setRefreshVersion((version) => version + 1);
        setError(null);
      } catch (err) {
        if (active) setError(err.message);
      } finally {
        requestInFlight = false;
        if (active) setLoading(false);
      }
    }

    refreshData();
    const refreshTimer = window.setInterval(refreshData, 15_000);

    return () => {
      active = false;
      window.clearInterval(refreshTimer);
    };
  }, []);

  const machines = dashboardData?.machines ?? EMPTY_MACHINES;
  const selectedMachineId = selectedMachineIdState;

  useEffect(() => {
    if (!selectedMachineId) return undefined;
    let active = true;

    getMeasurementPage({
      machineId: selectedMachineId,
      limit: DEFAULT_PAGE_SIZE,
      offset: measurementOffset,
    })
      .then((page) => {
        if (!active) return;
        setMeasurementPage(page);
        setMeasurementError(null);
        if (measurementOffset === 0) {
          setLatestMeasurement(page.items[0] ?? null);
        }
        correctOffset(page, measurementOffset, setMeasurementOffset);
      })
      .catch((err) => {
        if (active) setMeasurementError(err.message);
      })
      .finally(() => {
        if (active) setMeasurementLoading(false);
      });

    return () => {
      active = false;
    };
  }, [selectedMachineId, measurementOffset, refreshVersion]);

  useEffect(() => {
    if (activePage !== "predictions") return undefined;
    let active = true;

    getPredictionPage({
      filters: predictionFilters,
      limit: DEFAULT_PAGE_SIZE,
      offset: predictionOffset,
    })
      .then((page) => {
        if (!active) return;
        setPredictionPage(page);
        setPredictionError(null);
        correctOffset(page, predictionOffset, setPredictionOffset);
      })
      .catch((err) => {
        if (active) setPredictionError(err.message);
      })
      .finally(() => {
        if (active) setPredictionLoading(false);
      });

    return () => {
      active = false;
    };
  }, [activePage, predictionFilters, predictionOffset, refreshVersion]);

  useEffect(() => {
    if (activePage !== "alerts") return undefined;
    let active = true;

    getAlertPage({
      filters: alertFilters,
      limit: DEFAULT_PAGE_SIZE,
      offset: alertOffset,
      machines,
    })
      .then((page) => {
        if (!active) return;
        setAlertPage(page);
        setAlertError(null);
        correctOffset(page, alertOffset, setAlertOffset);
      })
      .catch((err) => {
        if (active) setAlertError(err.message);
      })
      .finally(() => {
        if (active) setAlertLoading(false);
      });

    return () => {
      active = false;
    };
  }, [activePage, alertFilters, alertOffset, machines, refreshVersion]);

  useEffect(() => {
    if (activePage !== "events") return undefined;
    let active = true;

    getTaskEventPage({
      limit: DEFAULT_PAGE_SIZE,
      offset: taskEventOffset,
    })
      .then((page) => {
        if (!active) return;
        setTaskEventPage(page);
        setTaskEventError(null);
        correctOffset(page, taskEventOffset, setTaskEventOffset);
      })
      .catch((err) => {
        if (active) setTaskEventError(err.message);
      })
      .finally(() => {
        if (active) setTaskEventLoading(false);
      });

    return () => {
      active = false;
    };
  }, [activePage, taskEventOffset, refreshVersion]);

  useEffect(() => {
    if (activePage !== "events") return undefined;
    let active = true;

    getMigrationPage({
      limit: DEFAULT_PAGE_SIZE,
      offset: migrationOffset,
    })
      .then((page) => {
        if (!active) return;
        setMigrationPage(page);
        setMigrationError(null);
        correctOffset(page, migrationOffset, setMigrationOffset);
      })
      .catch((err) => {
        if (active) setMigrationError(err.message);
      })
      .finally(() => {
        if (active) setMigrationLoading(false);
      });

    return () => {
      active = false;
    };
  }, [activePage, migrationOffset, refreshVersion]);

  useEffect(() => {
    if (activePage !== "events") return undefined;
    let active = true;

    getSupervisionPage({
      limit: DEFAULT_PAGE_SIZE,
      offset: supervisionOffset,
    })
      .then((page) => {
        if (!active) return;
        setSupervisionPage(page);
        setSupervisionError(null);
        correctOffset(page, supervisionOffset, setSupervisionOffset);
      })
      .catch((err) => {
        if (active) setSupervisionError(err.message);
      })
      .finally(() => {
        if (active) setSupervisionLoading(false);
      });

    return () => {
      active = false;
    };
  }, [activePage, supervisionOffset, refreshVersion]);

  if (loading) {
    return (
      <div className="dashboard-loading" role="status" aria-live="polite">
        Chargement du dashboard...
      </div>
    );
  }

  if (error && !dashboardData) {
    return (
      <div className="dashboard-error" role="alert">
        Erreur : {error}
      </div>
    );
  }

  const recentAlerts = dashboardData.recentAlerts;
  const alertCounts = dashboardData.alertCounts;
  const fogNodes = dashboardData.fogNodes;
  const machineTotal = dashboardData.machineTotal;
  const fogNodeTotal = dashboardData.fogNodeTotal;

  const normalMachines = machines.filter(
    (machine) => getMachineHealthStatus(machine) === "normal"
  ).length;
  const warningMachines = machines.filter(
    (machine) => getMachineHealthStatus(machine) === "warning"
  ).length;
  const criticalMachines = machines.filter(
    (machine) => getMachineHealthStatus(machine) === "critical"
  ).length;
  const idleMachines = machines.filter(
    (machine) => getMachineHealthStatus(machine) === "idle"
  ).length;
  const offlineMachines = machines.filter(
    (machine) => getMachineHealthStatus(machine) === "offline"
  ).length;
  const unknownMachines = machines.filter(
    (machine) => getMachineHealthStatus(machine) === "unknown"
  ).length;

  const zones = [...new Set(
    machines
      .map((machine) => machine.zone)
      .filter((zone) => zone != null)
  )].sort().map((zone) => {
    const zoneMachines = machines.filter((machine) => machine.zone === zone);
    return {
      name: zone,
      normal: zoneMachines.filter(
        (machine) => getMachineHealthStatus(machine) === "normal"
      ).length,
      warning: zoneMachines.filter(
        (machine) => getMachineHealthStatus(machine) === "warning"
      ).length,
      critical: zoneMachines.filter(
        (machine) => getMachineHealthStatus(machine) === "critical"
      ).length,
      other: zoneMachines.filter((machine) =>
        ["idle", "offline", "unknown"].includes(getMachineHealthStatus(machine))
      ).length,
    };
  });

  const updatePredictionFilter = (name, value) => {
    setPredictionLoading(true);
    setPredictionError(null);
    setPredictionFilters((current) => ({ ...current, [name]: value }));
    setPredictionOffset(0);
  };
  const updateAlertFilter = (name, value) => {
    setAlertLoading(true);
    setAlertError(null);
    setAlertFilters((current) => ({ ...current, [name]: value }));
    setAlertOffset(0);
  };
  const setActivePageWithLoading = (page) => {
    if (page === activePage) return;
    setActivePage(page);
    if (page === "predictions") {
      setPredictionLoading(true);
      setPredictionError(null);
    } else if (page === "alerts") {
      setAlertLoading(true);
      setAlertError(null);
    } else if (page === "events") {
      setTaskEventLoading(true);
      setTaskEventError(null);
      setMigrationLoading(true);
      setMigrationError(null);
      setSupervisionLoading(true);
      setSupervisionError(null);
    } else if (page === "machines") {
      setMeasurementLoading(true);
      setMeasurementError(null);
    }
  };
  const changeMeasurementPage = (offset) => {
    setMeasurementLoading(true);
    setMeasurementOffset(offset);
  };
  const changePredictionPage = (offset) => {
    setPredictionLoading(true);
    setPredictionOffset(offset);
  };
  const changeAlertPage = (offset) => {
    setAlertLoading(true);
    setAlertOffset(offset);
  };
  const changeTaskEventPage = (offset) => {
    setTaskEventLoading(true);
    setTaskEventOffset(offset);
  };
  const changeMigrationPage = (offset) => {
    setMigrationLoading(true);
    setMigrationOffset(offset);
  };
  const changeSupervisionPage = (offset) => {
    setSupervisionLoading(true);
    setSupervisionOffset(offset);
  };

  return (
    <div className="dashboard">
      <Sidebar
        activePage={activePage}
        setActivePage={setActivePageWithLoading}
        connectionError={error}
      />

      <main className="main-content">
        <Header
          activePage={activePage}
          connectionError={error}
          lastUpdated={lastUpdated}
        />
        {error && (
          <div className="dashboard-refresh-error" role="alert">
            Échec de l’actualisation : {error}. Les dernières données reçues sont
            conservées ; une nouvelle tentative aura lieu automatiquement.
          </div>
        )}

        {activePage === "overview" && (
          <div className="dashboard-content">
            <section className="stats-grid">
              <StatCard
                title="Nombre total de machines"
                value={machineTotal}
                subtitle={`Réparties sur ${zones.length} zones`}
                icon="⚙"
                color="blue"
              />
              <StatCard
                title="Normal"
                value={normalMachines}
                subtitle={`${idleMachines} au repos, ${offlineMachines} hors service, ${unknownMachines} inconnues`}
                icon="✓"
                color="green"
              />
              <StatCard
                title="Warning"
                value={warningMachines}
                subtitle="Nécessitent une attention"
                icon="!"
                color="orange"
              />
              <StatCard
                title="Critical"
                value={criticalMachines}
                subtitle="Intervention immédiate requise"
                icon="⚠"
                color="red"
              />
            </section>

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
                      {zone.normal > 0 && (
                        <div className="zone-bar-normal" style={{ flex: zone.normal }} />
                      )}
                      {zone.warning > 0 && (
                        <div className="zone-bar-warning" style={{ flex: zone.warning }} />
                      )}
                      {zone.critical > 0 && (
                        <div className="zone-bar-critical" style={{ flex: zone.critical }} />
                      )}
                    </div>
                    <div className="zone-details">
                      <span>{zone.normal} Normal</span>
                      <span>{zone.warning} Warning</span>
                      <span>{zone.critical} Critical</span>
                      <span>{zone.other} hors service, au repos ou inconnues</span>
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <section className="overview-section">
              <div className="overview-section-heading">
                <h2>Alertes récentes</h2>
                <div className="alert-counts">
                  <span className="alert-count active">
                    {alertCounts.active} actives
                  </span>
                  <span className="alert-count resolved">
                    {alertCounts.resolved} résolues
                  </span>
                </div>
              </div>
              <AlertsPanel alerts={recentAlerts} compact />
            </section>
          </div>
        )}

        {activePage === "machines" && (
          <div className="dashboard-content">
            <section className="machines-section">
              <MachineTable machines={machines} total={machineTotal} />
            </section>
            <section className="measurement-section">
              <div className="section-heading">
                <h2>Mesures des capteurs</h2>
                <select
                  aria-label="Machine sélectionnée"
                  value={selectedMachineId}
                  onChange={(event) => {
                    setSelectedMachineIdState(event.target.value);
                    setMeasurementOffset(0);
                    setMeasurementPage(EMPTY_PAGE);
                    setLatestMeasurement(null);
                    setMeasurementLoading(true);
                    setMeasurementError(null);
                  }}
                  disabled={machines.length === 0}
                >
                  {machines.map((machine) => (
                    <option key={machine.machine_id} value={machine.machine_id}>
                      {machine.machine_id} - {machine.name}
                    </option>
                  ))}
                </select>
              </div>
              <MeasurementPanel
                measurement={latestMeasurement}
                measurements={measurementPage.items}
                total={measurementPage.total}
                offset={measurementOffset}
                pageSize={DEFAULT_PAGE_SIZE}
                onPageChange={changeMeasurementPage}
                loading={measurementLoading}
                error={measurementError}
              />
            </section>
          </div>
        )}

        {activePage === "predictions" && (
          <div className="dashboard-content">
            <section className="predictions-section">
              <div className="section-heading">
                <h2>Analyse des risques de défaillance</h2>
              </div>
              <PredictionPanel
                predictions={predictionPage.items}
                total={predictionPage.total}
                offset={predictionOffset}
                pageSize={DEFAULT_PAGE_SIZE}
                onPageChange={changePredictionPage}
                filters={predictionFilters}
                onFilterChange={updatePredictionFilter}
                machines={machines}
                loading={predictionLoading}
                error={predictionError}
              />
            </section>
          </div>
        )}

        {activePage === "alerts" && (
          <div className="dashboard-content">
            <section className="alerts-page-section">
              <div className="section-heading">
                <h2>Alertes industrielles</h2>
                <div className="alert-counts">
                  <span className="alert-count active">
                    {alertCounts.active} actives
                  </span>
                  <span className="alert-count resolved">
                    {alertCounts.resolved} résolues
                  </span>
                </div>
              </div>
              <AlertsPanel
                alerts={alertPage.items}
                total={alertPage.total}
                offset={alertOffset}
                pageSize={DEFAULT_PAGE_SIZE}
                onPageChange={changeAlertPage}
                filters={alertFilters}
                onFilterChange={updateAlertFilter}
                machines={machines}
                loading={alertLoading}
                error={alertError}
              />
            </section>
          </div>
        )}

        {activePage === "fog" && (
          <div className="dashboard-content">
            <section className="fog-section">
              <div className="section-heading">
                <h2>État des nœuds Fog</h2>
                <span>{fogNodeTotal} nœuds disponibles</span>
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
              </div>
              <TaskEventsPanel
                events={taskEventPage.items}
                total={taskEventPage.total}
                offset={taskEventOffset}
                pageSize={DEFAULT_PAGE_SIZE}
                onPageChange={changeTaskEventPage}
                loading={taskEventLoading}
                error={taskEventError}
                migrationEvents={migrationPage.items}
                migrationTotal={migrationPage.total}
                migrationOffset={migrationOffset}
                onMigrationPageChange={changeMigrationPage}
                migrationLoading={migrationLoading}
                migrationError={migrationError}
                supervisionEvents={supervisionPage.items}
                supervisionTotal={supervisionPage.total}
                supervisionOffset={supervisionOffset}
                onSupervisionPageChange={changeSupervisionPage}
                supervisionLoading={supervisionLoading}
                supervisionError={supervisionError}
              />
            </section>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
