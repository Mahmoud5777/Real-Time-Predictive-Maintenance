# Lot 4 — Collaborative Fog Computing

Guide d’installation, de simulation et de déploiement LAN du lot « intégration, supervision et validation ». Les commandes ci-dessous partent de la racine du dépôt et utilisent PowerShell 5.1 ou 7 avec Docker Desktop et Compose v2.

## Architecture

Le PC central héberge le scheduler MP2 et le broker MQTT. Il envoie les tâches vers Fog A, Fog B et Fog C via leurs API HTTP; les événements et échanges de coordination passent par MQTT. En simulation, les quatre rôles tournent sur le même PC avec un broker dédié `lot4-sim-mosquitto` et le réseau Docker isolé `lot4-sim-network`. Le broker MP2 existant reste séparé.

Prometheus collecte les métriques HTTP des services et Blackbox Exporter sonde `/health` et le port TCP MQTT. Grafana présente le dashboard existant UID `lot4-overview`. Les ports Grafana, Prometheus et Blackbox sont liés à `127.0.0.1` en configuration locale.

| Service | Port hôte | Usage |
|---|---:|---|
| Scheduler MP2 LAN | 8100 | API et métriques du scheduler central |
| Fog A/B/C LAN | 8101 / 8102 / 8103 | API HTTP des nœuds distants |
| Scheduler Lot 4 simulation | 8110 | Scheduler de simulation locale |
| Fog A/B/C simulation | 8201 / 8202 / 8203 | API des nœuds simulés |
| MQTT MP2 | 1884 local, 1883 LAN central | Broker MP2 |
| MQTT simulation | 1885 local | Broker indépendant de simulation |
| Prometheus / Blackbox | 9090 / 9115 | Supervision, interfaces locales |
| Grafana | 3002 | Dashboard, interface locale |

## Prérequis et configuration

- Windows 10/11, PowerShell 5.1 ou 7, Docker Desktop démarré et Compose v2.
- Pour le LAN physique: quatre PC sur un réseau privé routable, IPv4 fixes ou réservées, accès TCP selon le tableau ci-dessus.
- Les scripts ne configurent pas le pare-feu implicitement et ne créent aucun fichier `.env` automatiquement.

Préparer Grafana avant de démarrer la supervision:

```powershell
if (-not (Test-Path .\Lot4_LAN_Integration\monitoring\.env)) { Copy-Item .\Lot4_LAN_Integration\monitoring\.env.example .\Lot4_LAN_Integration\monitoring\.env }
notepad .\Lot4_LAN_Integration\monitoring\.env
```

Remplacer `GRAFANA_ADMIN_PASSWORD` par un secret aléatoire unique. Ce fichier est ignoré par Git. Le compose local n’expose Grafana que sur la boucle locale. Pour changer plus tard le mot de passe d’une base Grafana déjà initialisée, utiliser l’interface Grafana ou `grafana-cli admin reset-admin-password` dans le conteneur; modifier l’environnement seul ne change pas un compte existant.

## Simulation locale

Vérifier/Créer le réseau dédié sans toucher aux autres réseaux:

```powershell
docker network inspect lot4-sim-network *> $null
if ($LASTEXITCODE -ne 0) { docker network create lot4-sim-network }
```

Démarrer les trois Fog simulés (ce compose démarre également le broker MQTT isolé), puis le scheduler et la supervision:

```powershell
docker compose -f .\Lot4_LAN_Integration\fog-node\docker-compose.fog-local-sim.yml up -d --build
docker compose -f .\Lot4_LAN_Integration\central\docker-compose.scheduler-lan-sim.yml up -d
docker compose --env-file .\Lot4_LAN_Integration\monitoring\.env `
  -f .\Lot4_LAN_Integration\monitoring\docker-compose.monitoring.yml `
  -f .\Lot4_LAN_Integration\monitoring\docker-compose.monitoring-local.yml up -d
```

Contrôler l’état et les endpoints sans lancer de scénario de tâches MP2:

```powershell
docker ps --filter name=lot4 --filter name=mp2-scheduler-lan-sim
Invoke-RestMethod http://localhost:8110/health
Invoke-RestMethod http://localhost:8201/health
Invoke-RestMethod http://localhost:8202/health
Invoke-RestMethod http://localhost:8203/health
& .\Lot4_LAN_Integration\scripts\Test-Lot4.ps1
```

Interfaces: Prometheus `http://localhost:9090`, Grafana `http://localhost:3002`, Blackbox `http://localhost:9115`. Arrêt ciblé sans supprimer de données:

```powershell
docker compose -f .\Lot4_LAN_Integration\central\docker-compose.scheduler-lan-sim.yml stop
docker compose -f .\Lot4_LAN_Integration\fog-node\docker-compose.fog-local-sim.yml stop
docker compose --env-file .\Lot4_LAN_Integration\monitoring\.env `
  -f .\Lot4_LAN_Integration\monitoring\docker-compose.monitoring.yml `
  -f .\Lot4_LAN_Integration\monitoring\docker-compose.monitoring-local.yml stop
```

