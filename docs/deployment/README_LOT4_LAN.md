# Lot 4 — LAN deployment for the Collaborative Fog Computing project

This is a deployment bundle adapted to the inspected repository structure. It preserves the existing single-PC Compose files. It is a configuration bundle; it has not been executed against the user's local Docker environment.

## Topology

- Central PC: MP1 simulator, Mosquitto, MP2 scheduler, MP3 Cloud, MP4 dashboard, monitoring.
- Fog PC A/B/C: one existing Fog service each.
- MQTT is the cross-PC message bus. Docker bridge networks remain local to each PC.

## 1. Central PC setup

From the repository root, copy `central/.env.central.example` to `central/.env` and set:
- `CENTRAL_LAN_IP` to the central PC's LAN IPv4 (not localhost)
- `FOG_A_IP`, `FOG_B_IP`, `FOG_C_IP` to the Fog PC addresses

Start central MP2 using the existing MP2 Compose and the overlay:

```powershell
cd Real-Time-Predictive-Maintenance
docker compose -f docker-compose.yml -f ../Lot4_LAN_Integration/central/docker-compose.lan-central.yml --env-file ../Lot4_LAN_Integration/central/.env up -d --build
```

The overlay puts Fog services behind a `remote-fogs` profile (not started by default), removes scheduler's local Fog dependency, and configures scheduler URLs to the Fog PCs. MQTT port 1883 is exposed for LAN clients. **Only do this on a trusted LAN**; the current Mosquitto config allows anonymous access. For a lab LAN, use the firewall script and do not port-forward MQTT to the Internet.

Note: Compose env-file values are not automatically substituted into a service `env_file`; this overlay explicitly uses variables in the compose file.

## 2. Fog PC A/B/C

Copy `fog-node/.env.fog.example` to each Fog PC's working copy as `.env`, then edit:
- `FOG_NODE` (`fog-a`, `fog-b`, or `fog-c`)
- `FOG_ZONE` (`A`, `B`, or `C`)
- `FOG_API_PORT` (`8001`, `8002`, or `8003`)
- `CENTRAL_LAN_IP`

Use the corresponding command:
```powershell
docker compose -f fog-node/docker-compose.fog-remote.yml --env-file .env up -d --build
```
This compose file expects to be run from the repository root (build context is MP2 directory); adjust `FOG_NODE`/zone/port to the PC. Use a separate copy of the repo or bundle per Fog PC. The node binds its API to the host on the chosen port.

## 3. MP3 and monitoring

Existing MP3 overlay `docker-compose.mp2-integration.yml` uses the Docker network `mp2-network`, which is local to one PC. It is not a cross-PC bridge. In the LAN topology, MP2 MQTT and MP3 ingestion must be configured to reach central MQTT over the host LAN address if the MP3 ingest service is on central PC. Do not use Docker service names across computers.

For Prometheus, use `monitoring/prometheus-lan.yml` as the central scrape config. Targets are host IPs/ports. Apply it to the existing Prometheus volume mount only after backing up the existing config. Monitoring compose is based on the current Project_Monitoring docker compose and is a reference; Grafana password is required in `.env`.

## 4. Firewall and connectivity

- MQTT: TCP 1883 on central PC, inbound from trusted LAN only.
- Fog APIs: TCP 8101/8102/8103 on Fog PCs, inbound from central PC only (plus any required monitoring host).
- Scheduler: TCP 8100 central PC.
- Dashboard/MP3/monitoring ports remain as configured in the existing project.
- Do not expose these services to the public Internet.

## 5. Validation (configuration/network only)

On central PC:
```powershell
Test-NetConnection $FogA -Port 8101
Test-NetConnection $FogB -Port 8102
Test-NetConnection $FogC -Port 8103
Test-NetConnection $CentralIP -Port 1883
```
On each Fog PC:
```powershell
Test-NetConnection $CentralIP -Port 1883
```
Check central Scheduler `http://CENTRAL_IP:8100/health` and `/nodes`. Do not repeat MP2 scenario tests that have already been completed.

## 6. Rollback

Stop LAN services with `docker compose ... down` using the same files. The original `docker-compose.yml` and `docker-compose.integrated.yml` are not overwritten by this bundle.
