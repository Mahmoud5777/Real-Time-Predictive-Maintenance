# KPI et agregats horaires - etape 6

Reference executable : `app/analytics/catalogue.py` et `app/analytics/aggregate.py`.
Les unites des capteurs viennent du [contrat producteur](../../docs/DATA_CONTRACT.md).
Ces calculs decrivent les observations recues. Ils ne prouvent pas une amelioration
du partage Fog, une precision ML ou une disponibilite de l'usine.

## Fenetres et donnees absentes

Chaque resultat couvre une heure UTC terminee, intervalle **[bucket_start, bucket_end)**.
Une observation a 11:00:00 appartient a 11h, jamais a 10h. Les lectures choisissent
par defaut la derniere heure terminee. `from` et `to` doivent etre dates ISO-8601 avec
fuseau, alignees sur l'heure UTC ; `to` est exclusif. La periode est bornee a 744 heures
(31 jours). Les heures restent distinctes ; aucune moyenne de moyennes n'est calculee.

Chaque ligne porte `value`, `sample_size`, `computed_at`, `unit`, `time_basis`, `quality`
et `stale`. `LOW_SAMPLE` signifie moins de 30 observations contributrices : c'est un
seuil de presentation propose, pas une garantie statistique. Sinon `quality=OBSERVED`.
Pour les compteurs et ratios, sample_size est le nombre de lignes du groupe source ;
pour les moyennes, seuls les echantillons effectivement utilises sont comptes.
`stale=true` indique un calcul datant de plus de trois periodes de refresh, y compris
pour les anciennes heures qui ne sont plus recalculees ; cela ne signifie pas qu'un
Fog est OFFLINE. Les horloges Cloud doivent etre synchronisees.

Un groupe sans observation n'a aucune ligne. Une moyenne sans valeur connue n'a aucune
ligne non plus. Un compteur a zero est conserve lorsque son groupe source existe
(par exemple, trois predictions connues dont aucune anomalie). L'absence de donnees
ne devient jamais une moyenne de zero. Les reponses vides exposent `empty_reason` ;
elles ne distinguent pas un refresh en attente d'une source silencieuse.

## Mesures

Source : `sensor_data`, heure determinee par `timestamp` producteur.

- `measurement_count` : nombre de mesures stockees, unite `observations`.
- `mean_temperature` : moyenne temperature, `degC`.
- `mean_vibration` : moyenne vibration, `mm/s` RMS.
- `mean_speed` : moyenne vitesse, `rpm`.
- `mean_current` : moyenne courant, `A`.
- `mean_pressure` : moyenne des pressions connues, `bar`.
- `mean_power` : moyenne des puissances connues, `kW`.
- `mean_frequency` : moyenne des frequences connues, `Hz`.
- `mean_ingest_latency_s` : moyenne de `received_at - timestamp`, en secondes,
  uniquement pour les delais positifs ou nuls. C'est le delai jusqu'a reception Cloud,
  avec transport et eventuel tamponnage ; ce n'est pas la latence de detection Fog.
- `clock_skew_count` : nombre de delais de reception negatifs, unite `observations`.
  Ils signalent des timestamps a verifier et sont exclus de la moyenne de latence.

## Predictions et risque

Source : `predictions`, heure determinee par `timestamp` producteur.

- `prediction_count` : nombre de predictions stockees, unite `predictions`.
- `anomaly_count` : nombre de predictions avec `anomaly=true`, unite `predictions`.
- `anomaly_ratio` : anomaly_count / prediction_count, ratio entre 0 et 1.
- `mean_risk_score` : moyenne des risques rapportes, ratio entre 0 et 1.
- `critical_prediction_count` : predictions CRITICAL, unite `predictions`.

Le classement de risque trie les machines par `mean_risk_score` decroissant sur une
seule heure, puis par machine_id pour departager. Les machines sans prediction sont
absentes. La pagination permet un top 5 via `limit=5`.
La comparaison de modeles expose ces cinq indicateurs par model_version et heure.
Elle compare leurs distributions de predictions, **sans mesurer leur exactitude**.

## Alertes et resolutions

