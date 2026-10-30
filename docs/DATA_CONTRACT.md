# Contrat de donnees partage - FOG

Congele en semaine 1. Toute modification = PR etiquetee `BREAKING` + validation MP3 (proprietaire du contrat).

Conventions communes :
- Encodage UTF-8, `Content-Type: application/json`.
- Tous les timestamps : **UTC**, format ISO-8601 avec suffixe `Z` (`2026-10-30T14:25:31Z`).
- IDs machines : `M01`..`M12`. Zones : `A`, `B`, `C`. Fog : `FOG_A`, `FOG_B`, `FOG_C`.
- Unites fixes : temperature en degres C, vibration en mm/s RMS, vitesse en tr/min, courant en A, pression en bar, puissance en kW, frequence en Hz.
- `message_id` : ULID ou UUIDv4 unique par emission, sert a la deduplication cote Cloud.

---

## 1. Machine data (MP1 -> MQTT -> MP2)

Topic : `fog/{zone}/sensor/{machine_id}`   (ex. `fog/A/sensor/M01`)

```json
{
  "message_id": "01J9ZK7Q9F3T2W8R1X0YABCDEF",
  "machine_id": "M01",
  "zone": "A",
  "timestamp": "2026-10-30T14:25:31Z",
  "temperature": 71.2,
  "vibration": 4.8,
  "speed": 1480,
  "current": 12.4,
  "pressure": 6.1,
  "power": 8.3,
  "frequency": 49.9,
  "state": "RUNNING"
}
```

| Champ | Type | Obligatoire | Regle |
|---|---|---|---|
| `message_id` | string(26) | oui | unique, reel sur 24 h glissantes |
| `machine_id` | string | oui | existe dans la table `machines` |
| `zone` | enum A/B/C | oui | incoherence avec machine_id = rejet |
| `timestamp` | date-time UTC | oui | non futur, >= 2020 |
| `temperature` | number | oui | -50..300 |
| `vibration` | number | oui | 0..100 |
| `speed` | number | oui | 0..20000 |
| `current` | number | oui | 0..1000 |
| `pressure` | number | optionnel | 0..100 |
| `power` | number | optionnel | 0..1000 |
| `frequency` | number | optionnel | 0..400 |
| `state` | enum | oui | `RUNNING`,`IDLE`,`STOPPED`,`FAULT` |

---

## 2. Prediction result (MP2 -> MQTT -> MP3)

Topic : `fog/{fog_id}/predictions`

```json
{
  "message_id": "01J9ZK7Q9F3T2W8R1X0YABCDEFG",
  "machine_id": "M01",
  "fog_id": "FOG_A",
  "timestamp": "2026-10-30T14:25:31Z",
  "risk_score": 0.78,
  "anomaly": true,
  "predicted_fault": "BEARING_WEAR",
  "severity": "WARNING",
  "model_version": "iforest-2026-10-28"
}
```

- `risk_score` : 0..1.
- `predicted_fault` : `NONE`, `BEARING_WEAR`, `OVERHEATING`, `IMBALANCE`, `ELECTRICAL_OVERLOAD`, `MISALIGNMENT`.
- `severity` : `NORMAL`, `WARNING`, `CRITICAL`.
- `model_version` obligatoire : sans lui, aucune comparaison de modeles possible cote Cloud.

---

## 3. Alert (MP2 -> MQTT -> MP3)

Topic : `fog/{fog_id}/alerts`

```json
{
  "message_id": "01J9ZK7Q9F3T2W8R1X0YABCDEFGHI",
  "alert_id": "ALR-2026-10-30-000123",
  "machine_id": "M01",
  "fog_id": "FOG_A",
  "timestamp": "2026-10-30T14:25:32Z",
  "type": "ANOMALY_DETECTED",
  "severity": "CRITICAL",
  "message": "Vibration 11.4 mm/s over threshold on M01",
  "recommended_action": "Inspect drive-end bearing within 24 h"
}
```

