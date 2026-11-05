# KPI usine - formules officielles

Aucun chiffre n est affiche au dashboard s il n a pas une formule ici. Unites respectees,
fenetre par defaut = derniere heure, agrégats horaires materialises.

| Metric (`kpi_records.metric`) | Formule | Source | Interpretation |
|---|---|---|---|
| `false_alarm_rate` | alertes `severity=WARNING` resolues sans prediction `anomaly=true` sur la meme machine dans +/-10 min / total alertes | `alerts` + `predictions` | Confiance accordee aux alarmes |
| `mean_detection_latency_s` | avg(`alert.timestamp` - `sensor_data.timestamp` le plus proche pour la machine) | `alerts` + `sensor_data` | Prouve l interet du Fog vs Cloud |
| `critical_alert_count` | count(alerts `severity=CRITICAL`) | `alerts` | Charge maintenance |
| `availability_percent` | 100 * (1 - secondes `status=OFFLINE` / secondes de la fenetre), avec couverture connue de toute la fenetre | `fog_status_history` + transitions de supervision | Disponibilite observee ; incomplete si des periodes sont inconnues |
| `mtbf_hours` | avg(ecart entre deux `PREDICTED_FAILURE` consecutifs d une machine) | `alerts` | Fiabilite machine |
| `mttr_hours` | avg(`resolved_at` - `timestamp`) des alertes CRITICAL | `alerts` | Reactivite maintenance |
| `risk_top_machines` | top 5 machines par avg(`risk_score`) sur la fenetre | `predictions` | Priorisation intervention |
| `tasks_migrated_total` | count(task_events `status=MIGRATED`) | `task_events` | Activite de l equilibreur |
| `task_recovery_time_s` | avg(date de reprise effective - date de detection de panne), par episode | `task_events.occurred_at` + dates de panne a fournir par MP2 | Delai de reprise ; non calculable tant que ces dates manquent |
| `model_precision` | TP / (TP + FP) par `model_version` | `predictions` | Comparation modeles MP1 |
| `ingest_duplicate_ratio` | doublons rejetes / messages recus | metriques ingestion | Sante du lien Fog->Cloud |

Regles communes :
- Fenetre alignee sur l heure UTC (`bucket_start`, `bucket_end`), jamais glissante, pour que
  deux KPI soient comparables.
- `sample_size` obligatoire : un KPI calcule sur 2 echantillons est marque `LOW_SAMPLE` cote dashboard.
- Recalcul idempotent : relancer le job sur la meme fenetre ecrase la valeur, n cree pas de doublon.

Precision apportee a l'etape 2 : `completed_at - created_at` mesure la duree globale
d'une tache, pas son temps de reprise. Un statut RECOVERED ne donne pas a lui seul la
date de detection de panne ou celle du redemarrage effectif. Le contrat actuel ne fournit
pas occurred_at ; aucun delai d'evenement ne doit donc etre invente a partir de received_at.
Les extensions de chronologie et de tentative sont listees dans DATABASE_SCHEMA.md.

Les etats courants de fog_nodes ne suffisent pas a reconstruire la disponibilite d'une
fenetre. La supervision devra conserver ses transitions et signaler les periodes sans
observation. Un intervalle sans donnee ne vaut pas automatiquement un intervalle ONLINE.
Le nombre de migrations indique l'activite du partage ; son gain exige une comparaison
de charges equivalentes avec et sans partage, en tenant compte des couts de transfert.
