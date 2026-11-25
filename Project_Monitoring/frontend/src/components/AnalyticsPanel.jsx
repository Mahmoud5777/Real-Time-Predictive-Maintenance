import { useCallback, useEffect, useState } from "react";
import { api } from "../services/api";

const DEFAULT_FROM = "2026-11-01T01:00";
const DEFAULT_TO = "2026-11-01T02:00";
const MAX_TRUSTED_LATENCY_SECONDS = 86400;

const METRIC_LABELS = {
  measurement_count: "Mesures enregistrées",
  prediction_count: "Prédictions générées",
  mean_temperature: "Température moyenne",
  mean_vibration: "Vibration moyenne",
  mean_current: "Courant moyen",
  mean_power: "Puissance moyenne",
  mean_speed: "Vitesse moyenne",
  mean_frequency: "Fréquence moyenne",
  mean_risk_score: "Risque moyen",
  anomaly_count: "Anomalies détectées",
  anomaly_ratio: "Taux d'anomalies",
  critical_prediction_count: "Prédictions critiques",
  mean_ingest_latency_s: "Latence moyenne d'ingestion",
  clock_skew_count: "Décalages d'horloge",
};

const DISPLAY_ORDER = [
  "measurement_count", "prediction_count", "mean_temperature",
  "mean_vibration", "mean_current", "mean_power", "mean_speed",
  "mean_frequency", "mean_risk_score", "anomaly_count", "anomaly_ratio",
  "critical_prediction_count", "mean_ingest_latency_s", "clock_skew_count",
];

function toUtc(value) {
  if (!value) return "";
  return new Date(value).toISOString();
}

function formatValue(value, unit) {
  if (value == null || !Number.isFinite(Number(value))) return "—";
  const number = Number(value);
  if (["observations", "predictions", "alerts"].includes(unit)) {
    return new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 0 }).format(number);
  }
  if (unit === "ratio") return `${(number * 100).toFixed(2)} %`;
  const suffix = {
    degC: " °C", "mm/s": " mm/s", A: " A", kW: " kW",
    rpm: " rpm", Hz: " Hz", s: " s", bar: " bar",
  }[unit] ?? (unit ? ` ${unit}` : "");
  return `${new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 2 }).format(number)}${suffix}`;
}

function MetricCard({ item }) {
  return (
    <article className="analytics-metric-card">
      <span className="analytics-metric-label">{METRIC_LABELS[item.metric] ?? item.metric.replaceAll("_", " ")}</span>
      <strong>{formatValue(item.value, item.unit)}</strong>
      <small>
        {Number(item.sample_size ?? 0).toLocaleString("fr-FR")} échantillons
        {item.quality === "LOW_SAMPLE" ? " · échantillon faible" : ""}
        {item.stale ? " · données anciennes" : ""}
      </small>
    </article>
  );
}

function DataState({ children, type = "info" }) {
  return <div className={`analytics-state ${type}`} role="status">{children}</div>;
}

