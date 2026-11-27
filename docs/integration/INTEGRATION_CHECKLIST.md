# Lot 4 LAN checklist

- [ ] Confirm static/reserved LAN IPs for Central and each Fog PC.
- [ ] Copy this bundle into repository root as `Lot4_LAN_Integration`.
- [ ] Configure central `.env` with all IPs.
- [ ] Ensure central MQTT listener/port 1883 is reachable only on trusted LAN.
- [ ] Central MP2 compose overlay validation: `docker compose -f ... config`.
- [ ] On each Fog PC, clone/copy repository and create `.env` (central IP).
- [ ] Start one Fog profile only (`fog-a`, `fog-b`, or `fog-c`).
- [ ] Check ports from central PC.
- [ ] Confirm Scheduler `/health` and `/nodes` show remote Fog nodes.
- [ ] Configure Prometheus targets with actual IPs.
- [ ] Confirm MP3 ingestion MQTT endpoint is pointed to central LAN broker if separated from Docker MP2 network.
- [ ] Keep the original single-PC compose mode available for rollback.
