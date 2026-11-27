# Monitoring Prometheus et Grafana â€” MP4

Cette configuration ajoute Prometheus, Grafana, Blackbox Exporter et cAdvisor dans
MP4, sans changer les Compose, le code ni les donnÃ©es de MP1, MP2 ou MP3. Elle utilise
le rÃ©seau externe existant `mp3-cloud_default` et conserve les donnÃ©es Prometheus et
Grafana dans deux nouveaux volumes nommÃ©s.

## Ports et dÃ©marrage

- Dashboard MP4 existant : `http://localhost:3001` (inchangÃ©).
- Grafana : `http://localhost:3002` (bindÃ© sur l'interface locale).
- Prometheus : `http://localhost:9090` (bindÃ© sur l'interface locale).
- cAdvisor : rÃ©seau interne MP4 uniquement. Blackbox Exporter : rÃ©seau interne MP4 et
  rÃ©seau partagÃ©, pour atteindre les services sondÃ©s.
- Seuls Prometheus et Blackbox Exporter rejoignent Ã©galement `mp3-cloud_default`
  pour scruter les services externes; Grafana et cAdvisor restent isolÃ©s sur le
  rÃ©seau interne MP4.

Le Compose de monitoring est volontairement sÃ©parÃ© du Compose du Dashboard. Depuis
`projects/mp4`, aprÃ¨s validation et autorisation de dÃ©ploiement :

```powershell
$env:GF_SECURITY_ADMIN_PASSWORD = '<choisir un mot de passe local non commitÃ©>'
docker compose -f docker/docker-compose.monitoring.yml config --quiet
docker compose -f docker/docker-compose.monitoring.yml up -d
docker compose -f docker/docker-compose.monitoring.yml ps
```

Le dÃ©ploiement ne doit pas utiliser `down`, `down -v` ni une commande qui supprime le
rÃ©seau partagÃ©. Les volumes `mp4-phase2-prometheus-data` et
`mp4-phase2-grafana-data` sont distincts des volumes existants.

## Collecte configurÃ©e

Prometheus collecte toutes les 15 secondes :

- MP3 API : `api:8000/metrics`.
- MP3 Ingest, Analytics, Supervision et Retention : leurs endpoints `/metrics`
  respectifs sur les ports internes 8001 Ã  8004.
- MP2 Scheduler et Fog A/B/C : leurs endpoints `/metrics` sur les ports internes
  8000 Ã  8003.
- Prometheus, Blackbox Exporter et cAdvisor.
- Des sondes HTTP pour l'API MP3, le proxy MP4, le Scheduler et chaque Fog node.
- Une sonde TCP sur `mosquitto:1883`. Elle vÃ©rifie uniquement l'ouverture TCP, pas
  l'authentification MQTT ni la publication/rÃ©ception de messages.

Familles Prometheus vÃ©rifiÃ©es sur les endpoints actuels :

- MP3 API : `fog_cloud_http_requests_total`, mÃ©triques Python et processus.
- MP3 Ingest : compteurs de messages MQTT, Ã©tat de connexion/prÃªt, profondeur de
  file et latence de traitement.
- MP3 Analytics, Supervision et Retention : Ã©tat des cycles, dernier succÃ¨s,
  rÃ©sultats et volumes Ã©crits.
- MP2 Scheduler/Fog : CPU/RAM Fog, taille de file, tÃ¢ches terminÃ©es/Ã©chouÃ©es,
  migrations et histogrammes de latence/traitement.
- Blackbox : disponibilitÃ© (`probe_success`) et durÃ©e des sondes
  (`probe_duration_seconds`).
- cAdvisor : mÃ©triques CPU et mÃ©moire des conteneurs visibles depuis l'hÃ´te Linux
  Docker. Un lancement temporaire sur Docker Desktop a servi `/metrics` en HTTP 200
  et exposÃ© des sÃ©ries CPU/mÃ©moire avec le label `id=/docker/<container-id>`.
  Les panneaux filtrent maintenant ces IDs pour exclure les cgroups parents. Les noms
  Compose ne sont pas fournis par les labels observÃ©s.

## Limites observÃ©es

- MP4 sert son interface sur `/metrics` (HTML), pas des mÃ©triques Prometheus. Il est
  supervisÃ© par `/healthz` et par une route API en lecture seule.
- Les Ã©vÃ©nements `/api/v1/tasks/events` et l'historique de supervision ne sont pas
  eux-mÃªmes des endpoints Prometheus. Les mÃ©triques de tÃ¢ches MP2 sont des compteurs,
  jauges et histogrammes, pas une exportation de chaque Ã©vÃ©nement MP3.
- Mosquitto ne fournit pas de `/metrics` observÃ©. La sonde TCP ne prouve pas le bon
  fonctionnement du protocole MQTT.
- Aucun endpoint Prometheus ni exporter PostgreSQL n'a Ã©tÃ© vÃ©rifiÃ©/configurÃ©.
- La configuration ne collecte pas l'Ã©tat Docker dÃ©taillÃ© (code de sortie ou compteur
  de redÃ©marrages). `up` indique la disponibilitÃ© des endpoints scrutÃ©s; cAdvisor
  expose les conteneurs qu'il voit, sans historique fiable des conteneurs arrÃªtÃ©s.
- Le daemon Docker ne rÃ©pond pas sur `localhost:9323/metrics`. cAdvisor a Ã©tÃ© validÃ©
  sÃ©parÃ©ment sur Docker Desktop avec ses montages hÃ´te en lecture seule; les mÃ©triques
  Linux par ID sont accessibles. Les montages ne donnent pas les codes de sortie ni
  les compteurs de redÃ©marrage. L'absence de `/dev/kmsg` dÃ©sactive la collecte des
  Ã©vÃ©nements OOM. Aucun socket Docker n'est montÃ©.
- Cette intÃ©gration MP4 n'ajoute pas de target MP1; elle ne modifie ni n'instrumente
  le simulateur.
- Les endpoints des services MP2/MP3 sont joignables depuis l'hÃ´te et leurs alias
  DNS sont prÃ©sents sur le rÃ©seau partagÃ©. Les Ã©tats `UP`/`DOWN` Prometheus ne peuvent
  Ãªtre confirmÃ©s qu'aprÃ¨s dÃ©marrage autorisÃ© de cette stack.

Grafana provisionne la source Prometheus et les tableaux de bord depuis les fichiers
de `docker/grafana`. Les tableaux de bord ne fabriquent pas de donnÃ©es : les panneaux
restent vides si une famille mÃ©trique n'a encore aucun Ã©chantillon.