- `alert_count` : nombre d'alertes levees dans l'heure de `alerts.timestamp`, unite `alerts`.
- `critical_alert_count` : nombre de ces alertes avec severity CRITICAL, unite `alerts`.
- `mttr_hours` : moyenne de `(resolved_at - timestamp) / 3600` pour les alertes CRITICAL
  RESOLVED avec date de resolution connue, dans **l'heure de resolved_at**. sample_size
  est le nombre de ces resolutions. Une alerte ouverte ne participe pas au calcul.

Ce MTTR mesure le delai de resolution d'alertes critiques ; il ne prouve pas un temps
de reparation mecanique. Le choix d'une cohorte de resolutions permet d'inclure une
alerte ancienne resolue maintenant, sans devoir recalculer indefiniment son heure
de creation. Le jalon de retention devra conserver les alertes necessaires a ce calcul.

## Rapports de taches

Source : `task_events`, heure determinee par **received_at Cloud**. Le contrat MP2
actuel ne donne pas toujours occurred_at ; aucune date d'execution n'est inventee.

- `task_event_count` : nombre de rapports recus, unite `reports`.
- `tasks_migrated_total` : rapports avec status MIGRATED, unite `reports`.
- `completed_task_reports` : nombre de task_id distincts rapportes COMPLETED dans
  l'heure, unite `tasks`. Deux rapports de completion d'une meme tache dans la meme
  heure comptent une fois ; cette tache peut etre rapportee dans plusieurs heures.

La deduplication d'ingestion par message_id elimine les retransmissions identiques.
Plusieurs rapports MIGRATED avec des identifiants differents restent plusieurs rapports.
Ces indicateurs n'affirment ni un nombre de tentatives reelles ni un gain de performance.

## Perimetres

- `plant/all` : ensemble des observations du groupe.
- `zone/A`, B ou C : zone de la machine pour mesures, predictions et alertes ; zone
  de l'origine connue de la tache pour ses rapports.
- `machine/M01` a M12 : machine associee, si connue pour une tache.
- `fog/FOG_A`, B ou C : Fog du catalogue machine pour les mesures, Fog rapporteur
  pour predictions et alertes, source_fog du rapport pour les evenements de taches.
- `model/<model_version>` : predictions seulement, jusqu'a 64 caracteres.

Les dimensions inconnues sont ignorees ; leurs observations restent dans plant et
les autres dimensions connues. Les perimetres sont independants, sans filtre croise
zone + modele. Les catalogues/projections connus lors du calcul fournissent ces dimensions.

## Indicateurs indisponibles

Ces noms sont acceptes par `/analytics/kpis?metric=...` mais renvoient une collection
vide et une explication dans `unavailable_metrics`. Les anciens chiffres eventuels
dans la table ne sont pas exposes pour ces noms.

- `model_precision`, `false_alarm_rate` : labels de verite terrain et TP/FP absents.
  Une prediction voisine n'est pas la preuve qu'une alerte est vraie ou fausse.
- `mean_detection_latency_s` : lien causal entre mesure et alerte absent.
- `availability_percent` : couverture temporelle et transitions de panne incompletes.
- `mtbf_hours` : evenements de panne machine reelle absents ; une panne predite ne suffit pas.
- `task_recovery_time_s` : dates de panne, reprise effective et tentatives incompletes.
- `ingest_duplicate_ratio` : compteurs Prometheus de processus non persistants par heure.

## Stockage, refresh et exploitation

Les resultats vivent dans `kpi_records`, avec unicite metric / scope / scope_value / heure.
La migration `0002_kpi_scope` elargit scope_value de 16 a 64 caracteres, ajoute un index
received_at pour les rapports de taches et un index partiel resolved_at pour les
resolutions critiques. Il reste **neuf tables metier**, plus `alembic_version`.
Le downgrade refuse les valeurs de plus de 16 caracteres ; il ne les tronque pas.

Le worker `app.analytics.worker` execute les agregats SQL GROUPING SETS sur les
24 dernieres heures terminees par defaut, toutes les 60 secondes. Les lectures HTTP
consultent uniquement le cache, avec limit=50 (maximum 1000) et offset. Elles restent
publiques dans la politique de demonstration actuelle ; erreurs 422 et 503 documentees.

