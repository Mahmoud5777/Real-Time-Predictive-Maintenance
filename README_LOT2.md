# Lot 2 — Connexion MP2 → MP3

## But

Relier le worker d'ingestion MQTT MP3 au broker utilisé par les Fog Nodes MP2.
Le code métier des deux côtés existe déjà :
- MP2 publie prédictions, alertes, heartbeats et événements de tâches en QoS 1.
- MP3 valide les topics et payloads, persiste dans PostgreSQL et déduplique `message_id`.

Le problème résolu ici est l'isolation des deux brokers Docker.

## Fichiers livrés

- `Real-Time-Predictive-Maintenance/docker-compose.yml` : broker MP2 exposé localement sur `127.0.0.1:1884`, volume de persistance ajouté.
- `Real-Time-Predictive-Maintenance/mosquitto/mosquitto.conf` : persistance Mosquitto activée.
- `MP3_Backend_Source/mp3-cloud/docker-compose.yml` : API/worker ne dépendent plus du broker MP3 local ; le broker MP3 reste disponible en mode autonome.
- `MP3_Backend_Source/mp3-cloud/docker-compose.mp2-integration.yml` : connecte uniquement le worker MP3 au réseau Docker `mp2-network` et au conteneur `mp2-mosquitto`.

Le fichier `.env` local de MP3 n'est ni inclus ni remplacé.

## 1. Installer les fichiers

Extraire le contenu de l'archive à la racine du dépôt `Collaborative-Fog-Computing`, en conservant les chemins.

Ne pas remplacer `MP3_Backend_Source/mp3-cloud/.env`.

Depuis PowerShell, à la racine du dépôt :

```powershell
$Root = (Get-Location).Path
$Mp3 = Join-Path $Root "MP3_Backend_Source\mp3-cloud"

if (-not (Test-Path (Join-Path $Mp3 ".env"))) {
    Copy-Item (Join-Path $Mp3 ".env.example") (Join-Path $Mp3 ".env")
    Write-Host "Fichier .env local créé depuis .env.example. Vérifier ses paramètres avant démarrage."
}
```

## 2. Démarrer le broker MP2

```powershell
$Mp2 = Join-Path $Root "Real-Time-Predictive-Maintenance"
Push-Location $Mp2

docker compose config --quiet
if ($LASTEXITCODE -ne 0) { throw "Configuration MP2 invalide" }

docker compose up -d --force-recreate mosquitto
if ($LASTEXITCODE -ne 0) { throw "Démarrage du broker MP2 échoué" }

Test-NetConnection 127.0.0.1 -Port 1884
docker network inspect mp2-network

Pop-Location
```

Le broker reste sur le réseau Docker `mp2-network` pour les conteneurs et expose le port local `1884` pour le simulateur MP1 lancé depuis Windows.

## 3. Démarrer MP3 connecté au broker MP2

```powershell
Push-Location $Mp3

$Compose = @("-f", "docker-compose.yml", "-f", "docker-compose.mp2-integration.yml")

docker compose @Compose config --quiet
if ($LASTEXITCODE -ne 0) { throw "Configuration MP3 intégrée invalide" }

docker compose @Compose up -d --build db api ingest analytics supervision retention
if ($LASTEXITCODE -ne 0) { throw "Démarrage MP3 échoué" }

# Initialise les catalogues des 3 Fog Nodes et des 12 machines.
docker compose @Compose exec api python -m scripts.init_catalogue

docker compose @Compose ps
Pop-Location
```

Dans ce mode, le service `ingest` rejoint deux réseaux :
- le réseau MP3 pour accéder à PostgreSQL ;
- le réseau externe `mp2-network` pour joindre `mp2-mosquitto:1883`.

Le broker Mosquitto propre à MP3 reste disponible pour les essais autonomes, mais il n'est pas démarré par cette commande d'intégration.

## 4. Vérifier que le worker MP3 est prêt

```powershell
$Metrics = (Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8001/metrics").Content
$Metrics -split "`n" | Select-String "fog_cloud_mqtt_(ready|connected|database_ready|accepted_total)"
```

Attendre que `fog_cloud_mqtt_ready` et `fog_cloud_mqtt_connected` soient à `1`.

Si le worker n'est pas prêt :

```powershell
Push-Location $Mp3
docker compose -f docker-compose.yml -f docker-compose.mp2-integration.yml logs --tail 100 ingest
Pop-Location
```

## 5. Test réel MP1 → MP2 → MP3

Ce test publie les mesures du dataset MP1 pour M01 sur le broker MP2. Fog A reçoit les mesures, exécute le modèle MP1 après sa période de warm-up, puis publie la prédiction. Le worker MP3 la stocke dans PostgreSQL.

```powershell
$Mp1 = Join-Path $Root "mp1-simulator"
Push-Location $Mp1

python -m src.simulator --dataset test --out data/generated
if ($LASTEXITCODE -ne 0) { throw "Génération du dataset MP1 échouée" }

python -c "import pandas as pd; d=pd.read_csv('data/generated/test.csv'); m=d[d.machine_id == 'M01']; m.to_csv('data/generated/lot2_smoke_M01.csv', index=False); print('M01 rows:', len(m))"
if ($LASTEXITCODE -ne 0) { throw "Préparation du flux M01 échouée" }

python -m src.publisher --csv data/generated/lot2_smoke_M01.csv --host 127.0.0.1 --port 1884 --speed 10 --qos 1 --limit 301
if ($LASTEXITCODE -ne 0) { throw "Publication MQTT MP1 échouée" }

Pop-Location
```

Le paramètre `--limit 301` correspond à 301 instants du dataset. Le publisher doit afficher le nombre de messages réellement envoyés.

Attendre quelques secondes puis vérifier les métriques et l'API :

```powershell
Start-Sleep -Seconds 5

$Metrics = (Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8001/metrics").Content
$Metrics -split "`n" | Select-String 'fog_cloud_mqtt_accepted_total\{kind="prediction"\}'

Invoke-RestMethod "http://127.0.0.1:8000/api/v1/predictions?machine_id=M01" |
    ConvertTo-Json -Depth 8
```

Résultat attendu :
- le compteur `fog_cloud_mqtt_accepted_total{kind="prediction"}` est supérieur à zéro ;
- l'API retourne au moins une prédiction pour `M01` ;
- `fog_id` vaut `FOG_A` ;
- `model_version` correspond au modèle MP1 utilisé par Fog A.

Si la prédiction n'apparaît pas immédiatement, consulter les logs `fog-a` et `ingest` avant de republier. Une republication doit conserver les mêmes `message_id` pour être dédupliquée correctement.

## 6. Vérification des trois Fog Nodes

Après validation du test M01, on pourra publier les données des machines M05 (zone B) et M09 (zone C), puis vérifier leurs prédictions avec :

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/v1/predictions?machine_id=M05" |
    ConvertTo-Json -Depth 8

Invoke-RestMethod "http://127.0.0.1:8000/api/v1/predictions?machine_id=M09" |
    ConvertTo-Json -Depth 8
```

## Important

- Ne jamais exécuter `docker compose down -v` : cela supprimerait les volumes PostgreSQL et MQTT.
- Ne pas lancer deux workers MP3 avec le même `MQTT_CLIENT_ID`.
- Le broker de démonstration autorise les connexions anonymes ; ne pas exposer ce port à Internet.
- Pour un déploiement sur plusieurs PC, remplacer le réseau Docker partagé par l'adresse IP LAN du PC central et configurer l'authentification MQTT/ACL. `mp2-mosquitto` est un nom DNS valable uniquement sur le réseau Docker partagé.
