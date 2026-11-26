# Lot 4 — LAN deployment bundle (corrected v3)

This bundle is configuration tooling only. It does not alter existing MP1/MP2/MP3/MP4 source files and does not rerun MP2 scenario tests.

## Topology
- Central PC: MQTT broker, MP2 Scheduler, MP1 simulator, MP3/MP4, monitoring.
- Fog PC A/B/C: each runs only one remote Fog API.
- Cross-PC MQTT uses central PC LAN IP. Docker DNS/network names are PC-local and must not be used between PCs.

## 0) Validate local files first
From repository root in PowerShell, run:
```powershell
.\Lot4_LAN_Integration\scripts\Validate-Lot4-Config.ps1
```
The validator checks bundle inventory and Fog compose profiles. It creates example `.env` files if absent; edit them before deployment. It does not start containers.

## Central PC
Edit `Lot4_LAN_Integration\central\.env` with LAN IPv4 addresses for central and Fog PCs. From the MP2 folder, run:
```powershell
cd Real-Time-Predictive-Maintenance
docker compose -f docker-compose.yml -f ../Lot4_LAN_Integration/central/docker-compose.lan-central.yml --env-file ../Lot4_LAN_Integration/central/.env config --quiet
docker compose -f docker-compose.yml -f ../Lot4_LAN_Integration/central/docker-compose.lan-central.yml --env-file ../Lot4_LAN_Integration/central/.env up -d --build
```
The overlay keeps local Fog containers inactive by profile, removes Scheduler's local-Fog dependency, points it to remote host IPs, and publishes MQTT TCP 1883 for the LAN. The original local MQTT port mapping 1884 is preserved.

**Security:** the current Mosquitto config allows anonymous connections. Restrict Windows Firewall to trusted LAN clients; never port-forward MQTT or Fog APIs to the public Internet.

## Remote Fog PC
On each Fog PC, use a local copy of the repository at the same folder structure, copy `Lot4_LAN_Integration\fog-node\.env.fog.example` to repository-root `.env`, and set `CENTRAL_LAN_IP` to the central PC LAN address. From repository root:
```powershell
.\Lot4_LAN_Integration\scripts\Start-FogPC.ps1 -Node fog-a
```
Use `fog-b` or `fog-c` on the corresponding PC. The script validates Compose before starting the selected profile. Stop with:
```powershell
.\Lot4_LAN_Integration\scripts\Stop-FogPC.ps1 -Node fog-a
```
The Fog Compose build context is `Real-Time-Predictive-Maintenance`; the MP1 simulator bind mount expects root folder `mp1-simulator`.

## Monitoring
Prometheus does not automatically expand shell placeholders in its YAML. Render the LAN config with real IP addresses:
```powershell
.\Lot4_LAN_Integration\scripts\Render-Prometheus-LAN.ps1 -CentralIP 192.168.1.10 -FogAIP 192.168.1.11 -FogBIP 192.168.1.12 -FogCIP 192.168.1.13
```
Back up the current Prometheus config before replacing it. Confirm that the scheduler and Fog API expose the expected metrics endpoints; if the APIs do not expose Prometheus metrics, remove those scrape jobs or add exporters before expecting scrape success.

## Firewall
Run `Set-Lot4-Firewall.ps1` elevated on each PC, using Role Central/FogA/FogB/FogC and a restricted `TrustedRemote` scope. Central opens 1883 (MQTT) and 8100 (Scheduler); Fog nodes open their API port 8101/8102/8103.

## Network checks
From central PC:
```powershell
.\Lot4_LAN_Integration\scripts\Test-Lot4-LAN.ps1 -CentralIP 192.168.1.10 -FogAIP 192.168.1.11 -FogBIP 192.168.1.12 -FogCIP 192.168.1.13
```
Check Scheduler health at `http://CENTRAL_IP:8100/health` and `/nodes`. These are deployment connectivity checks only, not a repeat of MP2 scenario tests.
