# MP4 - Industrial Monitoring Dashboard, Observability and DevOps

Responsable : Member 4 - Branche : `mp4/dashboard`

## Perimetre
- Vue usine : 3 zones, 12 machines, etats Normal / Warning / Critical.
- Affiche mesures, sante, risque de panne, defaillance predite, alertes actives, recommandations.
- Sante des nœuds Fog : CPU/RAM, files, migrations, evenements offline, reprise.
- Prometheus + Grafana : dispo services, ressources, latence, metriques de taches.
- Docker Compose global + GitHub Actions (lint + tests) + health checks + config par environnement.

## Livrables
- Dashboard responsive, configs Prometheus/Grafana, docker-compose complet, workflow CI, guide d installation, script de demonstration (normal -> degradation -> surcharge -> panne -> reprise).

## Interfaces
- Consomme **uniquement** l API MP3 definie dans `contracts/openapi.yaml`.
- Consomme les metriques Prometheus exposees par MP2 et MP3.
- Interdit : acces direct a PostgreSQL ou aux topics MQTT.

## Demarrage
```bash
cd dashboard && npm install && npm run dev
docker compose -f ../infra/docker-compose.yml up -d
```
Developper d abord contre les mocks generes depuis le contrat OpenAPI de MP3.
