# Supervision persistante des heartbeats - etape 7

Reference executable : `app/supervision/service.py`. Le worker distinct
`app.supervision.worker` verifie les trois Fog toutes les 5 secondes par defaut.
Il observe leur joignabilite, sans modifier l'ordonnanceur MP2 ou inventer des charges.

## Etats, dates et preuves

`fog_nodes.status` reste le dernier statut rapporte par MP2 (ONLINE, OVERLOADED,
OFFLINE, RECOVERING). `offline_since` et `recovered_at` gardent les dates rapportees
par le producteur. La supervision utilise ses propres champs :

- `supervision_status` : UNKNOWN, REACHABLE ou UNREACHABLE.
- `supervision_reason` : NO_HEARTBEAT, FRESH_HEARTBEAT, HEARTBEAT_TIMEOUT,
  REPORTED_OFFLINE, CLOCK_SKEW ou MONITOR_GAP.
- `supervision_since` : derniere decision changeant l'etat ou la raison, date Cloud.
- `supervision_checked_at` : derniere verification transactionnelle confirmee.

Un Fog jamais observe reste UNKNOWN / NO_HEARTBEAT, sans faux evenement de panne.
REACHABLE exige que date producteur et reception Cloud soient toutes deux fraiches.
Le depassement strict de HEARTBEAT_TIMEOUT_SECONDS (15 s par defaut) produit
UNREACHABLE / HEARTBEAT_TIMEOUT ; l'egalite au seuil reste fraiche. Un statut frais
OFFLINE produit UNREACHABLE / REPORTED_OFFLINE. OVERLOADED et RECOVERING restent
joignables. Un nouveau heartbeat frais permet une reprise au prochain scan.
UNREACHABLE n'est pas la preuve d'une panne materielle : transport ou Cloud peuvent
etre responsables. Les dates de decision ne sont jamais des dates de panne reelle.

Une date producteur/reception dans le futur au-dela de HEARTBEAT_CLOCK_SKEW_SECONDS
(5 s par defaut) donne UNKNOWN / CLOCK_SKEW. Les horloges doivent etre synchronisees
et les dates sont UTC. Une correction fraiche de l'horloge producteur peut remplacer
une projection erronee dans le futur ; un vieux message retarde ne peut pas la corriger.
Les observations originales restent dans l'historique.

## Livraisons retardees et concurrence

Un ancien heartbeat MQTT retenu ne devient pas frais parce qu'il vient d'arriver.
La retransmission identique reste dedupliquee et ne renouvelle pas last_received_at.
Une observation plus ancienne ne remplace pas la projection, sauf correction fraiche
de l'horloge future decrite ci-dessus.

Le superviseur et l'ingestion verrouillent les memes lignes Fog. Les scans prennent
les verrous dans l'ordre fog_id et decident apres acquisition. Une reception concurrente
confirmee est lue avant la decision ou prise en compte au scan suivant. Deux scans
simultanes ne creent pas deux transitions identiques.
Depuis l'etape 9, ingestion et scans prennent FOR NO KEY UPDATE : ils restent
mutuellement exclusifs sur les etats, mais ne bloquent plus les FOR KEY SHARE des
cles etrangeres de predictions, alertes et taches. Ces operations ne changent jamais
fog_id ou zone. Un test maintient une prediction non commitee et verifie que le scan
et un heartbeat peuvent progresser ; le test de mise a jour concurrente conserve
la serialisation entre heartbeat et scan.
Etat courant, historique et dates de verification partagent un commit atomique.
Timeout (10 s par defaut), erreur SQL ou annulation annule tout le cycle. Le worker
attend schema et catalogue, utilise une session neuve par tentative et retente avec
delai croissant borne par l'intervalle. SIGTERM annule proprement le calcul ; les logs
ne montrent pas le DSN. KPI et supervision partagent la boucle/arret dans
`app/services/periodic.py`, avec registres, operations et transactions distincts.

## Couverture interrompue

Si deux scans confirmes sont distants de plus de SUPERVISION_GAP_SECONDS (30 s),
un Fog deja observe recoit UNKNOWN / MONITOR_GAP avec gap_start et gap_end. Une
decision sur les preuves actuelles suit au meme instant Cloud ; id departage donc
deux evenements possibles a cette date. La periode entre scans est sans couverture.
Aucune perte n'est antidatee a last_heartbeat + timeout ; aucune reprise manquee n'est
reconstruite. Les Fog jamais observes n'ont pas de faux evenements de lacune.
Une horloge Cloud qui recule ne reecrit pas le journal a une date anterieure.

