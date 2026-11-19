# MP3 - Industrial Cloud Backend, Data Management and Analytics

Responsable : Member 3 (toi) - Branche de travail actuelle : `mp3-cloud-backend`

## Mission
Couche Cloud de la plateforme : collecter les resultats des 3 nœuds Fog, les stocker
coheremment dans PostgreSQL, et exposer une API REST documentee pour le dashboard.
Le dashboard ne touche **ni la base, ni les services Fog** : tout passe par cette API.

## Perimetre (ce que je possede)
| Objet | Detail |
|---|---|
| Ingestion | Abonnement MQTT (`sensor`, `predictions`, `alerts`, `status`, `tasks/events`) + `POST /api/v1/ingest/batch` de secours |
| Base | 9 tables metier : catalogues, mesures, predictions, alertes, taches, historiques et KPI ; tables techniques `alembic_version` et `ingest_receipts` |
| Robustesse | Validation stricte Pydantic, rejet des payloads malformes, **deduplication** par `message_id` |
| Lecture | Machines, dernieres mesures, predictions, alertes, sante Fog, historique des taches ; pagination + filtres machine/zone/periode + tri |
| Analytics | Agregrats historiques, KPI usine, comparaison de modeles (`model_version`) |
| Contrat | `contracts/openapi.yaml` publie en semaine 1 = reference pour MP4 |
| Qualite | Tests API + base, migrations Alembic, script de seed, rapport de performance |

## Hors perimetre (a ne pas faire)
- Detection temps reel critique (MP2). Un appel reseau qui tombe ne doit jamais empecher une alarme locale.
- Calcul du ML (MP1). Je stocke et compare les resultats, je ne re-entraine pas en ligne.
- Rendu visuel (MP4). Je fournis les donnees, pas les graphiques.

## Plan en 12 taches
| # | Tache | Livrable verifiable |
|---|---|---|
| T1 | Lire et congele le contrat d equipe | `docs/DATA_CONTRACT.md` valide par les 4 membres |
| T2 | Environnement local | `docker-compose.yml` avec Postgres + Mosquitto + API |
| T3 | Schema + migrations | 9 tables, FK, bornes, index, migration et catalogue rejouables |
| T4 | Schemas Pydantic | validation bornes/types/UTC, fixtures invalides rejetees |
| T5 | Ingestion MQTT | un `mosquitto_pub` arrive en base |
| T6 | Deduplication | 3 envois identiques = 1 ligne + compteur `duplicates_rejected` |
| T7 | Ingestion HTTP batch | reponse 207 `{accepted, duplicates, rejected, errors[]}` |
| T8 | Endpoints de lecture | pagination, filtres, tri, Swagger exploitable |
| T9 | KPI + agregrats | job periodique + `/analytics/kpis`, formules documentees |
| T10 | Contrat OpenAPI publie | MP4 peut mocker sans attendre mon code |
| T11 | Tests automatiques | `pytest -q` vert depuis un clone frais |
| T12 | Perf + rapport | partitionnement, retention, batch writes, test de charge avant/apres |

## Augmentations prevues si le temps le permet
- `GET /api/v1/stream` (SSE) : le dashboard recoit les alarmes en push, son KPI « time to reflect alerts » depend de moi.
- `GET /healthz` + `GET /metrics` Prometheus : mon service devient visible dans Grafana (MP4).
- Seed scenarise : `python scripts/seed.py --scenario degradation --zone A --duration 120`.
- Audit trail des alertes (open / acknowledged / resolved, acteur, horodatage).
- Comparaison de modeles par `model_version` : valorise MP1 et MP2 dans mon rapport.

## Decisions deja prises (justifiees)
1. **Ingestion mixte MQTT + HTTP.** MQTT car MP2 est oriente topics ; HTTP batch car il me rend independant
   pour les tests, le seed et la demo. Sans cela je suis bloque des que MP2 est en retard.
2. **Dedup par contrainte d unicite, pas par applicatif.** En QoS 1 les re-emit sont garantis ; seule la base
   peut les refuser atomiquement. C'est aussi la seule facon de prouver le KPI « data consistency ».
3. **KPI calcules par moi, pas par les Fog.** Sinon chaque zone invente sa formule et le dashboard est incoherent.
4. **Brut 7 jours + agregrats illimites.** 12 machines a 1 Hz = ~1 M lignes/jour ; sans retention l historique
   devient inutilisable et mon rapport de perf perd son interet.
5. **UTC partout, `timestamptz` en base.** Les trois environnements Fog doivent produire des dates coherentes.
6. **Agrégats pre-calculés (vues materialisees / tables summary).** Les endpoints d historique doivent repondre
   sur des agregats deja calcules pour limiter le volume parcouru.

## Structure du dossier
```
mp3-cloud/
  app/main.py            application FastAPI + routeur de sant
  app/api/               routers v1 (ingest, machines, measurements, predictions, alerts, fog, tasks, analytics)
  app/schemas/           modeles Pydantic par type de message
  app/models/            modeles SQLAlchemy (tables)
  app/db/                sessions et initialisation des catalogues
  app/services/          logique metier : ingestion, dedup, kpis, aggregation
  scripts/               init_catalogue.py, publish_mqtt.py, seed.py, check_contract.py
  tests/                 unitaires + integration (bases PostgreSQL et brokers MQTT jetables)
  alembic/versions/      migrations versionnees du schema
```

