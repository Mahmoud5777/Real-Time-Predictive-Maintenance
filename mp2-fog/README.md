# MP2 - Collaborative Fog Computing and Fault-Tolerant Dynamic Scheduling

Responsable : Member 2 - Branche : `mp2/fog`

## Perimetre
- Trois services independants `FOG_A`, `FOG_B`, `FOG_C` recevant les mesures via MQTT.
- Suivi heartbeat, disponibilite, CPU/RAM, longueur de file, priorite et statut des taches.
- Taches critiques (detection temps reel) gardees locales ; migration des taches non critiques.
- Choix du noeud destinataire selon ressources disponibles et charge de la file.
- Coeurs de heartbeat manques = noeud `OFFLINE` -> reassigned des taches recuperables -> reintegration possible.
- Journalisation des migrations, temps d achevement, decisions de scheduling, temps de reprise.

## Livrables
- 3 services Fog + scheduler.
- Mecanisme heartbeat / reprise apres panne.
- Simulateur de taches.
- Scenarios de test : surcharge volontaire, arret d un noeud, retour du noeud.
- Benchmark statique vs dynamique.

## Interfaces
- Consomme `fog/{zone}/sensor/{machine_id}` (MP1).
- Publie `fog/{fog_id}/predictions`, `fog/{fog_id}/alerts`, `fog/{fog_id}/status`, `tasks/events` (MP3).
- Respect strict de `docs/DATA_CONTRACT.md` sections 2 a 5, notamment `task_id` UUID stable et timestamps UTC.

## Demarrage
```bash
docker compose up -d mosquitto
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python -m src.fog_node --id FOG_A --zone A
pytest -q
```
