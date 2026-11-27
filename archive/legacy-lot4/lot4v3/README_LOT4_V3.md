# Lot 4 LAN – correction pack v3

This is a correction pack, not a full deployment. Apply it to `Lot4_LAN_Integration` at the repository root. It preserves MP2's original compose and adds an optional local single-PC simulation.

## Contents
- `central/docker-compose.lan-central.yml`: overlay to use with MP2 base compose from the MP2 folder.
- `central/docker-compose.central-local-sim.yml`: Scheduler endpoints override for same-PC simulation.
- `fog-node/docker-compose.fog-remote.yml`: one Fog service per remote PC, profile-selected; corrected relative build/mount paths.
- `fog-node/docker-compose.fog-local-sim.yml`: local simulation with alternate host ports 8201-8203.
- `.env` templates for central and remote Fog.
- `scripts/Validate-Lot4-V3.ps1`: validates base/overlay/local-sim and Fog profiles without starting containers.

## Install
Extract the ZIP into the repository root, then run `scripts/Apply-Lot4-V3.ps1` from the repository root. This copies only the files into `Lot4_LAN_Integration`; it does not touch MP2 base compose or existing source code. Review the generated env templates before deployment.

## Central validation/deployment compose invocation
From `Real-Time-Predictive-Maintenance` directory:
`docker compose --env-file ..\Lot4_LAN_Integration\central\.env -f docker-compose.yml -f ..\Lot4_LAN_Integration\central\docker-compose.lan-central.yml config --quiet`
For real central deployment: add `up -d` only after IPs are configured and remote Fog PCs are ready.

## Local simulation
The central compose is first started using base + central overlay (Fog services disabled by profile), then add `central/docker-compose.central-local-sim.yml` for the local simulation Scheduler endpoints and start the local simulation Fog compose separately. Simulation Fog ports are 8201/8202/8203. Scheduler reaches those services through `host.docker.internal`; Fog containers reach the host MQTT broker at `host.docker.internal:1883`.

Run central compose from MP2 folder and Fog compose from repository root (paths are relative to each compose file). Never use local simulation ports for actual LAN deployment.
