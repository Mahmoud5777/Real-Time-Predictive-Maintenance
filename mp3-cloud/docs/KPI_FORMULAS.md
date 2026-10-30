# KPI usine - formules officielles

Aucun chiffre n est affiche au dashboard s il n a pas une formule ici. Unites respectees,
fenetre par defaut = derniere heure, agrégats horaires materialises.

| Metric (`kpi_records.metric`) | Formule | Source | Interpretation |
|---|---|---|---|
| `false_alarm_rate` | alertes `severity=WARNING` resolues sans prediction `anomaly=true` sur la meme machine dans +/-10 min / total alertes | `alerts` + `predictions` | Confiance accordee aux alarmes |
| `mean_detection_latency_s` | avg(`alert.timestamp` - `sensor_data.timestamp` le plus proche pour la machine) | `alerts` + `sensor_data` | Prouve l interet du Fog vs Cloud |
| `critical_alert_count` | count(alerts `severity=CRITICAL`) | `alerts` | Charge maintenance |
| `availability_percent` | 100 * (1 - secondes `status=OFFLINE` / secondes de la fenetre) par zone | `fog_nodes` + `task_events` | Robustesse percue |
| `mtbf_hours` | avg(ecart entre deux `PREDICTED_FAILURE` consecutifs d une machine) | `alerts` | Fiabilite machine |
| `mttr_hours` | avg(`resolved_at` - `timestamp`) des alertes CRITICAL | `alerts` | Reactivite maintenance |
| `risk_top_machines` | top 5 machines par avg(`risk_score`) sur la fenetre | `predictions` | Priorisation intervention |
| `tasks_migrated_total` | count(task_events `status=MIGRATED`) | `task_events` | Activite de l equilibreur |
| `task_recovery_time_s` | avg(`completed_at` - `created_at`) des taches `RECOVERED` | `task_events` | RTO observe |
| `model_precision` | TP / (TP + FP) par `model_version` | `predictions` | Comparation modeles MP1 |
| `ingest_duplicate_ratio` | doublons rejetes / messages recus | metriques ingestion | Sante du lien Fog->Cloud |

Regles communes :
- Fenetre alignee sur l heure UTC (`bucket_start`, `bucket_end`), jamais glissante, pour que
  deux KPI soient comparables.
- `sample_size` obligatoire : un KPI calcule sur 2 echantillons est marque `LOW_SAMPLE` cote dashboard.
- Recalcul idempotent : relancer le job sur la meme fenetre ecrase la valeur, n cree pas de doublon.
