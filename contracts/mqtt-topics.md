# Topics MQTT - congeles semaine 1

| Topic | Producteur | Consommateur | Payload |
|---|---|---|---|
| `fog/{zone}/sensor/{machine_id}` | MP1 | MP2, MP3 | MachineData |
| `fog/{fog_id}/predictions` | MP2 | MP3 | PredictionResult |
| `fog/{fog_id}/alerts` | MP2 | MP3, MP4 (via API seulement) | AlertMessage |
| `fog/{fog_id}/status` | MP2 | MP3 | FogStatus (heartbeat <= 5 s) |
| `tasks/events` | MP2 | MP3 | TaskEvent |

Regles :
- QoS **1** pour predictions/alerts/status/tasks (au moins une fois) => le Cloud deduplique par `message_id`.
- `retain=true` uniquement pour `fog/{fog_id}/status` : un nouveau consommateur voit etat courant immediatement.
- Aucun topic ad hoc : ajouter un topic = PR sur `contracts/` + accord MP3.
- Retention broker desactivee en demo (`persistence false`) : la verite est en base, pas dans le broker.
