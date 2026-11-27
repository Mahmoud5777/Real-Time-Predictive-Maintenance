# Docker et dÃ©ploiement â€” Dashboard MP4

MP4 est servi exclusivement par le conteneur API-only `mp4-dashboard-api` sur le port
`3001`. Le frontend utilise les routes rÃ©elles de l'API MP3; aucun mode Mock ni jeu de
donnÃ©es statiques n'est inclus dans le dÃ©ploiement.

## Configuration

- `docker-compose.yml` inclut `docker/docker-compose.api.yml`, afin que la commande
  Compose Ã  la racine ne lance que le Dashboard API-only.
- `docker/docker-compose.api.yml` construit l'image `mp4-dashboard:api` et publie le
  port `3001`.
- `frontend/Dockerfile` compile l'application avec Vite puis la sert avec Nginx.
- `docker/nginx/nginx.api.conf` est le proxy canonique vers `api:8000` sur le rÃ©seau
  externe `mp3-cloud_default`.
- `frontend/nginx.api.conf` est la configuration Nginx intÃ©grÃ©e par dÃ©faut Ã  l'image;
  elle doit rester synchronisÃ©e avec la configuration canonique.
- `frontend/nginx.conf.bak` est une sauvegarde conservÃ©e et n'est pas utilisÃ©e par le
  build API-only.

Le rÃ©seau externe `mp3-cloud_default` et le service API MP3 doivent dÃ©jÃ  exister. Le
Compose MP4 ne dÃ©marre et ne modifie aucun service MP3.

## Validation et dÃ©ploiement

Depuis `projects/mp4` :

```powershell
docker compose -f docker-compose.yml config --quiet
docker compose -f docker/docker-compose.api.yml config --quiet
docker compose -f docker-compose.yml up -d --build
docker compose -f docker-compose.yml ps
docker inspect mp4-dashboard-api --format '{{.State.Status}} {{.State.Health.Status}}'
```

Le conteneur attendu est `mp4-dashboard-api`, exposÃ© sur `http://localhost:3001`.

## VÃ©rification HTTP

```powershell
$routes = @(
  '/',
  '/healthz',
  '/api/v1/machines',
  '/api/v1/measurements',
  '/api/v1/predictions',
  '/api/v1/alerts',
  '/api/v1/fog/nodes',
  '/api/v1/tasks/events',
  '/api/v1/fog/supervision-history'
)
foreach ($route in $routes) {
  $response = Invoke-WebRequest "http://localhost:3001$route" -UseBasicParsing
  "$route HTTP $([int]$response.StatusCode)"
}
```

Les routes API sont relayÃ©es par Nginx vers MP3. Les donnÃ©es affichÃ©es dans MP4
proviennent des rÃ©ponses API; une erreur ou une rÃ©ponse vide n'est pas remplacÃ©e par
des donnÃ©es de dÃ©monstration.

## Journaux et arrÃªt ciblÃ©

```powershell
docker logs --tail 100 mp4-dashboard-api
docker compose -f docker-compose.yml stop mp4-dashboard
```

Ne pas arrÃªter ou supprimer le rÃ©seau externe : il est partagÃ© avec MP3.
