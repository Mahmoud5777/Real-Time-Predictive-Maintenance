# MP3 - Checklist executable

Legende : P = priorite, E = effort estime. Cocher au fur et mesure, une tache = une branche courte.

| # | Tache | P | E | Definition de fini | Branche |
|---|---|---|---|---|---|
| T1 | Faire valider le contrat donnees par l equipe | P0 | 0,5 j | PR `chore(contracts)` approvee par MP1/MP2/MP4 | `chore/mp3/contract-freeze` |
| T2 | Environnement local (compose Postgres + Mosquitto + API) | P0 | 0,5 j | `docker compose up` puis `/healthz` = 200 | `feat/mp3/env` |
| T3 | 7 tables + Alembic + index + partition `sensor_data` | P0 | 1 j | `alembic upgrade head` rejouable sur BDD vide | `feat/mp3/schema` |
| T4 | Schemas Pydantic stricts (bornes, UTC, enums) | P0 | 0,5 j | fixtures invalides rejetees par `check_contract.py` | `feat/mp3/schemas` |
| T5 | Consommateur MQTT -> insertion | P0 | 1 j | `mosquitto_pub` => ligne en base | `feat/mp3/ingest-mqtt` |
| T6 | Deduplication par `message_id` + compteur | P0 | 0,5 j | 3 envois identiques = 1 ligne, metrique dup = 2 | `fix/mp3/dedup` |
| T7 | `POST /ingest/batch` (207 + erreurs indexes) | P1 | 1 j | reponse `{accepted,duplicates,rejected,errors[]}` | `feat/mp3/ingest-http` |
| T8 | Endpoints lecture + pagination + filtres + tri | P0 | 1,5 j | Swagger exploitable, page de 50 par defaut | `feat/mp3/read-api` |
| T9 | KPI pre-calculs + `/analytics/*` | P1 | 1,5 j | formules documentees, valeurs stables | `feat/mp3/kpis` |
| T10 | Publier `openapi.yaml` + mocks pour MP4 | P0 | 0,5 j | MP4 developpe sans attendre mon code | `docs/mp3/openapi` |
| T11 | Tests API + base + CI verte | P0 | 1 j | `pytest -q` vert depuis clone frais | `test/mp3/api` |
| T12 | Partitionnement, retention, batch writes, test de charge | P1 | 1,5 j | rapport avant/apres avec p95 et debit | `perf/mp3/load` |
| B1 | SSE `/stream` pour le temps reel | P2 | 0,5 j | MP4 recoit une alerte en < 1 s | `feat/mp3/sse` |
| B2 | `/metrics` Prometheus | P2 | 0,5 j | mes series visibles dans Grafana | `feat/mp3/metrics` |
| B3 | Seed scenarise | P2 | 0,5 j | `seed.py --scenario degradation --zone A` | `feat/mp3/seed` |
| B4 | Audit trail alertes (ack/resolve) | P2 | 0,5 j | historique immuable consultable | `feat/mp3/alert-lifecycle` |

Chemin critique : T1 -> T3 -> T4 -> T5 -> T6 -> T8 -> T11. Les autres sont paralleles.
