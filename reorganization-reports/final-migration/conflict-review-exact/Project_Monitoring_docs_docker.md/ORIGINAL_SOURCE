# Docker et déploiement — Dashboard MP4

MP4 est servi exclusivement par le conteneur API-only `mp4-dashboard-api` sur le port
`3001`. Le frontend utilise les routes réelles de l'API MP3; aucun mode Mock ni jeu de
données statiques n'est inclus dans le déploiement.

## Configuration

- `docker-compose.yml` inclut `docker/docker-compose.api.yml`, afin que la commande
  Compose à la racine ne lance que le Dashboard API-only.
- `docker/docker-compose.api.yml` construit l'image `mp4-dashboard:api` et publie le
  port `3001`.
- `frontend/Dockerfile` compile l'application avec Vite puis la sert avec Nginx.
- `docker/nginx/nginx.api.conf` est le proxy canonique vers `api:8000` sur le réseau
  externe `mp3-cloud_default`.
- `frontend/nginx.api.conf` est la configuration Nginx intégrée par défaut à l'image;
  elle doit rester synchronisée avec la configuration canonique.
- `frontend/nginx.conf.bak` est une sauvegarde conservée et n'est pas utilisée par le
  build API-only.

Le réseau externe `mp3-cloud_default` et le service API MP3 doivent déjà exister. Le
Compose MP4 ne démarre et ne modifie aucun service MP3.

## Validation et déploiement

Depuis `Project_Monitoring` :

```powershell
docker compose -f docker-compose.yml config --quiet
docker compose -f docker/docker-compose.api.yml config --quiet
docker compose -f docker-compose.yml up -d --build
docker compose -f docker-compose.yml ps
docker inspect mp4-dashboard-api --format '{{.State.Status}} {{.State.Health.Status}}'
```

Le conteneur attendu est `mp4-dashboard-api`, exposé sur `http://localhost:3001`.

## Vérification HTTP

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

Les routes API sont relayées par Nginx vers MP3. Les données affichées dans MP4
proviennent des réponses API; une erreur ou une réponse vide n'est pas remplacée par
des données de démonstration.

## Journaux et arrêt ciblé

```powershell
docker logs --tail 100 mp4-dashboard-api
docker compose -f docker-compose.yml stop mp4-dashboard
```

Ne pas arrêter ou supprimer le réseau externe : il est partagé avec MP3.