function AnalyticsPanel() {
  const [from, setFrom] = useState(DEFAULT_FROM);
  const [to, setTo] = useState(DEFAULT_TO);
  const [data, setData] = useState(null);
  const [risk, setRisk] = useState(null);
  const [comparison, setComparison] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadAnalytics = useCallback(async (start, end) => {
    setLoading(true);
    setError("");
    const params = `from=${encodeURIComponent(toUtc(start))}&to=${encodeURIComponent(toUtc(end))}&limit=100`;
    const [kpiResult, riskResult, modelResult] = await Promise.allSettled([
      api.get(`/api/v1/analytics/kpis?scope=plant&${params}`),
      api.get(`/api/v1/analytics/risk-ranking?${params}`),
      api.get(`/api/v1/analytics/model-comparison?${params}`),
    ]);
    if (kpiResult.status === "fulfilled") setData(kpiResult.value);
    else setData({ items: [], unavailable_metrics: {}, empty_reason: kpiResult.reason?.message });
    if (riskResult.status === "fulfilled") setRisk(riskResult.value);
    else setRisk({ items: [], error: riskResult.reason?.message });
    if (modelResult.status === "fulfilled") setComparison(modelResult.value);
    else setComparison({ items: [], error: modelResult.reason?.message });
    if ([kpiResult, riskResult, modelResult].every((result) => result.status === "rejected")) {
      setError("Les trois services Analytics sont inaccessibles. Vérifiez le backend MP3.");
    }
    setLoading(false);
  }, []);

  useEffect(() => { loadAnalytics(DEFAULT_FROM, DEFAULT_TO); }, [loadAnalytics]);

  const applyPeriod = (event) => {
    event.preventDefault();
    if (!from || !to || new Date(from) >= new Date(to)) {
      setError("La date de début doit précéder la date de fin.");
      return;
    }
    if (new Date(to) - new Date(from) !== 3600000) {
      setError("Les KPI MP3 sont horaires : choisissez exactement une heure.");
      return;
    }
    loadAnalytics(from, to);
  };

  const metrics = data?.items ?? [];
  const metricByName = new Map(metrics.map((item) => [item.metric, item]));
  const latencyMetric = metricByName.get("mean_ingest_latency_s");
  const latencyInvalid = latencyMetric && (
    !Number.isFinite(Number(latencyMetric.value)) ||
    Number(latencyMetric.value) < 0 ||
    Number(latencyMetric.value) > MAX_TRUSTED_LATENCY_SECONDS
  );
  const orderedMetrics = DISPLAY_ORDER
    .map((name) => metricByName.get(name))
    .filter((item) => item && !(item.metric === "mean_ingest_latency_s" && latencyInvalid));
  const unavailable = Object.entries(data?.unavailable_metrics ?? {});
  const riskItems = risk?.items ?? [];
  const modelItems = comparison?.items ?? [];
  const periodLabel = data?.from_ && data?.to
    ? `${new Date(data.from_).toLocaleString("fr-FR")} – ${new Date(data.to).toLocaleString("fr-FR")}`
    : "Période sélectionnée";

  return (
    <section className="overview-section analytics-section">
      <div className="overview-section-heading analytics-heading">
        <div>
          <h2>Analytics Cloud — MP3</h2>
          <p className="analytics-period">{periodLabel}</p>
        </div>
        <span>{data?.meta?.total ?? 0} indicateurs</span>
      </div>
      <form className="analytics-period-form" onSubmit={applyPeriod}>
        <label>Début<input type="datetime-local" value={from} onChange={(event) => setFrom(event.target.value)} /></label>
        <label>Fin<input type="datetime-local" value={to} onChange={(event) => setTo(event.target.value)} /></label>
        <button type="submit" disabled={loading}>{loading ? "Chargement…" : "Actualiser les Analytics"}</button>
      </form>
      {error && <DataState type="error">{error}</DataState>}
      {loading && <DataState>Chargement des indicateurs Cloud…</DataState>}
      {!loading && orderedMetrics.length > 0 && (
        <div className="analytics-metrics-grid">
          {orderedMetrics.map((item) => <MetricCard key={`${item.metric}-${item.scope_value}-${item.bucket_start}`} item={item} />)}
        </div>
      )}
      {!loading && orderedMetrics.length === 0 && (
        <DataState type="warning">
          {data?.empty_reason ?? data?.error ?? "Aucun KPI disponible pour cette période. Vérifiez la période et le cache analytique MP3."}
        </DataState>
      )}
      {latencyInvalid && (
        <DataState type="warning">
          Latence d'ingestion non affichée : la valeur historique dépasse 24 h et ne représente pas une mesure fiable
          du délai réel de traitement. Les timestamps simulés et la date d'ingestion doivent être distingués.
        </DataState>
      )}
      <div className="analytics-two-columns">
        <div className="analytics-subpanel">
          <div className="analytics-subheading"><h3>Machines — classement du risque</h3><span>{risk?.meta?.total ?? 0} machines</span></div>
          {risk?.error ? <DataState type="warning">{risk.error}</DataState> :
            riskItems.length ? (
              <ol className="analytics-risk-list">
                {riskItems.slice(0, 8).map((item, index) => (
                  <li key={`${item.scope_value}-${item.bucket_start}`}>
                    <span className="analytics-rank">{index + 1}</span>
                    <span className="analytics-risk-machine">{item.scope_value}</span>
                    <strong>{formatValue(item.value, item.unit)}</strong>
                    <small>{item.sample_size} prédictions</small>
                  </li>
                ))}
              </ol>
            ) : <DataState>Aucun classement de risque pour cette heure.</DataState>}
        </div>
        <div className="analytics-subpanel">
          <div className="analytics-subheading"><h3>Distribution par version du modèle</h3><span>{comparison?.meta?.total ?? 0} indicateurs</span></div>
          <p className="analytics-disclaimer">Ces données décrivent les distributions des prédictions ; elles ne mesurent pas la précision du modèle.</p>
          {comparison?.error ? <DataState type="warning">{comparison.error}</DataState> :
            modelItems.length ? (
              <div className="analytics-model-list">
                {modelItems.map((item) => (
                  <div key={`${item.scope_value}-${item.metric}-${item.bucket_start}`}>
                    <span>{item.scope_value}</span>
                    <strong>{METRIC_LABELS[item.metric] ?? item.metric}</strong>
                    <small>{formatValue(item.value, item.unit)} · {item.sample_size} échantillons</small>
                  </div>
                ))}
              </div>
            ) : <DataState>Aucune donnée de comparaison de modèle pour cette heure.</DataState>}
        </div>
      </div>
      {unavailable.length > 0 && (
        <details className="analytics-unavailable">
          <summary>{unavailable.length} métriques non calculables avec les données actuelles</summary>
          <ul>{unavailable.map(([name, reason]) => <li key={name}><strong>{name.replaceAll("_", " ")}</strong> : {reason}</li>)}</ul>
        </details>
      )}
      <p className="analytics-footnote">Source : API Analytics MP3 / cache horaire PostgreSQL. Les valeurs absentes ne sont pas remplacées par zéro.</p>
    </section>
  );
}

export default AnalyticsPanel;
