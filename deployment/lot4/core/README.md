# Lot 4 â€” Collaborative Fog Computing

Guide dâ€™installation, de simulation et de dÃ©ploiement LAN du lot Â« intÃ©gration, supervision et validation Â». Les commandes ci-dessous partent de la racine du dÃ©pÃ´t et utilisent PowerShell 5.1 ou 7 avec Docker Desktop et Compose v2.

## Architecture

Le PC central hÃ©berge le scheduler MP2 et le broker MQTT. Il envoie les tÃ¢ches vers Fog A, Fog B et Fog C via leurs API HTTP; les Ã©vÃ©nements et Ã©changes de coordination passent par MQTT. En simulation, les quatre rÃ´les tournent sur le mÃªme PC avec un broker dÃ©diÃ© `lot4-sim-mosquitto` et le rÃ©seau Docker isolÃ© `lot4-sim-network`. Le broker MP2 existant reste sÃ©parÃ©.

Prometheus collecte les mÃ©triques HTTP des services et Blackbox Exporter sonde `/health` et le port TCP MQTT. Grafana prÃ©sente le dashboard existant UID `lot4-overview`. Les ports Grafana, Prometheus et Blackbox sont liÃ©s Ã  `127.0.0.1` en configuration locale.

| Service | Port hÃ´te | Usage |
|---|---:|---|
| Scheduler MP2 LAN | 8100 | API et mÃ©triques du scheduler central |
| Fog A/B/C LAN | 8101 / 8102 / 8103 | API HTTP des nÅ“uds distants |
| Scheduler Lot 4 simulation | 8110 | Scheduler de simulation locale |
| Fog A/B/C simulation | 8201 / 8202 / 8203 | API des nÅ“uds simulÃ©s |
| MQTT MP2 | 1884 local, 1883 LAN central | Broker MP2 |
| MQTT simulation | 1885 local | Broker indÃ©pendant de simulation |
| Prometheus / Blackbox | 9090 / 9115 | Supervision, interfaces locales |
| Grafana | 3002 | Dashboard, interface locale |

## PrÃ©requis et configuration

- Windows 10/11, PowerShell 5.1 ou 7, Docker Desktop dÃ©marrÃ© et Compose v2.
- Pour le LAN physique: quatre PC sur un rÃ©seau privÃ© routable, IPv4 fixes ou rÃ©servÃ©es, accÃ¨s TCP selon le tableau ci-dessus.
- Les scripts ne configurent pas le pare-feu implicitement et ne crÃ©ent aucun fichier `.env` automatiquement.

PrÃ©parer Grafana avant de dÃ©marrer la supervision:

```powershell
if (-not (Test-Path .\deployment\lot4\core\monitoring\.env)) { Copy-Item .\deployment\lot4\core\monitoring\.env.example .\deployment\lot4\core\monitoring\.env }
notepad .\deployment\lot4\core\monitoring\.env
```

Remplacer `GRAFANA_ADMIN_PASSWORD` par un secret alÃ©atoire unique. Ce fichier est ignorÃ© par Git. Le compose local nâ€™expose Grafana que sur la boucle locale. Pour changer plus tard le mot de passe dâ€™une base Grafana dÃ©jÃ  initialisÃ©e, utiliser lâ€™interface Grafana ou `grafana-cli admin reset-admin-password` dans le conteneur; modifier lâ€™environnement seul ne change pas un compte existant.

## Simulation locale

VÃ©rifier/CrÃ©er le rÃ©seau dÃ©diÃ© sans toucher aux autres rÃ©seaux:

```powershell
docker network inspect lot4-sim-network *> $null
if ($LASTEXITCODE -ne 0) { docker network create lot4-sim-network }
```

DÃ©marrer les trois Fog simulÃ©s (ce compose dÃ©marre Ã©galement le broker MQTT isolÃ©), puis le scheduler et la supervision:

```powershell
docker compose -f .\deployment\lot4\core\fog-node\docker-compose.fog-local-sim.yml up -d --build
docker compose -f .\deployment\lot4\core\central\docker-compose.scheduler-lan-sim.yml up -d
docker compose --env-file .\deployment\lot4\core\monitoring\.env `
  -f .\deployment\lot4\core\monitoring\docker-compose.monitoring.yml `
  -f .\deployment\lot4\core\monitoring\docker-compose.monitoring-local.yml up -d
```