Un refresh utilise une session neuve, un snapshot REPEATABLE READ, un verrou transactionnel
advisory non bloquant et un timeout total de 30 secondes. Suppression des seuls indicateurs
possedes par ce module et insertion des nouveaux resultats partagent un commit atomique.
Un autre refresh actif produit busy ; une erreur, un timeout ou SIGTERM annule la transaction
et conserve le cache precedent. Le worker attend le schema migre et retente avec delais
croissants bornes par KPI_REFRESH_SECONDS ; aucune exception contenant le DSN n'est loggee.
Readiness n'est valide qu'apres commit, meme si la source est vide.

`KPI_LOOKBACK_HOURS` ne depasse pas RAW_RETENTION_DAYS * 24. L'heure partiellement
expirable la plus ancienne est exclue. Une periode explicite en dehors de l'horizon
est refusee, pour ne pas effacer un cache historique lorsque les sources ont expire.
Le cache n'est pas purge. Une donnee tardive hors lookback exige un refresh manuel
avant expiration de sa source. La retention est disponible depuis l'etape 8 en
simulation par defaut, avec activation explicite de la suppression.
Le dimensionnement sous charge reelle et l'optimisation restent a mesurer au jalon performance.
Depuis l'etape 8, la retention finalise les 15 indicateurs de mesures/predictions d'une
heure expiree avant suppression du brut. Une marque technique masque ces heures aux
nouvelles observations brutes, tout en conservant leurs KPI et doublons connus ; voir
[RETENTION.md](RETENTION.md). Les marques internes ne sont pas des KPI exposes par l'API.

Depuis PowerShell dans `mp3-cloud`, apres creation du `.env` et du catalogue :

```powershell
docker compose up -d --build api analytics
docker compose ps
docker compose logs --tail 30 analytics
Invoke-RestMethod http://127.0.0.1:8002/metrics
Invoke-RestMethod http://127.0.0.1:8000/api/v1/analytics/kpis
Invoke-RestMethod 'http://127.0.0.1:8000/api/v1/analytics/risk-ranking?limit=5'
Invoke-RestMethod http://127.0.0.1:8000/api/v1/analytics/model-comparison
docker compose exec analytics python -m scripts.refresh_kpis
```

Le CLI rafraichit une heure par defaut. Pour une periode explicite, fournir `--from`
et `--to` en UTC (adaptez les dates a des sources encore retenues) :

```powershell
docker compose exec analytics python -m scripts.refresh_kpis --from 2026-11-07T10:00:00Z --to 2026-11-07T11:00:00Z
```

Un CLI concurrent peut afficher busy et demander de reessayer. L'API a des periodes
maximales de 31 jours ; le CLI respecte aussi l'horizon de retention de la source.
Le contrat [OpenAPI](../../contracts/openapi.yaml) expose les schemas de ces quatre GET.

Le port 8002 expose `fog_cloud_kpi_ready`, `fog_cloud_kpi_last_success_timestamp_seconds`,
`fog_cloud_kpi_refresh_total{outcome=success|error|busy}` et `fog_cloud_kpi_last_written_rows`.
Docker exige ready=1 et un commit datant de moins de trois periodes de refresh.
Un healthy avec zero ligne signifie calcul disponible et source vide, pas Fog actifs.
Si unhealthy : verifier PostgreSQL et `alembic upgrade head`, les logs et le timeout.
Le worker reprend seul apres le retablissement ; augmenter le timeout/lookback seulement
apres mesure de charge. Les tests utilisent exclusivement des bases et brokers jetables.

## Verification

Le 7 novembre 2026 : 316 tests reussis avec --mqtt, Ruff, 11 fixtures, OpenAPI 3.0.3
et Compose valides. Images API / analytics Python 3.12 construites, quatre GET verifies
par HTTP et worker healthy. La base de travail reste sans observations synthetiques.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_analytics.py tests/test_analytics_database.py --postgres
.\.venv\Scripts\python.exe -m scripts.export_openapi --check
.\.venv\Scripts\python.exe -m pytest --mqtt
```

Les tests couvrent valeurs attendues, bornes, NULL, clock skew, perimetres, versions
de modele longues, heures multiples, idempotence, donnees tardives, snapshot concurrent,
verrou, rollback apres suppression, timeout/cancellation, reprise worker, migration
reversible sans troncature, validation des parametres, erreurs HTTP et schema OpenAPI.
