param(
  [Parameter(Mandatory=$true)][ValidateSet('fog-a','fog-b','fog-c')][string]$Node,
  [string]$CentralIP
)
$ErrorActionPreference = 'Stop'
$Root = (Get-Location).Path
$Compose = Join-Path $Root 'Lot4_LAN_Integration\fog-node\docker-compose.fog-remote.yml'
$EnvFile = Join-Path $Root '.env'
if (!(Test-Path $Compose)) { throw "Compose file not found: $Compose. Run from repository root." }
if (!(Test-Path $EnvFile)) { throw "Create root .env from Lot4_LAN_Integration\fog-node\.env.fog.example first." }
if ($CentralIP) { (Get-Content $EnvFile) -replace '^CENTRAL_LAN_IP=.*',"CENTRAL_LAN_IP=$CentralIP" | Set-Content $EnvFile }
docker compose -f $Compose --env-file $EnvFile --profile $Node config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose configuration validation failed.' }
docker compose -f $Compose --env-file $EnvFile --profile $Node up -d --build
if ($LASTEXITCODE -ne 0) { throw "Docker Compose failed for $Node" }