Les lectures exposent `supervision_stale` et `effective_supervision_status` : sans
scan confirme, avec un scan trop ancien ou anormalement futur, l'etat effectif devient
UNKNOWN. L'etat stocke reste visible ; le filtre supervision_status porte sur celui-ci.
Lire l'API ne modifie aucune ligne. Une perte/reprise plus courte que l'intervalle
peut echapper au scan ; l'historique des statuts MP2 reste conserve.
`availability_percent` reste indisponible : la disponibilite reelle exige des preuves
et une definition de couverture supplementaires.

## Historique et migration

`0003_fog_supervision` reutilise fog_status_history : toujours neuf tables metier,
plus alembic_version. `record_type=HEARTBEAT` marque une observation MP2 avec
observed_at producteur et statut/charges obligatoires. `record_type=SUPERVISION`
marque une decision Cloud avec observed_at Cloud et statut/charges MP2 NULL.
Elle porte supervision_status, previous_supervision_status, supervision_reason,
evidence_heartbeat_at / evidence_received_at et timeout_seconds. gap_start/gap_end
sont obligatoires uniquement pour MONITOR_GAP. Les CHECK refusent le melange des
deux sources et les etats incompatibles avec leurs raisons. Les anciennes lignes
deviennent HEARTBEAT par defaut ; le contrat des messages producteurs reste identique.
L'index partiel ix_fog_supervision_observed aide les lectures du journal Cloud.
Le downgrade refuse des decisions Cloud presentes, pour ne pas supprimer leurs preuves.
Sauvegarder/exporter et definir leur conservation avant un retour a l'ancien schema.

`GET /api/v1/fog/status-history` garde seulement les HEARTBEAT.
`GET /api/v1/fog/supervision-history` donne les decisions Cloud : filtres fog_id, zone,
supervision_status et periode from/to inclusive UTC ; limit=50 (maximum 1000), offset,
tri observed_at, received_at ou id, prefixe `-` pour descendre. Erreurs 422/503 et schemas
sont dans OpenAPI. Les lectures restent publiques dans la demonstration actuelle.

## Lancement et reprise

Depuis PowerShell dans mp3-cloud, avec .env, PostgreSQL et catalogue initialises :

```powershell
docker compose up -d --build api ingest analytics supervision
docker compose ps
docker compose logs --tail 30 supervision
Invoke-RestMethod http://127.0.0.1:8000/api/v1/fog/nodes
Invoke-RestMethod http://127.0.0.1:8000/api/v1/fog/supervision-history
Invoke-RestMethod http://127.0.0.1:8003/metrics
```

Les parametres sont dans [.env.example](../.env.example). SUPERVISION_GAP_SECONDS
doit couvrir deux intervalles et intervalle + timeout DB. Calibrer les seuils sur les
delais producteurs observes ; 15 s est la valeur existante, sans calibration reelle prouvee.

Le port 8003 expose `fog_cloud_supervision_ready`,
`fog_cloud_supervision_last_success_timestamp_seconds`,
`fog_cloud_supervision_refresh_total{outcome=success|error|busy}` et
`fog_cloud_supervision_last_written_rows`. Docker exige ready=1 et un scan confirme
depuis moins que SUPERVISION_GAP_SECONDS. Healthy peut accompagner trois Fog UNKNOWN :
la sante du superviseur ne prouve pas leur activite. Si unhealthy, verifier PostgreSQL,
migration/catalogue et logs. La reprise est automatique ; les lacunes restent visibles.

## Verification

Le 7 novembre 2026 : 364 tests reussis avec --mqtt (48 controles supplementaires),
Ruff, 11 fixtures, OpenAPI 3.0.3 et Compose valides. Migration locale 0003 confirme,
supervision / ingestion / analytics Docker healthy. Les trois Fog jamais observes
restent UNKNOWN, avec zero decision de panne inventee et aucune donnee de scenario.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_supervision.py tests/test_supervision_database.py --postgres
.\.venv\Scripts\python.exe -m scripts.export_openapi --check
.\.venv\Scripts\python.exe -m pytest --mqtt
```

Les tests couvrent seuils, noeuds inconnus, pertes/reprises, vieux messages/doublons,
horloges futures/corrigees, lacunes, concurrence, verrou d'ingestion, rollback,
timeout/reprise, contraintes, downgrade sans perte, fraicheur, filtres et contrat HTTP.
Les scenarios vivent exclusivement dans des bases et brokers jetables, jamais fog_cloud.
