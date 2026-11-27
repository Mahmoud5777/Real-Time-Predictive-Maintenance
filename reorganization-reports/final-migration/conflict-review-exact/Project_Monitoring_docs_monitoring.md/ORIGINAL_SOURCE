# Monitoring Prometheus et Grafana — MP4

Cette configuration ajoute Prometheus, Grafana, Blackbox Exporter et cAdvisor dans
MP4, sans changer les Compose, le code ni les données de MP1, MP2 ou MP3. Elle utilise
le réseau externe existant `mp3-cloud_default` et conserve les données Prometheus et
Grafana dans deux nouveaux volumes nommés.

## Ports et démarrage

- Dashboard MP4 existant : `http://localhost:3001` (inchangé).
- Grafana : `http://localhost:3002` (bindé sur l'interface locale).
- Prometheus : `http://localhost:9090` (bindé sur l'interface locale).
- cAdvisor : réseau interne MP4 uniquement. Blackbox Exporter : réseau interne MP4 et
  réseau partagé, pour atteindre les services sondés.
- Seuls Prometheus et Blackbox Exporter rejoignent également `mp3-cloud_default`
  pour scruter les services externes; Grafana et cAdvisor restent isolés sur le
  réseau interne MP4.

Le Compose de monitoring est volontairement séparé du Compose du Dashboard. Depuis
`Project_Monitoring`, après validation et autorisation de déploiement :

```powershell
$env:GF_SECURITY_ADMIN_PASSWORD = '<choisir un mot de passe local non commité>'
docker compose -f docker/docker-compose.monitoring.yml config --quiet
docker compose -f docker/docker-compose.monitoring.yml up -d
docker compose -f docker/docker-compose.monitoring.yml ps
```

Le déploiement ne doit pas utiliser `down`, `down -v` ni une commande qui supprime le
réseau partagé. Les volumes `mp4-phase2-prometheus-data` et
`mp4-phase2-grafana-data` sont distincts des volumes existants.

## Collecte configurée

Prometheus collecte toutes les 15 secondes :

- MP3 API : `api:8000/metrics`.
- MP3 Ingest, Analytics, Supervision et Retention : leurs endpoints `/metrics`
  respectifs sur les ports internes 8001 à 8004.
- MP2 Scheduler et Fog A/B/C : leurs endpoints `/metrics` sur les ports internes
  8000 à 8003.
- Prometheus, Blackbox Exporter et cAdvisor.
- Des sondes HTTP pour l'API MP3, le proxy MP4, le Scheduler et chaque Fog node.
- Une sonde TCP sur `mosquitto:1883`. Elle vérifie uniquement l'ouverture TCP, pas
  l'authentification MQTT ni la publication/réception de messages.

Familles Prometheus vérifiées sur les endpoints actuels :

- MP3 API : `fog_cloud_http_requests_total`, métriques Python et processus.
- MP3 Ingest : compteurs de messages MQTT, état de connexion/prêt, profondeur de
  file et latence de traitement.
- MP3 Analytics, Supervision et Retention : état des cycles, dernier succès,
  résultats et volumes écrits.
- MP2 Scheduler/Fog : CPU/RAM Fog, taille de file, tâches terminées/échouées,
  migrations et histogrammes de latence/traitement.
- Blackbox : disponibilité (`probe_success`) et durée des sondes
  (`probe_duration_seconds`).
- cAdvisor : métriques CPU et mémoire des conteneurs visibles depuis l'hôte Linux
  Docker. Un lancement temporaire sur Docker Desktop a servi `/metrics` en HTTP 200
  et exposé des séries CPU/mémoire avec le label `id=/docker/<container-id>`.
  Les panneaux filtrent maintenant ces IDs pour exclure les cgroups parents. Les noms
  Compose ne sont pas fournis par les labels observés.

## Limites observées

- MP4 sert son interface sur `/metrics` (HTML), pas des métriques Prometheus. Il est
  supervisé par `/healthz` et par une route API en lecture seule.
- Les événements `/api/v1/tasks/events` et l'historique de supervision ne sont pas
  eux-mêmes des endpoints Prometheus. Les métriques de tâches MP2 sont des compteurs,
  jauges et histogrammes, pas une exportation de chaque événement MP3.
- Mosquitto ne fournit pas de `/metrics` observé. La sonde TCP ne prouve pas le bon
  fonctionnement du protocole MQTT.
- Aucun endpoint Prometheus ni exporter PostgreSQL n'a été vérifié/configuré.
- La configuration ne collecte pas l'état Docker détaillé (code de sortie ou compteur
  de redémarrages). `up` indique la disponibilité des endpoints scrutés; cAdvisor
  expose les conteneurs qu'il voit, sans historique fiable des conteneurs arrêtés.
- Le daemon Docker ne répond pas sur `localhost:9323/metrics`. cAdvisor a été validé
  séparément sur Docker Desktop avec ses montages hôte en lecture seule; les métriques
  Linux par ID sont accessibles. Les montages ne donnent pas les codes de sortie ni
  les compteurs de redémarrage. L'absence de `/dev/kmsg` désactive la collecte des
  événements OOM. Aucun socket Docker n'est monté.
- Cette intégration MP4 n'ajoute pas de target MP1; elle ne modifie ni n'instrumente
  le simulateur.
- Les endpoints des services MP2/MP3 sont joignables depuis l'hôte et leurs alias
  DNS sont présents sur le réseau partagé. Les états `UP`/`DOWN` Prometheus ne peuvent
  être confirmés qu'après démarrage autorisé de cette stack.

Grafana provisionne la source Prometheus et les tableaux de bord depuis les fichiers
de `docker/grafana`. Les tableaux de bord ne fabriquent pas de données : les panneaux
restent vides si une famille métrique n'a encore aucun échantillon.
