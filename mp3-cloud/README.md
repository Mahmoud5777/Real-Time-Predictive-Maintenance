# MP3 - Industrial Cloud Backend, Data Management and Analytics

Responsable : Member 3 (toi) - Branche de travail actuelle : `codex/mp3-schema`

## Mission
Couche Cloud de la plateforme : collecter les resultats des 3 nœuds Fog, les stocker
coheremment dans PostgreSQL, et exposer une API REST documentee pour le dashboard.
Le dashboard ne touche **ni la base, ni les services Fog** : tout passe par cette API.

## Perimetre (ce que je possede)
| Objet | Detail |
|---|---|
| Ingestion | Abonnement MQTT (`sensor`, `predictions`, `alerts`, `status`, `tasks/events`) + `POST /api/v1/ingest/batch` de secours |
| Base | 9 tables : catalogues `machines` / `fog_nodes`, mesures `sensor_data`, `predictions`, `alerts`, etat `tasks`, historiques `task_events` / `fog_status_history`, agregats `kpi_records` |
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

La prochaine etape est 5 : completer les API de lecture pour le dashboard. L'ordonnancement
et l'inference ML restent dans MP2 ; la supervision temporelle des Fog et les KPI sont a venir.
