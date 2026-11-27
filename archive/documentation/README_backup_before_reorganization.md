# Fog Project 2026

Monorepo regroupant les quatre mini-projets de la plateforme Collaborative Fog Computing for Real-Time Predictive Maintenance.

## Structure du dépôt

| Dossier | Description |
|---|---|
| MP1_Industrial_Simulation/ | Simulation industrielle |
| Real-Time-Predictive-Maintenance/ | Nœuds Fog, MQTT et scheduler |
| MP3_Backend_Source/ | Backend Cloud FastAPI et PostgreSQL |
| Project_Monitoring/ | Dashboard de supervision |

## Architecture générale

1. La simulation industrielle produit les données.
2. Les nœuds Fog traitent les données.
3. Le backend Cloud collecte et stocke les informations.
4. Le dashboard visualise les machines et les alertes.

## Technologies

- Python
- FastAPI
- PostgreSQL
- MQTT / Mosquitto
- React / Vite
- Docker / Docker Compose

## Organisation Git

La branche integration est la branche commune qui regroupe les quatre mini-projets.

## Collaboration

Pour récupérer le projet :

git clone -b integration https://github.com/Mahmoud5777/Real-Time-Predictive-Maintenance.git