## Démarrage
```bash
cp .env.example .env
docker compose up -d db mosquitto
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
python -m scripts.init_catalogue
docker compose up -d --build ingest
uvicorn app.main:app --reload
pytest -q
```
Docs : http://localhost:8000/docs - Sante : http://localhost:8000/healthz - Metriques : http://localhost:8000/metrics

## Etape 2 validee

Le schema et les catalogues sont expliques dans [docs/DATABASE_SCHEMA.md](docs/DATABASE_SCHEMA.md).
Sur ce poste : revision 0001_mp3_schema, neuf tables metier, trois Fog et douze machines.
Le catalogue ne cree pas de mesures ; les Fog restent OFFLINE jusqu'aux vrais heartbeats MP2.

Depuis PowerShell dans ce dossier :

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.init_catalogue
.\.venv\Scripts\python.exe -m alembic check
.\.venv\Scripts\python.exe -m pytest --postgres
```

`--postgres` cree et supprime une base mp3_test_<UUID> distincte ; il ne remet pas fog_cloud
a zero. Sans cette option, seuls les tests locaux s'executent. Les observations de collaboration
dans les tests sont synthetiques. L'ingestion HTTP persistante est realisee a l'etape 3.

## Etape 3 - ingestion HTTP persistante

`POST /api/v1/ingest/batch` utilise le service commun `persist_batch` pour enregistrer
les cinq types de messages. Les ecritures sont transactionnelles, les doublons identiques
sans effet, les erreurs metier isolees par element. Les etats Fog et les projections de
taches sont mis a jour avec leurs historiques. Un lot de doublons seuls recoit 207 ;
un lot entierement rejete recoit 422 ; une transaction non confirmee recoit 503.

Le guide [HTTP_INGESTION.md](docs/HTTP_INGESTION.md) explique les regles, les limites de
chronologie et les tests. Aucun nouveau champ producteur ni migration n'est ajoute.
Le worker MQTT de l'etape 4 appelle maintenant ce meme service.

## Etape 4 - ingestion MQTT operationnelle

Les cinq abonnements sont confirmes en QoS 1. Le worker valide topic et payload, appelle
`persist_batch`, puis acquitte apres une decision definitive. Une erreur temporaire de
base est retentee sans ACK ; les retransmissions identiques ne creent pas de nouvelle ligne.
Mosquitto conserve les sessions et messages retenus dans le volume `mqttdata`.

Guide de lancement, essai manuel et limites de reprise :
[MQTT_INGESTION.md](docs/MQTT_INGESTION.md).

```powershell
docker compose ps
docker compose logs --tail 50 ingest
.\.venv\Scripts\python.exe -m pytest --mqtt
```

Les metriques du worker sont sur http://127.0.0.1:8001/metrics, dans un registre distinct
de celui de l'API. Ne lancer qu'un worker par `MQTT_CLIENT_ID`. Les tests MQTT utilisent
des brokers et bases jetables ; aucune fixture n'est publiee dans la base de travail.
Verification complete : 149 tests reussis le 2 novembre 2026.

L'etape 5 est realisee ci-dessous. L'ordonnancement et l'inference ML restent dans MP2.

## Etape 5 - lectures du dashboard

Les 13 routes de lecture couvrent machines, derniere mesure, historique de mesures,
predictions, alertes et leur detail, etat / historique Fog, taches et leur journal.
Toutes les collections ont une pagination bornee, des filtres valides et un tri stable.
Les erreurs de lecture sont documentees, les dates inconnues restent NULL et les vieux
heartbeats sont marques stale sans modifier le dernier etat rapporte.

Le [guide READ_API.md](docs/READ_API.md) detaille routes, periodes, limites et exemples
PowerShell. Swagger declare les reponses et l'authentification de l'ingestion. Le contrat
publie distingue les lectures implementees des operations futures.

```powershell
.\.venv\Scripts\python.exe -m scripts.export_openapi --check
docker compose up -d --build api
```

L'etape 6 est realisee ci-dessous.
La supervision persistante des Fog, la retention et le partitionnement restent a venir.

## Etape 6 - KPI et agregats horaires

Le worker Docker `analytics` calcule 21 indicateurs observables sur des heures UTC
terminees et les stocke dans kpi_records. Les quatre GET `/analytics/kpis`,
`/analytics/measurements`, `/analytics/model-comparison`, `/analytics/risk-ranking`
consultent ce cache avec pagination, unites, effectifs et fraicheur. Les indicateurs
sans preuves (precision ML, disponibilite, temps de reprise) restent indisponibles.

Le [guide KPI_FORMULAS.md](docs/KPI_FORMULAS.md) donne formules, perimetres, limites,
configuration, refresh manuel et reprise. La migration 0002_kpi_scope conserve les
neuf tables metier et permet des versions de modele de 64 caracteres.

```powershell
docker compose up -d --build api analytics
docker compose logs --tail 30 analytics
Invoke-RestMethod http://127.0.0.1:8000/api/v1/analytics/kpis
```

Les metriques du worker sont sur http://127.0.0.1:8002/metrics. Sans observations,
les reponses restent vides avec une explication ; aucun chiffre de demonstration
n'est ajoute a la base de travail. Les etapes suivantes sont la supervision persistante,
la retention et les controles de performance. La supervision est realisee ci-dessous.

## Etape 7 - supervision persistante des Fog

Le worker Docker `supervision` verifie la fraicheur des heartbeats et conserve pertes,
reprises et lacunes de couverture. Le statut MP2 reste distinct de la joignabilite
Cloud UNKNOWN / REACHABLE / UNREACHABLE. Les Fog jamais observes restent UNKNOWN.
La migration 0003_fog_supervision conserve les neuf tables metier.

Le [guide FOG_SUPERVISION.md](docs/FOG_SUPERVISION.md) explique seuils, horloges,
livraisons retardees, concurrence, journal et reprise. Le journal est consultable
par `/api/v1/fog/supervision-history`, et les metriques du worker sur le port 8003.

```powershell
docker compose up -d --build api ingest analytics supervision
Invoke-RestMethod http://127.0.0.1:8000/api/v1/fog/nodes
Invoke-RestMethod http://127.0.0.1:8000/api/v1/fog/supervision-history
```

## Etape 8 - retention des mesures et predictions

Le worker `retention` finalise les agregats des heures expirees avant de purger le brut
par lots. Le registre technique ingest_receipts conserve la deduplication et les conflits
apres suppression. Le dernier capteur par machine, alertes, taches et preuves Fog restent
disponibles. Le [guide RETENTION.md](docs/RETENTION.md) donne limites, activation et reprise.

```powershell
docker compose up -d --build api ingest analytics supervision retention
docker compose exec retention python -m scripts.retain_raw
```

Simulation par defaut (RETENTION_DRY_RUN=true), metriques sur 8004. Le CLI --apply
supprime un lot ; RETENTION_DRY_RUN=false active la suppression periodique. Les deux
tables techniques s'ajoutent aux neuf tables metier : onze tables PostgreSQL au total.

## Etape 9 - trois zones et premiere mesure de performance

Les abonnements MQTT couvrent deja A/B/C. Un scenario teste les douze machines,
les trois alertes Fog, les transferts A->B->C->A, la supervision et les rejeux.
Les mesures longues comparent HTTP par lots, lectures, MQTT, jobs et retention
dans des bases et brokers jetables ; elles sont ignorees par les tests ordinaires.
Une contention de supervision reproduite avec une FK de prediction est corrigee
par FOR NO KEY UPDATE, sans modification de contrat ni de schema.

```powershell
.\.venv\Scripts\python.exe -m pytest --mqtt tests/test_mqtt_integration.py -k three_fog
.\.venv\Scripts\python.exe -m pytest --mqtt --performance tests/test_performance.py -s -x --tb=short
```

Le [guide PERFORMANCE.md](docs/PERFORMANCE.md) donne les conditions, les mesures
avant/apres et les limites. La latence des lectures sous charge et celle du MQTT
en rafale restent a ameliorer et a mesurer sur une topologie plus representative.
Cette baseline ne termine pas le dimensionnement ou le partitionnement de T12.

## Etape 10 - laboratoire pour tes propres essais

Le [tutoriel LAB_ETAPE10.md](docs/LAB_ETAPE10.md) explique comment generer les flux
des douze machines A/B/C, consulter PostgreSQL et Swagger, comparer les charges
et comprendre la latence. Le generateur Windows et les cinq processus backend
Docker sont separes. Le laboratoire possede sa base fog_lab, ses volumes et ses
ports ; il ne lit pas le .env de travail.

```powershell
.\.venv\Scripts\python.exe -m scripts.lab start
.\.venv\Scripts\python.exe -m scripts.lab run --seconds 60 --hz 1
.\.venv\Scripts\python.exe -m scripts.lab status
.\.venv\Scripts\python.exe -m scripts.lab sql
```

Swagger : http://127.0.0.1:8100/docs. A 1 Hz, 720 mesures et 120 autres messages
sont attendus en 60 s. Pour essayer 5 Hz, utiliser --hz 5. Les rapports JSON restent
dans data/lab/ (ignore par Git), meme apres `python -m scripts.lab stop`, qui efface
seulement les conteneurs et volumes du laboratoire.

Le test local de 120 s a 5 Hz a confirme 7428/7428 messages, sans erreur et avec
cadence respectee : p95 HTTP combine 69,7 ms, p95 MQTT reception->commit (75,100] ms.
La boucle MQTT non bloquante corrige le retard constate avant cet essai ; les ACK
restent apres commit et la file reste bornee. Le [rapport PERFORMANCE.md](docs/PERFORMANCE.md)
precise les conditions et la progression des workers. Les essais utilisent des
predictions synthetiques ; l'integration des programmes reels MP2/MP4 reste a valider.
