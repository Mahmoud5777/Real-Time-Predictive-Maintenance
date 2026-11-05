# Guide d’autonomie MP3

Ce guide permet de démarrer, tester et démontrer le backend Cloud sans attendre
les producteurs MP1/MP2 ni le dashboard MP4. Les commandes utilisent PowerShell
et les ports par défaut de `mp3-cloud/.env.example`.

## 1. Préparer l’environnement

Prérequis : Python 3.11 ou supérieur, Docker Desktop démarré et Docker Compose.
Depuis la racine du projet :

```powershell
Set-Location mp3-cloud
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Configurer `INGEST_TOKEN` dans `.env`. Ce fichier reste local. Les commandes
suivantes s’exécutent toutes depuis `mp3-cloud/`, sans activation du virtualenv.

## 2. Démarrer la base, le catalogue et le worker

```powershell
docker compose up -d db mosquitto
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m scripts.init_catalogue
docker compose up -d --build ingest
docker compose ps
```

Attendre que PostgreSQL soit prêt avant la migration. Le catalogue initialise
trois Fog (`FOG_A`, `FOG_B`, `FOG_C`) et douze machines (`M01` à `M12`). Il est
rejouable et ne crée aucune mesure. Les Fog restent initialement `OFFLINE`, sans
heartbeat ; leur catalogue ne prouve pas que les environnements MP2 fonctionnent.

## 3. Lancer et consulter l’API

Dans un terminal PowerShell, depuis `mp3-cloud/` :

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Garder ce terminal ouvert. Depuis un second terminal :

```powershell
Invoke-RestMethod http://127.0.0.1:8000/healthz
Invoke-RestMethod http://127.0.0.1:8000/api/v1/machines
```

Swagger est accessible sur <http://127.0.0.1:8000/docs>. Les métriques de l’API
sont sur <http://127.0.0.1:8000/metrics> et celles du worker MQTT sur
<http://127.0.0.1:8001/metrics>. Le worker doit exposer `fog_cloud_mqtt_ready 1.0`.

## 4. Démontrer l’ingestion sans MP2

Pour générer un lot local sans écrire dans la base :

```powershell
.\.venv\Scripts\python.exe scripts/seed.py --scenario degradation --zone A --duration 60 --dump
```

Le résultat est `mp3-cloud/data/seed_degradation_A.json`. Pour l’envoyer par HTTP,
ouvrir `POST /api/v1/ingest/batch` dans Swagger, utiliser **Authorize** avec le
token de `.env`, puis copier le contenu du fichier dans le corps de la requête.
Le bilan expose `accepted`, `duplicates`, `rejected` et `errors` ; une insertion
ou un doublon donne une réponse 207.

Pour démontrer MQTT et la déduplication avec une fixture :

```powershell
.\.venv\Scripts\python.exe -m scripts.publish_mqtt --topic fog/A/sensor/M01 --file ../contracts/fixtures/valid/sensor_ok.json --repeat 3
Invoke-RestMethod http://127.0.0.1:8000/api/v1/machines/M01/latest
```

Cette publication écrit dans la base de travail. Si la fixture n’a jamais été
envoyée, les trois publications produisent une insertion et deux doublons.
Consulter aussi les compteurs du worker : la confirmation du programme de
publication concerne la réception par le broker.

## 5. Vérifier le projet

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe scripts/check_contract.py
docker compose config --quiet
```

Pour vérifier également PostgreSQL et MQTT :

```powershell
.\.venv\Scripts\python.exe -m pytest --mqtt
```

`--mqtt` inclut les tests PostgreSQL et nécessite Docker. Les tests d’intégration
créent puis suppriment leurs propres bases et brokers de test. Les résultats de
la dernière vérification documentée sont dans
[MQTT_INGESTION.md](mp3-cloud/docs/MQTT_INGESTION.md) ; relancer les commandes
pour connaître l’état du poste actuel.

## 6. Diagnostiquer et arrêter

```powershell
docker compose ps
docker compose logs --tail 50 db ingest mosquitto
.\.venv\Scripts\python.exe -m alembic current
.\.venv\Scripts\python.exe -m alembic check
```

- Worker en attente : vérifier la migration et l’initialisation du catalogue.
- HTTP 401 : vérifier le token fourni et la valeur `INGEST_TOKEN`.
- HTTP 422 : consulter les erreurs de validation ou le bilan des rejets.
- HTTP 503 : vérifier PostgreSQL, puis rejouer le lot avec les mêmes identifiants.
- Mesure absente : consulter les compteurs et logs du worker ; `/latest` renvoie
  404 tant qu’aucune mesure n’est stockée pour la machine.
- Déconnexions MQTT répétées : utiliser un seul worker par `MQTT_CLIENT_ID`.

Arrêter l’API avec `Ctrl+C`, puis les services avec `docker compose stop`.
Les volumes `pgdata` et `mqttdata` conservent les données et les sessions MQTT.

## 7. Poursuivre le développement

Le socle comprend les migrations, les catalogues, l’ingestion HTTP/MQTT et les
lectures des machines et de leur dernière mesure. La prochaine étape documentée
complète les API de lecture pour le dashboard. Les KPI, la rétention et la
détection automatique des heartbeats absents restent à développer.

Suivre [TASKS.md](mp3-cloud/TASKS.md) pour les critères de livraison,
[DATA_CONTRACT.md](docs/DATA_CONTRACT.md) pour les messages entrants et
[API_DESIGN.md](mp3-cloud/docs/API_DESIGN.md) pour les choix d’API.
Les données synthétiques permettent de vérifier MP3 ; la démonstration des trois
Fog réels et de leur collaboration dépend des environnements MP2.
