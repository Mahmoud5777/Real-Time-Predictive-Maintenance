# Lot 4 deployment

Lot 4 coordinates local integration and the four-PC LAN deployment.

- `core/`: maintained LAN and local-simulation configuration, monitoring, and validation scripts.
- `automation/`: installation, configuration, and orchestration PowerShell scripts.
- `alternative-deployment/`: a separate LAN deployment implementation retained because its scripts and configuration differ from `core/`.

Start with `core/README.md` for topology and prerequisites. Copy `.example` files to local `.env` files and supply machine-specific values; real `.env` files remain local.

Static validation scripts do not start services. Deployment and service start/stop scripts are operational tools.