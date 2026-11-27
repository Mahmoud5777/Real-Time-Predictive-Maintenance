# Rapport de finalisation — Lot 4

Date : 26 novembre 2026
Branche : `integration` (`origin/integration`)
Périmètre : `Lot4_LAN_Integration/`; aucun fichier d’un autre lot n’a été modifié.

## Éléments examinés

- Statut Git, branche, derniers commits et fichiers Lot 4 déjà modifiés/non suivis.
- Compose du scheduler central, des simulations central/Fog, du Fog distant et de la supervision.
- Prometheus, Blackbox, règles d’alerte, JSON du dashboard, provisioning Grafana et variables d’environnement d’exemple.
- Scripts PowerShell Lot 4 et collecteur MP2 réel `shared/metrics.py`, avec les endpoints `/metrics` et `/health`.
- Conteneurs, endpoints, targets Prometheus et APIs Grafana.

## Modifications réalisées

- Complété le scraping local pour le scheduler Lot 4, les Fog simulés, le scheduler et les Fog MP2, les health checks HTTP et les brokers MQTT. Ajout des labels de service, déploiement et Fog.
- Reconstruit le template Prometheus LAN pour scruter les quatre endpoints `/metrics` et sonder leurs `/health` ainsi que le port MQTT central. Le rendu valide les IPv4 et lit la configuration centrale sans l’écraser.
- Corrigé le réseau datasource Grafana : en local, Grafana rejoint le réseau partagé avec Prometheus; l’URL utilise le nom stable `lot4-prometheus`. Le répertoire de provisioning datasource est monté.
- Retiré le mot de passe Grafana en clair du compose. Ajout de `monitoring/.env.example`; un secret aléatoire local a été créé dans `monitoring/.env` (ignoré par Git) et le mot de passe de démonstration du compte existant a été remplacé. Aucun fichier `.env` préexistant n’a été modifié.
- Synchronisé le dashboard existant `lot4-overview` à 10 panneaux. Les requêtes correspondent aux jobs et métriques réellement exportés, utilisent `rate()` pour le débit et `_sum`/`_count` pour les moyennes, et n’inventent pas de valeurs lorsqu’il n’y a aucun événement.
- Ajouté les règles d’alerte MQTT/HTTP/disponibilité/ressources, les scripts de validation globale et de synchronisation du dashboard; renforcé les scripts IPv4, démarrage/arrêt Fog et pare-feu. Le pare-feu requiert explicitement `-Apply`; aucun démarrage n’applique de règles automatiquement.
- Ajouté le guide français Lot 4 et ce rapport.

## Résultats runtime observés

- Les conteneurs Lot 4, MP2, MP3 et MP4 étaient actifs lors du contrôle. Ils n’ont pas été arrêtés; seul Grafana a été recréé pour appliquer son provisioning, en conservant le volume `monitoring_lot4-grafana-data`.
- Endpoints de santé: Prometheus, Blackbox, Grafana, scheduler Lot 4 et MP2, Fog A/B/C simulés: réponses positives.
- Prometheus charge 19 targets sur neuf jobs; 19/19 sont `up`.
- `prometheus-lan.yml` est actuellement un rendu de démonstration avec les IP d’exemple `192.168.1.10`–`.13`; le script échoue si le fichier de configuration choisi ne contient pas les quatre adresses, et doit être relancé avec les vraies IP avant le LAN physique.
- Séries dans les panneaux de supervision: 8 disponibilités, 8 checks HTTP, 2 checks MQTT, 6 CPU, 6 RAM, 6 files d’attente et 1 série de tâches terminées.
- Aucun dispatch/RTO dans la fenêtre échantillonnée et aucune migration enregistrée. Ces panneaux événementiels restent sans donnée plutôt que d’afficher une moyenne ou un zéro trompeur. `fog_tasks_failed_total` et `fog_migrations_total` sont des familles définies par le collecteur; elles n’ont aucune série tant qu’aucun événement étiqueté ne les initialise.
- L’API Grafana sert le dashboard `lot4-overview`, version 2, avec 10 panneaux et datasource Prometheus par défaut. L’API health datasource retourne `OK`; le proxy Grafana exécute `up` et retourne 19 séries.

## Diagnostic des erreurs API

- Le 400 du health check datasource et le 502 du proxy étaient dus à une séparation de réseaux Compose : Grafana ne pouvait pas résoudre `prometheus`. Après raccordement au réseau commun et changement d’URL vers `lot4-prometheus`, le health check est `OK` et le proxy réussit.
- Le 400 de `POST /api/ds/query` venait du payload de diagnostic incomplet et du format attendu par cette API. Il ne signalait pas une panne du datasource; le proxy Prometheus et le health check ont confirmé sa disponibilité après correction réseau.

## Vérifications réellement exécutées

- `Validate-Lot4-Config.ps1` : PASS. Huit validations Compose/profils, JSON des deux dashboards et synchronisation, analyse syntaxique de 12 scripts PowerShell, `promtool check config` local et LAN, `promtool check rules` (5 règles).
- `Test-Lot4.ps1` : PASS. Conteneurs ciblés, sept endpoints HTTP, neuf jobs, 19 targets, syntaxe et présence des séries requises des dix requêtes PromQL, dashboard/datasource Grafana authentifiés et synchronisés.
- Aucun test métier MP2 n’a été relancé. Aucun résultat LAN physique n’est revendiqué.
- Aucun volume ou réseau n’a été supprimé; aucun `docker compose down -v` n’a été exécuté; aucun push GitHub n’a eu lieu.

## Limites et tâches restantes

- Les quatre PC physiques ne sont pas disponibles : adresses et routage réels, pare-feu du laboratoire, MQTT inter-PC, santé et scrape depuis le PC central restent à valider sur le LAN de démonstration.
- Les compteurs/histogrammes n’ont aucune observation immédiatement après démarrage; l’absence est décrite dans Grafana.
- Mosquitto conserve la configuration anonyme existante. Le broker LAN doit rester sur un réseau de confiance, avec des règles pare-feu limitées; aucune exposition Internet n’est prévue.
- Pour modifier le mot de passe Grafana persistant, utiliser l’interface ou `grafana-cli`; modifier uniquement la variable d’environnement ne change pas un compte déjà initialisé.
