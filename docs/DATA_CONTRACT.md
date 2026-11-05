# Contrat de donnees - messages acceptes par MP3

Ce fichier definit **ce que mon backend accepte de stocker**. Il ne designe pas ce que les autres
mini-projets doivent devenir : si un producteur emet autre chose, mon ingestion rejette le message
et le compteur `invalid` augmente. C'est volontaire : une donnee hors contrat ne doit jamais
silencieusement polluer l historique ni les KPI.

Conventions imposees a l entree :
- UTF-8, JSON object, `Content-Type: application/json`.
- Champs inconnus = rejet (`extra="forbid"` dans `app/schemas/common.py`).
- Timestamps ISO-8601 avec fuseau explicite, normalises en UTC par la validation.
  `Z` ou `+00:00` sont les formats recommandes ; un timestamp naif est refuse.
- `message_id` obligatoire, 8 a 64 caracteres, unique par type : cle de la deduplication.
- Machines `M01`..`M12`, zones `A`/`B`/`C`, nœuds `FOG_A`/`FOG_B`/`FOG_C`.
- Unites : temperature degres C, vibration mm/s RMS, vitesse tr/min, courant A, pression bar,
  puissance kW, frequence Hz.

Exemples executables : `contracts/fixtures/valid/` (doivent etre acceptes) et
`contracts/fixtures/invalid/` (doivent etre rejetes). Verification :
`python mp3-cloud/scripts/check_contract.py`.

---

## 1. `sensor` - mesure machine

Topic attendu : `fog/{zone}/sensor/{machine_id}`

