# MP3 - Industrial Cloud Backend, Data Management and Analytics

Responsable : Member 3 (toi) - Branche : `mp3/cloud`

## Mission
Couche Cloud de la plateforme : collecter les resultats des 3 nœuds Fog, les stocker
coheremment dans PostgreSQL, et exposer une API REST documentee pour le dashboard.
Le dashboard ne touche **ni la base, ni les services Fog** : tout passe par cette API.

## Perimetre (ce que je possede)
| Objet | Detail |
|---|---|
| Ingestion | Abonnement MQTT (`predictions`, `alerts`, `status`, `tasks/events`) + `POST /api/v1/ingest/batch` de secours |
| Base | 7 tables : `machines`, `sensor_data`, `predictions`, `alerts`, `fog_nodes`, `task_events`, `kpi_records` |
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
| T3 | Schema + migrations | 7 tables, FK, index, `alembic upgrade head` propre |
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
5. **UTC partout, `timestamptz` en base.** Trois conteneurs, trois fuseaux : la moindre erreur invalide tous mes calculs.
6. **Agrégats pre-calculés (vues materialisees / tables summary).** Les endpoints d historique doivent repondre
   en O(1), pas en scannant des millions de lignes.

## Structure du dossier
```
mp3-cloud/
  app/main.py            application FastAPI + routeur de sant
  app/api/               routers v1 (ingest, machines, measurements, predictions, alerts, fog, tasks, analytics)
  app/schemas/           modeles Pydantic par type de message
  app/models/            modeles SQLAlchemy (tables)
  app/db/                session, engine, migrations Alembic
  app/services/          logique metier : ingestion, dedup, kpis, aggregation
  scripts/               seed.py, check_contract.py
  tests/                 unitaires + integration (PostgreSQL reel via compose)
  sql/migrations/        SQL versionne
```

## Démarrage
```bash
cp .env.example .env
docker compose up -d db mosquitto
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
pytest -q
```
Docs : http://localhost:8000/docs - Sante : http://localhost:8000/healthz - Metriques : http://localhost:8000/metrics