## Déploiement sur quatre PC

### PC 1 — Scheduler central et MQTT

Créer une configuration locale à partir de l’exemple, puis renseigner les quatre IPv4 réelles:

```powershell
if (-not (Test-Path .\Lot4_LAN_Integration\central\.env)) { Copy-Item .\Lot4_LAN_Integration\central\.env.central.example .\Lot4_LAN_Integration\central\.env }
notepad .\Lot4_LAN_Integration\central\.env
```

Le fichier unique `central\.env` contient `CENTRAL_LAN_IP`, `FOG_A_IP`, `FOG_B_IP`, `FOG_C_IP`. Depuis la racine du dépôt, valider puis démarrer le broker et le scheduler MP2 avec la configuration distante:

```powershell
docker compose --env-file .\Lot4_LAN_Integration\central\.env `
  -f .\Real-Time-Predictive-Maintenance\docker-compose.yml `
  -f .\Lot4_LAN_Integration\central\docker-compose.lan-central.yml config --quiet
docker compose --env-file .\Lot4_LAN_Integration\central\.env `
  -f .\Real-Time-Predictive-Maintenance\docker-compose.yml `
  -f .\Lot4_LAN_Integration\central\docker-compose.lan-central.yml up -d --build mosquitto scheduler
```

Cette intégration utilise les services MP2 existants sur le PC central; vérifier le contexte local avant de reconfigurer un scheduler déjà utilisé. Le broker LAN écoute sur TCP 1883. Ne pas publier ces ports sur Internet.

### PC 2, 3 et 4 — Fog A, B et C

Sur chaque PC, cloner/coller le dépôt avec la même structure relative, puis configurer l’adresse du PC central:

```powershell
if (-not (Test-Path .\Lot4_LAN_Integration\fog-node\.env.fog)) { Copy-Item .\Lot4_LAN_Integration\fog-node\.env.fog.example .\Lot4_LAN_Integration\fog-node\.env.fog }
notepad .\Lot4_LAN_Integration\fog-node\.env.fog
```

Démarrer le profil correspondant. Le paramètre `-CentralIP` évite de modifier le fichier local; à défaut, le script lit `CENTRAL_LAN_IP` dans `.env.fog`.

```powershell
& .\Lot4_LAN_Integration\scripts\Start-FogPC.ps1 -Node fog-a -CentralIP 192.168.1.10
& .\Lot4_LAN_Integration\scripts\Start-FogPC.ps1 -Node fog-b -CentralIP 192.168.1.10
& .\Lot4_LAN_Integration\scripts\Start-FogPC.ps1 -Node fog-c -CentralIP 192.168.1.10
```

Arrêt ciblé d’un seul nœud:

```powershell
& .\Lot4_LAN_Integration\scripts\Stop-FogPC.ps1 -Node fog-a
```

### Supervision LAN

Depuis PC 1, rendre la configuration Prometheus à partir de `central\.env`, puis lancer la stack monitoring avec `PROMETHEUS_CONFIG_FILE=prometheus-lan.yml` dans `monitoring\.env`:

```powershell
& .\Lot4_LAN_Integration\scripts\Render-Prometheus-LAN.ps1
notepad .\Lot4_LAN_Integration\monitoring\.env
docker compose --env-file .\Lot4_LAN_Integration\monitoring\.env `
  -f .\Lot4_LAN_Integration\monitoring\docker-compose.monitoring.yml up -d
```

Le template LAN collecte `/metrics` sur les quatre services HTTP et utilise Blackbox pour les health checks et MQTT. Tester la connectivité depuis PC 1:

```powershell
& .\Lot4_LAN_Integration\scripts\Test-Lot4-LAN.ps1 `
  -CentralIP 192.168.1.10 -FogAIP 192.168.1.11 -FogBIP 192.168.1.12 -FogCIP 192.168.1.13
```

Les valeurs ci-dessus sont des exemples: les remplacer par les adresses attribuées au LAN.

## Pare-feu

Le script affiche d’abord le plan et n’applique rien sans `-Apply`. L’exécuter dans une console administrateur avec une portée limitée au sous-réseau fiable:

```powershell
& .\Lot4_LAN_Integration\scripts\Set-Lot4-Firewall.ps1 -Role Central -TrustedRemote LocalSubnet -Apply
& .\Lot4_LAN_Integration\scripts\Set-Lot4-Firewall.ps1 -Role FogA -TrustedRemote 192.168.1.10 -Apply
```

Les règles ouvertes sont: central TCP 1883/8100; Fog A/B/C TCP 8101/8102/8103. Aucun script de démarrage n’appelle la configuration du pare-feu.

## Métriques et dashboard

Prometheus scrape les métriques exportées par les endpoints `/metrics` MP2 et Lot 4. Blackbox utilise `probe_success` pour HTTP et TCP. Les compteurs de tâches terminées et migrations peuvent n’avoir aucune série avant le premier événement; les histogrammes de dispatch/RTO/traitement ne donnent une moyenne que s’il existe des observations. Le panneau file d’attente affiche un zéro réel quand le service rapporte une file vide; « aucune donnée » indique l’absence de snapshot.