```json
{
  "message_id": "01J9ZK7Q9F3T2W8R1X0YABCDEF0",
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

Obligatoire : `message_id`, `machine_id`, `zone`, `timestamp`, `temperature` (-50..300),
`vibration` (0..100), `speed` (0..20000), `current` (0..1000), `state`
(`RUNNING`,`IDLE`,`STOPPED`,`FAULT`).
Optionnels : `pressure` (0..100), `power` (0..1000), `frequency` (0..400).

## 2. `prediction` - resultat d analyse d un nœud Fog

Topic attendu : `fog/{fog_id}/predictions`

```json
{
  "message_id": "01J9ZK7Q9F3T2W8R1X0YABCDEF1",
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

`risk_score` : 0..1. `predicted_fault` : `NONE`, `BEARING_WEAR`, `OVERHEATING`, `IMBALANCE`,
`ELECTRICAL_OVERLOAD`, `MISALIGNMENT`. `severity` : `NORMAL`, `WARNING`, `CRITICAL`.
`model_version` est **obligatoire** (1 a 64 caracteres) : sans lui, aucune comparaison de
modeles possible. La limite de 64 est aussi controlee par la base.

## 3. `alert` - alerte avec cycle de vie

Topic attendu : `fog/{fog_id}/alerts`

```json
{
  "message_id": "01J9ZK7Q9F3T2W8R1X0YABCDEF2",
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

`type` : `ANOMALY_DETECTED`, `THRESHOLD_EXCEEDED`, `PREDICTED_FAILURE`, `SENSOR_LOST`,
`NODE_UNREACHABLE`. `alert_id` contient 1 a 64 caracteres et reste unique global :
le cycle `OPEN -> ACKNOWLEDGED -> RESOLVED`
est pilote par le Cloud, donc cet identifiant ne doit jamais etre recycle.

## 4. `fog_status` - heartbeat d un nœud

Topic attendu : `fog/{fog_id}/status` (cadence <= 5 s, `retain=true`)

```json
{
  "message_id": "01J9ZK7Q9F3T2W8R1X0YABCDEF3",
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

`status` : `ONLINE`, `OVERLOADED`, `OFFLINE`, `RECOVERING`. MP3 conserve le dernier etat
observe et l'historique des heartbeats. La supervision temporelle prevue exposera un nœud
sans heartbeat pendant `HEARTBEAT_TIMEOUT_SECONDS` (defaut 15 s) comme `OFFLINE` ; cette
regle de timeout n'est pas encore implementee dans l'etape 4. Un ancien heartbeat retenu
ne constitue donc pas une preuve d'activite actuelle.

## 5. `task_event` - tache de scheduling

Topic attendu : `tasks/events`

```json
{
  "message_id": "01J9ZK7Q9F3T2W8R1X0YABCDEF4",
  "task_id": "b3f1c2d4-6a11-4f3a-9c2e-7d5b1a0e9f42",
  "task_type": "AGGREGATION",
  "priority": "MEDIUM",
  "critical": false,
  "source_fog": "FOG_A",
  "destination_fog": "FOG_B",
  "status": "MIGRATED",
  "created_at": "2026-10-30T14:25:28Z",
  "completed_at": null,
  "reason": "CPU > 85% on FOG_A"
}
```

`task_id` : **UUIDv4** (une regex le verifie) et stable sur toute la duree de la tache : un meme
`task_id` emet plusieurs evenements et je conserve tout l historique, sinon les mesures de
migration et de reprise sont impossibles.
`task_type` : `ANOMALY_DETECTION`, `FEATURE_EXTRACTION`, `AGGREGATION`, `REPORTING`, `MODEL_RETRAIN`.
`priority` : `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`.
`status` : `CREATED`, `QUEUED`, `RUNNING`, `MIGRATED`, `COMPLETED`, `FAILED`, `RECOVERED`.

`created_at` est la date de creation de la tache, pas celle de chaque evenement.
Le message actuel ne fournit pas de date propre a une migration ou reprise. MP3 conserve
donc ce manque et ne calcule pas de delai de migration a partir de l'heure de reception.
Une extension `occurred_at`, la sequence / tentative d'execution et le Fog rapporteur
restent a convenir avec MP2 avant de modifier les messages. Ces champs ne sont pas encore
acceptes par les schemas actuels (`extra="forbid"`).

---

## 6. Ingestion HTTP (`POST /api/v1/ingest/batch`)

Meme contenu que ci-dessus, enveloppe :

```json
{ "messages": [ { "kind": "prediction", "payload": { } } ] }
```

Reponse `207 Multi-Status` : `{ "accepted": 42, "duplicates": 3, "rejected": 5,
"errors": [ { "index": 7, "code": "VALIDATION_ERROR", "detail": "..." } ] }`.
`accepted` compte les insertions confirmees apres commit. `duplicates` compte les
retransmissions de contenu identique, sans modification d'etat ni d'historique.
Un lot compose uniquement de doublons recoit aussi `207`.

Si tous les messages sont rejetes : `422`, corps RFC 7807 avec `code=NO_VALID_MESSAGE`
et les quatre champs du bilan. Une enveloppe invalide recoit le `422` de FastAPI
avec sa liste `detail`. Route protegee par bearer token (`401` si absent ou invalide).

Une transaction non confirmee donne `503`, sans compteur d'insertions confirmees.
Le client rejoue alors les memes `message_id` ; il ne doit pas generer de nouveaux
identifiants pour une retransmission. Si la confirmation du commit est perdue, ce rejeu
permet de retrouver les doublons deja enregistres.

Erreurs par element : `VALIDATION_ERROR`, `UNKNOWN_KIND`, `REFERENCE_ERROR`,
`MESSAGE_ID_CONFLICT`, `IDENTIFIER_CONFLICT`, `TASK_CONFLICT`, `DATA_INTEGRITY_ERROR`.
Reutiliser un `message_id` avec un autre contenu est un conflit ; reutiliser un
`alert_id` sous un nouveau message n'ouvre ni ne modifie l'alerte existante.

Le pipeline et les regles d'etat sont detailles dans
[HTTP_INGESTION.md](../mp3-cloud/docs/HTTP_INGESTION.md). Aucun champ obligatoire nouveau
n'est ajoute aux cinq messages producteurs a cette etape.

L'entree MQTT utilise le meme service depuis l'etape 4. Son payload est l'objet brut,
sans enveloppe HTTP. Les regles de QoS, d'acquittement et de reprise sont dans
[MQTT_INGESTION.md](../mp3-cloud/docs/MQTT_INGESTION.md).

## 7. Erreurs normalisees (RFC 7807)

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

## 8. Negociation avec les producteurs

Je ne modifie pas le code d un autre mini-projet. Je signale donc explicitement :
- QoS 1 recommande : les re-emit sont absorbes par la contrainte d unicite sur `message_id`.
- Un producteur qui change un nom de champ casse mon ingestion ; ce changement doit etre annonce
  avant merge, pas decouvert en integration.
- Les fixtures de `contracts/fixtures/` servent de jeu de test commun : elles sont versionnees ici
  parce que c est mon module qui les execute.
