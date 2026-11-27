# Guide d’autonomie MP3

Ce guide permet de démarrer, tester et démontrer le backend Cloud sans attendre
les producteurs MP1/MP2 ni le dashboard MP4. Les commandes utilisent PowerShell
et les ports par défaut de `mp3-cloud/.env.example`.

## 1. Préparer l’environnement

Prérequis : Python 3.12 ou supérieur, Docker Desktop démarré et Docker Compose.
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
.\.venv\Scripts\python.exe -m scripts.export_openapi --check
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
13 routes de lecture du dashboard, détaillées dans
[READ_API.md](mp3-cloud/docs/READ_API.md), ainsi que quatre lectures analytics et un
worker de KPI horaires décrits dans [KPI_FORMULAS.md](mp3-cloud/docs/KPI_FORMULAS.md).
Lancer `docker compose up -d --build api analytics` depuis mp3-cloud pour les consulter
dans Swagger. Les métriques analytics sont sur http://127.0.0.1:8002/metrics.
La supervision persistante des heartbeats est réalisée : voir
[FOG_SUPERVISION.md](mp3-cloud/docs/FOG_SUPERVISION.md). Lancer aussi le service
`supervision` pour conserver les pertes/reprises et consulter `/fog/supervision-history`.
Ses métriques sont sur le port 8003. La rétention des mesures et prédictions est réalisée
en simulation par défaut : voir [RETENTION.md](mp3-cloud/docs/RETENTION.md). Le service
`retention` expose ses métriques sur 8004 et son CLI montre les candidats avant suppression.

Suivre [TASKS.md](mp3-cloud/TASKS.md) pour les critères de livraison,
[DATA_CONTRACT.md](docs/DATA_CONTRACT.md) pour les messages entrants et
[API_DESIGN.md](mp3-cloud/docs/API_DESIGN.md) pour les choix d’API.
Les données synthétiques permettent de vérifier MP3 ; la démonstration des trois
Fog réels et de leur collaboration dépend des environnements MP2.

## 8. Vérifier A/B/C et mesurer avant l'intégration d'équipe

Les abonnements MQTT couvrent déjà les trois zones avec le caractère `+`.
Le scénario suivant vérifie les douze machines, les transferts entre les trois Fog,
la supervision de B et la déduplication, dans une base et un broker jetables :

```powershell
.\.venv\Scripts\python.exe -m pytest --mqtt tests/test_mqtt_integration.py -k three_fog
```

Pour mesurer ensuite le débit, les lectures et les services concurrents :

```powershell
.\.venv\Scripts\python.exe -m pytest --mqtt --performance tests/test_performance.py -s -x --tb=short
```

Le [guide PERFORMANCE.md](mp3-cloud/docs/PERFORMANCE.md) précise la charge, l'isolation,
les limites et les rapports JSON dans mp3-cloud/data/benchmarks/. Les mesures longues
sont ignorées dans les tests ordinaires. Elles préparent MP3 sans ajouter de données
de démonstration à fog_cloud et sans exécuter les programmes MP2 ou MP4.

## 9. Étape 10 : expérimenter avec un laboratoire Docker séparé

Depuis mp3-cloud, Docker démarré :

```powershell
.\.venv\Scripts\python.exe -m scripts.lab start
.\.venv\Scripts\python.exe -m scripts.lab run --seconds 60 --hz 1
.\.venv\Scripts\python.exe -m scripts.lab status
```

Swagger du laboratoire : http://127.0.0.1:8100/docs. Les douze machines produisent
720 mesures en une minute à 1 Hz chacune, plus les prédictions, heartbeats, alertes
et événements de tâches. L'API et chaque worker sont dans des processus Docker
distincts du générateur Windows. La base fog_lab et ses volumes sont séparés de
fog_cloud ; la suppression des observations expirées est activée uniquement dans
ce laboratoire pour mesurer la maintenance.

Le [tutoriel LAB_ETAPE10.md](mp3-cloud/docs/LAB_ETAPE10.md) explique les observations,
les commandes SQL, p95, les limites et les exercices à 5 Hz. Pour nettoyer ensuite :

```powershell
.\.venv\Scripts\python.exe -m scripts.lab stop
```

Cette commande efface les conteneurs et données du laboratoire ; elle conserve
les rapports JSON dans mp3-cloud/data/lab/.
