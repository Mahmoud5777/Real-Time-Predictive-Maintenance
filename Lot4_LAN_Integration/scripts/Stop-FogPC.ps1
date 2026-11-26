param([Parameter(Mandatory=$true)][ValidateSet('fog-a','fog-b','fog-c')][string]$Node)
$ErrorActionPreference = 'Stop'
$Root = (Get-Location).Path
$Compose = Join-Path $Root 'Lot4_LAN_Integration\fog-node\docker-compose.fog-remote.yml'
$EnvFile = Join-Path $Root '.env'
if (!(Test-Path $Compose)) { throw "Compose file not found. Run from repository root." }
docker compose -f $Compose --env-file $EnvFile --profile $Node down
if ($LASTEXITCODE -ne 0) { throw "Docker Compose stop failed for $Node" }
