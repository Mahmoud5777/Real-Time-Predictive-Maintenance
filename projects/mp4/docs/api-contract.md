# Contrat API — MP3 Cloud

## 1. Base URL et conventions

L'API FastAPI utilise le préfixe `/api/v1`. En développement local, sa base est
`http://localhost:8000`; le Dashboard en mode API la contacte par le proxy Nginx.

Les routes de lecture sont publiques. La route d'ingestion requiert un en-tête
`Authorization: Bearer <token>`. Les dates sont des timestamps ISO 8601 avec
fuseau horaire ; MP3 les normalise en UTC. Les dates sans fuseau sont rejetées.

Les routes paginées renvoient :

```json
{
  "items": [],
  "meta": {
    "limit": 50,
    "offset": 0,
    "total": 0
  }
}
```

`limit` vaut de 1 à 1000 (défaut 50) et `offset` est supérieur ou égal à 0
(défaut 0). Les routes qui acceptent `from` et `to` utilisent des dates UTC ;
`from` doit être antérieur ou égal à `to`.

## 2. Routes utilisées par le Dashboard

| Méthode et chemin | Paramètres principaux | Réponse |
|---|---|---|
| `GET /api/v1/machines` | `zone` (`A`, `B`, `C`), `sort` (`machine_id`, `name`, `zone`, préfixe `-` pour l'ordre inverse), pagination | Page de `MachineRead` |
| `GET /api/v1/measurements` | `machine_id`, `zone`, `sort` (`timestamp`, `received_at`, `id`), `from`, `to`, pagination | Page de `MeasurementRead` |
| `GET /api/v1/predictions` | `machine_id`, `zone`, `fog_id`, `anomaly`, `severity`, `model_version`, `sort` (`timestamp`, `received_at`, `risk_score`, `id`), `from`, `to`, pagination | Page de `PredictionRead` |
| `GET /api/v1/alerts` | `machine_id`, `zone`, `fog_id`, `status`, `severity`, `sort` (`timestamp`, `received_at`, `id`), `from`, `to`, pagination | Page de `AlertRead` |
| `GET /api/v1/fog/nodes` | `zone`, `status`, `supervision_status`, `sort` (`fog_id`, `zone`, `last_heartbeat`), pagination | Page de Fog Nodes, avec horodatage de référence et seuils de supervision |
| `GET /api/v1/fog/status-history` | `fog_id`, `zone`, `status`, `sort` (`observed_at`, `received_at`, `id`), `from`, `to`, pagination | Page de `FogHistoryRead` |
| `GET /api/v1/tasks` | `origin_fog_id`, `current_fog_id`, `machine_id`, `zone`, `status`, `task_type`, `priority`, `critical`, `sort` (`created_at`, `last_received_at`), `from`, `to`, pagination | Page de `TaskRead` |
| `GET /api/v1/tasks/events` | `task_id` (UUID v4), `source_fog`, `destination_fog`, `zone`, `status`, `critical`, `time_field`, `sort`, `from`, `to`, pagination | Page de `TaskEventRead` |
| `GET /api/v1/fog/supervision-history` | `fog_id`, `zone`, `supervision_status`, `sort` (`observed_at`, `received_at`, `id`), `from`, `to`, pagination | Page de `FogSupervisionRead` |

`time_field` sur `/tasks/events` vaut `created_at`, `received_at` ou `occurred_at`.
Le tri des événements accepte ces trois champs et `id`, chacun avec un préfixe `-`
pour l'ordre décroissant.

Les routes de détail disponibles sont :

- `GET /api/v1/machines/{machine_id}` — un `MachineRead`.
- `GET /api/v1/machines/{machine_id}/latest` — la dernière `MeasurementRead`.
- `GET /api/v1/alerts/{alert_id}` — une `AlertRead`.
- `GET /api/v1/fog/nodes/{fog_id}` — un `FogNodeRead`.
- `GET /api/v1/tasks/{task_id}` — un `TaskRead` ; `task_id` est un UUID v4.

## 3. Champs renvoyés

- **Machine** : `machine_id`, `name`, `machine_type`, `zone`, `fog_id`. L'API ne
  fournit pas de champ `status` pour une machine ; le Dashboard le déduit des
  mesures et prédictions.
- **Mesure** : identifiants, machine/zone, `timestamp`, `received_at`,
  `temperature`, `vibration`, `speed`, `current`, `pressure`, `power`,
  `frequency`, `state`. Les trois dernières mesures citées peuvent être nulles ;
  `state` vaut `RUNNING`, `IDLE`, `STOPPED` ou `FAULT`.
- **Prédiction** : identifiants, machine/Fog, timestamps, `risk_score` entre 0 et
  1, `anomaly`, `predicted_fault`, `severity` (`NORMAL`, `WARNING`, `CRITICAL`)
  et `model_version`.
- **Alerte** : `alert_id`, machine/Fog, timestamps, `type`, `severity`, `message`,
  `recommended_action` (nullable), `status` (`OPEN`, `ACKNOWLEDGED`, `RESOLVED`)
  et dates/informations d'acquittement et de résolution.
- **Fog Node** : `fog_id`, `zone`, `status` (`ONLINE`, `OVERLOADED`, `OFFLINE`,
  `RECOVERING`), CPU/RAM, files et tâches actives, heartbeat, `offline_since`,
  `recovered_at` et informations de supervision. Les mesures de ressources et
  plusieurs dates peuvent être nulles.
- **Historique Fog** : `fog_id`, `zone`, `observed_at`, `received_at`, `status`,
  CPU/RAM, tâches en attente et actives. Cette route ne renvoie que les
  enregistrements de heartbeat.
- **Événement de tâche** : `task_id`, `task_type`, `priority`, `critical`,
  `source_fog`, `destination_fog`, `status`, `created_at`, `occurred_at`,
  `received_at`, `completed_at` et `reason`. Les statuts incluent `CREATED`,
  `QUEUED`, `RUNNING`, `MIGRATED`, `COMPLETED`, `FAILED` et `RECOVERED`.
  Les types de tâche incluent `ANOMALY_DETECTION`, `FAILURE_PREDICTION`,
  `FEATURE_EXTRACTION`, `AGGREGATION`, `REPORTING` et `MODEL_RETRAIN`; les
  priorités sont `CRITICAL`, `HIGH`, `MEDIUM` et `LOW`. Cette réponse ne contient
  pas `machine_id`.
- **Événement de supervision** : `fog_id`, `zone`, `observed_at`,
  `supervision_status`, `previous_supervision_status`, `supervision_reason` et
  éléments de preuve/intervalle éventuels. Les valeurs de supervision incluent
  `UNKNOWN`, `REACHABLE` et `UNREACHABLE`. `observed_at` est l'heure de la
  décision Cloud, pas nécessairement l'instant exact de la panne.

Les réponses de `/fog/nodes` ajoutent `as_of`, `heartbeat_timeout_seconds` et
`supervision_gap_seconds` à la page. Les routes de liste d'historique, dont
`/fog/supervision-history`, suivent le format de page commun.

## 4. Autres routes MP3

### Santé et métriques

- `GET /healthz` (hors `/api/v1`) renvoie l'état, le nom du service et sa version.
- `GET /metrics` (hors `/api/v1`) expose les métriques Prometheus au format texte.

### Ingestion de secours

`POST /api/v1/ingest/batch` accepte un corps de la forme :

```json
{
  "messages": [
    {
      "kind": "sensor",
      "payload": {
        "message_id": "mp4-doc-sensor-001",
        "machine_id": "M01",
        "zone": "A",
        "timestamp": "2026-11-19T09:00:00Z",
        "temperature": 65.2,
        "vibration": 2.1,
        "speed": 1480,
        "current": 12.5,
        "pressure": 3.4,
        "power": 5.5,
        "frequency": 50,
        "state": "RUNNING"
      }
    }
  ]
}
```

Chaque élément contient `kind` et `payload`; les champs du payload dépendent du
type de message MP3. La réponse `207` contient `accepted`, `duplicates`,
`rejected` et `errors`. Cette route requiert le token Bearer. Elle sert à
l'ingestion de secours, aux tests et au rejeu ; le flux principal est MQTT.

### Analytique

Les routes suivantes renvoient une page de KPI (`KpiPage`) avec `items`, `meta`,
`from_`, `to`, `unavailable_metrics`, `empty_reason` et `note` (`from_` est le
nom du champ dans la réponse JSON MP3) :

- `GET /api/v1/analytics/kpis` : paramètres `metric`, `scope`,
  `scope_value`, `from`, `to` et pagination.
- `GET /api/v1/analytics/measurements` : `scope`, `scope_value`, `from`, `to` et
  pagination.
- `GET /api/v1/analytics/model-comparison` : `model_version`, `from`, `to` et
  pagination.
- `GET /api/v1/analytics/risk-ranking` : `from`, `to` et pagination ; la fenêtre
  doit couvrir exactement une heure complète.

Les scopes disponibles sont `plant`, `zone`, `machine`, `fog` et `model` selon la
route. Chaque élément KPI comprend notamment `metric`, `scope`, `scope_value`,
`bucket_start`, `bucket_end`, `value`, `sample_size` et `computed_at`.

## 5. Exemple réel de réponse d'événement

Les champs ci-dessous correspondent au schéma `TaskEventRead` ; aucun
`machine_id` n'est fourni par cette route :

```json
{
  "items": [
    {
      "id": 12,
      "message_id": "d06d7053-c09b-47bd-9a9f-d8db6843b3ed",
      "task_id": "d0a6c76c-8e76-44db-99db-e02e3a9ed51b",
      "task_type": "ANOMALY_DETECTION",
      "priority": "HIGH",
      "critical": false,
      "source_fog": "FOG_A",
      "destination_fog": "FOG_B",
      "status": "MIGRATED",
      "created_at": "2026-11-19T09:00:00Z",
      "occurred_at": "2026-11-19T09:00:03Z",
      "received_at": "2026-11-19T09:00:04Z",
      "completed_at": null,
      "reason": "Load balancing"
    }
  ],
  "meta": {
    "limit": 50,
    "offset": 0,
    "total": 1
  }
}
```

## 6. Erreurs

Les erreurs de lecture utilisent les champs de problème `type`, `title`, `status`,
`detail` et `instance`. L'ingestion peut renvoyer `401` si le token est absent ou
invalide, `422` si la requête est invalide ou si tous les messages sont rejetés,
et `503` si la transaction ne peut pas être confirmée.