- `type` : `ANOMALY_DETECTED`, `THRESHOLD_EXCEEDED`, `PREDICTED_FAILURE`, `SENSOR_LOST`, `NODE_UNREACHABLE`.
- `alert_id` stable et unique : le cycle de vie (open/acknowledged/resolved) est pilote par le Cloud.

---

## 4. Fog status (MP2 -> MQTT -> MP3)

Topic : `fog/{fog_id}/status` (heartbeat, cadence <= 5 s)

```json
{
  "message_id": "01J9ZK7Q9F3T2W8R1X0YABCDEFGHJ",
  "fog_id": "FOG_A",
  "zone": "A",
  "status": "ONLINE",
  "cpu_percent": 63.4,
  "ram_percent": 48.1,
  "queued_tasks": 12,
  "active_tasks": 5,
  "last_heartbeat": "2026-10-30T14:25:30Z"
}
```

- `status` : `ONLINE`, `OVERLOADED`, `OFFLINE`, `RECOVERING`.
- Regle : un noeud est considere `OFFLINE` si 3 heartbeat manquent (= 15 s sans nouvelle).

---

## 5. Task event (MP2 -> MQTT -> MP3)

Topic : `tasks/events`

```json
{
  "message_id": "01J9ZK7Q9F3T2W8R1X0YABCDEFGHK",
  "task_id": "b3f1c2d4-6a11-4f3a-9c2e-7d5b1a0e9f42",
  "task_type": "ANOMALY_DETECTION",
  "priority": "HIGH",
  "critical": true,
  "source_fog": "FOG_A",
  "destination_fog": "FOG_B",
  "status": "COMPLETED",
  "created_at": "2026-10-30T14:25:28Z",
  "completed_at": "2026-10-30T14:25:31Z",
  "reason": "CPU > 85% on FOG_A"
}
```

- `task_id` : **UUIDv4 stable** obligatoire (sinon pas de dedup des evenements de migration).
- `task_type` : `ANOMALY_DETECTION`, `FEATURE_EXTRACTION`, `AGGREGATION`, `REPORTING`, `MODEL_RETRAIN`.
- `priority` : `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`.
- `status` : `CREATED`, `QUEUED`, `RUNNING`, `MIGRATED`, `COMPLETED`, `FAILED`, `RECOVERED`.
- Un meme `task_id` emet plusieurs evenements : le Cloud garde l historique complet, pas que le dernier.

---

## 6. HTTP d ingestion de secours (MP1/MP2/seed -> MP3)

`POST /api/v1/ingest/batch` avec `Authorization: Bearer $INGEST_TOKEN`

```json
{
  "messages": [
    { "kind": "prediction", "payload": { "...": "..." } },
    { "kind": "alert",      "payload": { "...": "..." } }
  ]
}
```

Reponse 207 Multi-Status :

```json
{
  "accepted": 42,
  "duplicates": 3,
  "rejected": 5,
  "errors": [
    { "index": 7, "code": "VALIDATION_ERROR", "detail": "risk_score must be <= 1" }
  ]
}
```

---

## 7. Erreurs API normalisees (RFC 7807)

```json
{
  "type": "https://fog-project/errors/validation",
  "title": "Validation Error",
  "status": 400,
  "detail": "zone 'D' is not a known zone",
  "instance": "/api/v1/ingest/batch"
}
```

Codes utilises : `200`, `201`, `207`, `400`, `401`, `404`, `409`, `422`, `429`, `500`, `503`.

---

## 8. Formats de test partagés

Fixtures valides : `contracts/fixtures/valid/*.json`
Fixettes invalides (doivent etre rejetees) : `contracts/fixtures/invalid/*.json`

Cas obligatoires fournis par MP3 et utilises par tous :
1. payload complet valide ;
2. timestamp non-UTC ;
3. valeur numerique hors bornes ;
4. `machine_id` inconnu ;
5. doublon strict (meme `message_id`).
