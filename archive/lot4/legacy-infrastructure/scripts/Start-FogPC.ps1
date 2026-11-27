param([ValidateSet("fog-a","fog-b","fog-c")][string]$Node)
$profile = $Node
docker compose -f fog-node/docker-compose.fog-remote.yml --env-file .env --profile $profile up -d --build