Les métriques de tâches échouées et migrations sont définies dans le collecteur MP2; elles ne sont pas supposées présentes tant qu’aucun événement à labels n’a été enregistré. Aucune métrique de débit de migrations distincte n’est inventée. Les alertes sont dans `monitoring/alert_rules.yml`.

Le dashboard n’a qu’une source JSON (`monitoring/grafana/dashboards/lot4-overview.json`); le script `Update-Lot4-Dashboard.ps1` synchronise la copie de provisioning. La datasource a l’UID stable `prometheus`, cible `lot4-prometheus:9090` et son provisioning est monté dans Grafana. En simulation locale, Grafana rejoint le réseau isolé partagé avec Prometheus. Après changement des fichiers Compose/provisioning, appliquer `docker compose up -d` avec les mêmes fichiers et le même projet Compose; les volumes nommés sont conservés.

## Validation

```powershell
& .\Lot4_LAN_Integration\scripts\Validate-Lot4-Config.ps1
& .\Lot4_LAN_Integration\scripts\Test-Lot4.ps1
```

Le premier vérifie les JSON, scripts PowerShell, Compose et promtool. Le second ajoute les conteneurs locaux, endpoints, targets et la syntaxe PromQL des panneaux. Il n’exécute aucun scénario métier MP2. Le test sur quatre machines reste à réaliser lorsque le matériel et le LAN de démonstration seront disponibles.

## Démonstration universitaire reproductible

1. Démarrer la simulation locale et la supervision selon les étapes ci-dessus.
2. Contrôler les services et Fog connus du scheduler:

   ```powershell
   Invoke-RestMethod http://localhost:8110/health
   Invoke-RestMethod http://localhost:8110/nodes
   Invoke-RestMethod http://localhost:8201/health
   Invoke-RestMethod http://localhost:8202/health
   Invoke-RestMethod http://localhost:8203/health
   & .\Lot4_LAN_Integration\scripts\Test-Lot4.ps1
   ```

3. Ouvrir `http://localhost:3002`, s’authentifier avec le compte et le secret de `monitoring/.env`, puis afficher le dashboard `Lot4 - Collaborative Fog Computing`. Présenter la disponibilité, les checks HTTP, MQTT et les jauges des trois Fog nodes. Dans Prometheus (`http://localhost:9090/targets`), montrer les 19 targets locales et MP2 en état `UP`.
4. Les panneaux de tâches, dispatch, RTO et migrations restent vides tant qu’aucun événement correspondant n’a été produit. Si la démonstration doit inclure une tâche, soumettre explicitement une requête au scheduler puis suivre son ID; cette action métier est distincte de la validation automatique:

   ```powershell
   $taskId = [guid]::NewGuid().ToString()
   $request = @{
     source_fog_id = 'fog-a'
     task = @{
       task_id = $taskId
       task_type = 'demonstration'
       priority = 'LOW'
       payload = @{}
     }
   } | ConvertTo-Json -Depth 5
   Invoke-RestMethod -Method Post -Uri http://localhost:8110/dispatch `
     -ContentType 'application/json' -Body $request
   Start-Sleep -Seconds 3
   Invoke-RestMethod -Uri "http://localhost:8110/tasks/$taskId"
   ```

   Les requêtes complétées font apparaître le débit de tâches; aucune migration/RTO n’est garantie par cette tâche unique. Pour le LAN, répéter la démonstration depuis PC 1 après les vérifications d’adresses et de pare-feu. Ce test physique n’a pas encore été exécuté.

## Dépannage

- **Target Prometheus `down`:** vérifier `/metrics`, IP/port, routage et pare-feu; `/health` et `/metrics` sont des chemins distincts.
- **Health `probe_success=0`:** ouvrir `http://IP:PORT/health` depuis PC 1 et vérifier que la réponse HTTP est 200.
- **MQTT inaccessible:** confirmer l’écoute centrale sur 1883 et la résolution d’adresse; la sonde TCP ne valide pas l’authentification MQTT.
- **Dashboard/datasource absents:** vérifier les deux mounts de provisioning, l’UID `prometheus`, les logs `docker logs lot4-grafana` et le chemin monté `/var/lib/grafana/dashboards`.
- **Métriques sans données:** distinguer une série inexistante faute d’événement d’une target indisponible (`up=0`). Ne pas transformer une absence d’événement en zéro ou en moyenne nulle.
- **Réseau local absent:** créer uniquement `lot4-sim-network`; ne pas supprimer les réseaux MP2/MP3/MP4.

## Limites

Le déploiement physique sur quatre PC, le routage réel, le pare-feu du laboratoire et les sondes entre machines ne peuvent pas être certifiés sur le PC actuel. Le broker MP2 LAN est configuré en accès anonyme par la configuration Mosquitto existante; le garder sur réseau de confiance, limiter le pare-feu et ne jamais faire de redirection publique. La configuration Grafana est fournie avec secrets externes et écoute localement par défaut.
