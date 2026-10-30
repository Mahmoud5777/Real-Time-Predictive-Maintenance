# Architecture - FOG

## Vue de bout en bout

```
+------------------- MP1 : SIMULATION -------------------+
| 12 machines (M01..M12) - zones A/B/C - 1 mesure/s      |
| scenarios : normal, bearing wear, overheat, imbalance, |
|             electrical overload                          |
+---------------------------+----------------------------+
                            | MQTT  fog/{zone}/sensor/{machine_id}
                            v
+------------------- MP2 : FOG LAYER --------------------+
| FOG_A            FOG_B            FOG_C                |
| clean -> features -> anomaly detection -> prediction    |
| Scheduler commun : heartbeat, priorites, migration,     |
| reprise apres panne de noeud                            |
+---------------------------+----------------------------+
                            | MQTT predictions / alerts / status / tasks
                            v
+------------------- MP3 : CLOUD BACKEND ----------------+
| ingest worker (MQTT subscriber) -> validation Pydantic  |
|   -> dedup message_id -> PostgreSQL (partitionne)       |
| REST API FastAPI : lecture, filtres, pagination,        |
|   analytics, KPI periodiques, SSE/WS temps reel         |
| /healthz + /metrics Prometheus                          |
+---------------------------+----------------------------+
                            | REST/JSON + SSE (OpenAPI contract)
                            v
+------------------- MP4 : DASHBOARD / DEVOPS ------------+
| React : etat usine, alertes, sante Fog, migrations      |
| Prometheus + Grafana, Docker Compose global, CI GitHub  |
+---------------------------------------------------------+
```

## Frontieres de responsabilite

| Couche | Possede | Ne fait jamais |
|---|---|---|
| MP1 | generation de donnees, scénarios, modele ML | decisions de routage |
| MP2 | analyse temps reel, scheduling, tolerance aux pannes | stockage historique |
| MP3 | verite des donnees, API, KPI, historique | calcul temps reel critique |
| MP4 | visualisation, observabilite, deploiement | acces direct BDD ou topics Fog |

## Flux critiques et latence cible

| Evenement | Chemin | Objectif |
|---|---|---|
| Anomalie machine -> alarme affichee | MP1 -> MP2 -> MP3 -> MP4 | < 3 s |
| Detection locale (critique) | MP1 -> MP2 local | < 500 ms, sans Cloud |
| Panne d un Fog -> taches reprises | MP2 heartbeat -> scheduler -> MP3 event log | RTO < 30 s |
| Rafraichissement dashboard | MP3 SSE push | < 1 s apres reception |

## Ou est la valeur de chaque couche

- **MP2** prouve que le Cloud n est plus indispensable (local first).
- **MP3** prouve que malgre la distribution, l usine a une memoire unique, propre et interrogeable.
- **MP4** rend les deux precedents demontrables.

## Volumetrie attendue (justifie les choix MP3)

- 12 machines x 1 mesure/s = 864 000 mesures/jour, ~1,04 M avec les re-emit.
- Predictions : meme ordre de grandeur si cadence 1/s par machine.
- Stratégie : brut partitionne par jour, retention 7 j, agrégats horaires et journaliers conserves sans limite.

## Points de decision ouverts

1. Orchestration finale : Docker Compose (retenu, suffisant pour 3 etudiants) vs k3s.
2. Base temporelle : PostgreSQL partitionné (retenu) vs TimescaleDB extension.
3. Temps réel vers MP4 : SSE (retenu, plus simple qu un WS stateful).
4. Auth ingestion : Bearer token via env (retenu), pas d OAuth complet.