ContrÃ´ler lâ€™Ã©tat et les endpoints sans lancer de scÃ©nario de tÃ¢ches MP2:

```powershell
docker ps --filter name=lot4 --filter name=mp2-scheduler-lan-sim
Invoke-RestMethod http://localhost:8110/health
Invoke-RestMethod http://localhost:8201/health
Invoke-RestMethod http://localhost:8202/health
Invoke-RestMethod http://localhost:8203/health
& .\deployment\lot4\core\scripts\Test-Lot4.ps1
```

Interfaces: Prometheus `http://localhost:9090`, Grafana `http://localhost:3002`, Blackbox `http://localhost:9115`. ArrÃªt ciblÃ© sans supprimer de donnÃ©es:

```powershell
docker compose -f .\deployment\lot4\core\central\docker-compose.scheduler-lan-sim.yml stop
docker compose -f .\deployment\lot4\core\fog-node\docker-compose.fog-local-sim.yml stop
docker compose --env-file .\deployment\lot4\core\monitoring\.env `
  -f .\deployment\lot4\core\monitoring\docker-compose.monitoring.yml `
  -f .\deployment\lot4\core\monitoring\docker-compose.monitoring-local.yml stop
```

## DÃ©ploiement sur quatre PC

### PC 1 â€” Scheduler central et MQTT

CrÃ©er une configuration locale Ã  partir de lâ€™exemple, puis renseigner les quatre IPv4 rÃ©elles:

```powershell
if (-not (Test-Path .\deployment\lot4\core\central\.env)) { Copy-Item .\deployment\lot4\core\central\.env.central.example .\deployment\lot4\core\central\.env }
notepad .\deployment\lot4\core\central\.env
```

Le fichier unique `central\.env` contient `CENTRAL_LAN_IP`, `FOG_A_IP`, `FOG_B_IP`, `FOG_C_IP`. Depuis la racine du dÃ©pÃ´t, valider puis dÃ©marrer le broker et le scheduler MP2 avec la configuration distante:

```powershell
docker compose --env-file .\deployment\lot4\core\central\.env `
  -f .\projects\mp2\docker-compose.yml `
  -f .\deployment\lot4\core\central\docker-compose.lan-central.yml config --quiet
docker compose --env-file .\deployment\lot4\core\central\.env `
  -f .\projects\mp2\docker-compose.yml `
  -f .\deployment\lot4\core\central\docker-compose.lan-central.yml up -d --build mosquitto scheduler
```

Cette intÃ©gration utilise les services MP2 existants sur le PC central; vÃ©rifier le contexte local avant de reconfigurer un scheduler dÃ©jÃ  utilisÃ©. Le broker LAN Ã©coute sur TCP 1883. Ne pas publier ces ports sur Internet.

### PC 2, 3 et 4 â€” Fog A, B et C

Sur chaque PC, cloner/coller le dÃ©pÃ´t avec la mÃªme structure relative, puis configurer lâ€™adresse du PC central:

```powershell
if (-not (Test-Path .\deployment\lot4\core\fog-node\.env.fog)) { Copy-Item .\deployment\lot4\core\fog-node\.env.fog.example .\deployment\lot4\core\fog-node\.env.fog }
notepad .\deployment\lot4\core\fog-node\.env.fog
```

DÃ©marrer le profil correspondant. Le paramÃ¨tre `-CentralIP` Ã©vite de modifier le fichier local; Ã  dÃ©faut, le script lit `CENTRAL_LAN_IP` dans `.env.fog`.

```powershell
& .\deployment\lot4\core\scripts\Start-FogPC.ps1 -Node fog-a -CentralIP 192.168.1.10
& .\deployment\lot4\core\scripts\Start-FogPC.ps1 -Node fog-b -CentralIP 192.168.1.10
& .\deployment\lot4\core\scripts\Start-FogPC.ps1 -Node fog-c -CentralIP 192.168.1.10
```

