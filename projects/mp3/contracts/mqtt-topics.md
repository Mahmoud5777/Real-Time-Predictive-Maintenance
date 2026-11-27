# Topics MQTT - congeles semaine 1

| Topic | Producteur | Consommateur | Payload |
|---|---|---|---|
| `fog/{zone}/sensor/{machine_id}` | MP1 | MP2, MP3 | MachineData |
| `fog/{fog_id}/predictions` | MP2 | MP3 | PredictionResult |
| `fog/{fog_id}/alerts` | MP2 | MP3, MP4 (via API seulement) | AlertMessage |
| `fog/{fog_id}/status` | MP2 | MP3 | FogStatus (heartbeat <= 5 s) |
| `tasks/events` | MP2 | MP3 | TaskEvent |

Regles :
- Les abonnements MP3 utilisent `+` : `fog/+/sensor/+`, `fog/+/predictions`,
  `fog/+/alerts`, `fog/+/status`. Ils couvrent deja A, B et C ; la validation limite
  les identifiants aux trois Fog et douze machines du catalogue.
- Mesures : M01-M04 en A, M05-M08 en B, M09-M12 en C. `tasks/events` est commun
  aux trois Fog ; source et destination figurent dans le payload.
- QoS **1** pour predictions/alerts/status/tasks (au moins une fois) => le Cloud deduplique par `message_id`.
- `retain=true` uniquement pour `fog/{fog_id}/status` : un nouveau consommateur voit etat courant immediatement.
- Aucun topic ad hoc : ajouter un topic = PR sur `contracts/` + accord MP3.
- Persistance broker activee (`persistence true`) avec un volume mqttdata. Les sessions
  persistantes et messages retenus peuvent survivre a un redemarrage propre du broker.
  PostgreSQL conserve l'historique metier ; Mosquitto conserve les livraisons en attente.
- MP3 utilise un client_id stable et une session MQTT 3.1.1 avec clean_session=false.
  Un seul worker actif doit utiliser cet identifiant. Ses abonnements sont confirmes en QoS 1.
- Les producteurs publient aussi en QoS 1 pour permettre la reprise. Les mesures QoS 0
  sont acceptees mais n'ont aucune garantie de relivraison.
- Payload MQTT = objet JSON directement, sans enveloppe HTTP kind/payload.
  Le topic doit correspondre aux identifiants du payload ; la zone sensor est celle de
  la machine, meme si un autre Fog effectue une analyse.
- Acquittement apres commit, doublon ou rejet definitif consigne. Une erreur temporaire
  de base est retentee sans ACK. Reutiliser le meme message_id lors d'un rejeu.
