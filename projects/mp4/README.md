# MP4 - Monitoring dashboard

MP4 provides the React/Vite frontend and the Prometheus, Grafana, Blackbox Exporter, and Nginx configuration used to observe the platform.

- `frontend/`: dashboard source, npm manifest/lockfile, and Dockerfile.
- `docker/`: monitoring and API proxy configuration, dashboards, and provisioning.
- `docker-compose.yml`: module-level compose entry point.

Use the frontend README for npm development commands. Review the compose files with their required MP3/MP2 endpoints and environment values before use.