ArrÃªt ciblÃ© dâ€™un seul nÅ“ud:

```powershell
& .\deployment\lot4\core\scripts\Stop-FogPC.ps1 -Node fog-a
```

### Supervision LAN

Depuis PC 1, rendre la configuration Prometheus Ã  partir de `central\.env`, puis lancer la stack monitoring avec `PROMETHEUS_CONFIG_FILE=prometheus-lan.yml` dans `monitoring\.env`:

```powershell
& .\deployment\lot4\core\scripts\Render-Prometheus-LAN.ps1
notepad .\deployment\lot4\core\monitoring\.env
docker compose --env-file .\deployment\lot4\core\monitoring\.env `
  -f .\deployment\lot4\core\monitoring\docker-compose.monitoring.yml up -d
```

Le template LAN collecte `/metrics` sur les quatre services HTTP et utilise Blackbox pour les health checks et MQTT. Tester la connectivitÃ© depuis PC 1:

```powershell
& .\deployment\lot4\core\scripts\Test-Lot4-LAN.ps1 `
  -CentralIP 192.168.1.10 -FogAIP 192.168.1.11 -FogBIP 192.168.1.12 -FogCIP 192.168.1.13
```

Les valeurs ci-dessus sont des exemples: les remplacer par les adresses attribuÃ©es au LAN.

## Pare-feu

Le script affiche dâ€™abord le plan et nâ€™applique rien sans `-Apply`. Lâ€™exÃ©cuter dans une console administrateur avec une portÃ©e limitÃ©e au sous-rÃ©seau fiable:

```powershell
& .\deployment\lot4\core\scripts\Set-Lot4-Firewall.ps1 -Role Central -TrustedRemote LocalSubnet -Apply
& .\deployment\lot4\core\scripts\Set-Lot4-Firewall.ps1 -Role FogA -TrustedRemote 192.168.1.10 -Apply
```

Les rÃ¨gles ouvertes sont: central TCP 1883/8100; Fog A/B/C TCP 8101/8102/8103. Aucun script de dÃ©marrage nâ€™appelle la configuration du pare-feu.

## MÃ©triques et dashboard

Prometheus scrape les mÃ©triques exportÃ©es par les endpoints `/metrics` MP2 et Lot 4. Blackbox utilise `probe_success` pour HTTP et TCP. Les compteurs de tÃ¢ches terminÃ©es et migrations peuvent nâ€™avoir aucune sÃ©rie avant le premier Ã©vÃ©nement; les histogrammes de dispatch/RTO/traitement ne donnent une moyenne que sâ€™il existe des observations. Le panneau file dâ€™attente affiche un zÃ©ro rÃ©el quand le service rapporte une file vide; Â« aucune donnÃ©e Â» indique lâ€™absence de snapshot.

Les mÃ©triques de tÃ¢ches Ã©chouÃ©es et migrations sont dÃ©finies dans le collecteur MP2; elles ne sont pas supposÃ©es prÃ©sentes tant quâ€™aucun Ã©vÃ©nement Ã  labels nâ€™a Ã©tÃ© enregistrÃ©. Aucune mÃ©trique de dÃ©bit de migrations distincte nâ€™est inventÃ©e. Les alertes sont dans `monitoring/alert_rules.yml`.

Le dashboard nâ€™a quâ€™une source JSON (`monitoring/grafana/dashboards/lot4-overview.json`); le script `Update-Lot4-Dashboard.ps1` synchronise la copie de provisioning. La datasource a lâ€™UID stable `prometheus`, cible `lot4-prometheus:9090` et son provisioning est montÃ© dans Grafana. En simulation locale, Grafana rejoint le rÃ©seau isolÃ© partagÃ© avec Prometheus. AprÃ¨s changement des fichiers Compose/provisioning, appliquer `docker compose up -d` avec les mÃªmes fichiers et le mÃªme projet Compose; les volumes nommÃ©s sont conservÃ©s.

## Validation

```powershell
& .\deployment\lot4\core\scripts\Validate-Lot4-Config.ps1
& .\deployment\lot4\core\scripts\Test-Lot4.ps1
```

Le premier vÃ©rifie les JSON, scripts PowerShell, Compose et promtool. Le second ajoute les conteneurs locaux, endpoints, targets et la syntaxe PromQL des panneaux. Il nâ€™exÃ©cute aucun scÃ©nario mÃ©tier MP2. Le test sur quatre machines reste Ã  rÃ©aliser lorsque le matÃ©riel et le LAN de dÃ©monstration seront disponibles.

## DÃ©monstration universitaire reproductible

1. DÃ©marrer la simulation locale et la supervision selon les Ã©tapes ci-dessus.
2. ContrÃ´ler les services et Fog connus du scheduler:

   ```powershell
   Invoke-RestMethod http://localhost:8110/health
   Invoke-RestMethod http://localhost:8110/nodes
   Invoke-RestMethod http://localhost:8201/health
   Invoke-RestMethod http://localhost:8202/health
   Invoke-RestMethod http://localhost:8203/health
   & .\deployment\lot4\core\scripts\Test-Lot4.ps1
   ```

3. Ouvrir `http://localhost:3002`, sâ€™authentifier avec le compte et le secret de `monitoring/.env`, puis afficher le dashboard `Lot4 - Collaborative Fog Computing`. PrÃ©senter la disponibilitÃ©, les checks HTTP, MQTT et les jauges des trois Fog nodes. Dans Prometheus (`http://localhost:9090/targets`), montrer les 19 targets locales et MP2 en Ã©tat `UP`.
4. Les panneaux de tÃ¢ches, dispatch, RTO et migrations restent vides tant quâ€™aucun Ã©vÃ©nement correspondant nâ€™a Ã©tÃ© produit. Si la dÃ©monstration doit inclure une tÃ¢che, soumettre explicitement une requÃªte au scheduler puis suivre son ID; cette action mÃ©tier est distincte de la validation automatique:

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

   Les requÃªtes complÃ©tÃ©es font apparaÃ®tre le dÃ©bit de tÃ¢ches; aucune migration/RTO nâ€™est garantie par cette tÃ¢che unique. Pour le LAN, rÃ©pÃ©ter la dÃ©monstration depuis PC 1 aprÃ¨s les vÃ©rifications dâ€™adresses et de pare-feu. Ce test physique nâ€™a pas encore Ã©tÃ© exÃ©cutÃ©.

## DÃ©pannage

- **Target Prometheus `down`:** vÃ©rifier `/metrics`, IP/port, routage et pare-feu; `/health` et `/metrics` sont des chemins distincts.
- **Health `probe_success=0`:** ouvrir `http://IP:PORT/health` depuis PC 1 et vÃ©rifier que la rÃ©ponse HTTP est 200.
- **MQTT inaccessible:** confirmer lâ€™Ã©coute centrale sur 1883 et la rÃ©solution dâ€™adresse; la sonde TCP ne valide pas lâ€™authentification MQTT.
- **Dashboard/datasource absents:** vÃ©rifier les deux mounts de provisioning, lâ€™UID `prometheus`, les logs `docker logs lot4-grafana` et le chemin montÃ© `/var/lib/grafana/dashboards`.
- **MÃ©triques sans donnÃ©es:** distinguer une sÃ©rie inexistante faute dâ€™Ã©vÃ©nement dâ€™une target indisponible (`up=0`). Ne pas transformer une absence dâ€™Ã©vÃ©nement en zÃ©ro ou en moyenne nulle.
- **RÃ©seau local absent:** crÃ©er uniquement `lot4-sim-network`; ne pas supprimer les rÃ©seaux MP2/MP3/MP4.

## Limites

Le dÃ©ploiement physique sur quatre PC, le routage rÃ©el, le pare-feu du laboratoire et les sondes entre machines ne peuvent pas Ãªtre certifiÃ©s sur le PC actuel. Le broker MP2 LAN est configurÃ© en accÃ¨s anonyme par la configuration Mosquitto existante; le garder sur rÃ©seau de confiance, limiter le pare-feu et ne jamais faire de redirection publique. La configuration Grafana est fournie avec secrets externes et Ã©coute localement par dÃ©faut.
