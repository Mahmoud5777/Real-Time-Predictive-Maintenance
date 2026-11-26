param([ValidateSet("fog-a","fog-b","fog-c")][string]$Role)
$Root = Split-Path $PSScriptRoot -Parent
$Compose = "$Root\fog-node\docker-compose.fog-remote.yml"
$EnvFile = "$Root\fog-node\.env.fog"

if (!(Test-Path $EnvFile)) { throw "Missing .env.fog. Copy .env.fog.example and configure CENTRAL_LAN_IP." }
docker compose --env-file $EnvFile -f $Compose --profile $Role up -d --build
if ($LASTEXITCODE -ne 0) { throw "Fog startup failed." }

& "$PSScriptRoot\Configure-Firewall.ps1" $Role
Write-Host "$Role started." -ForegroundColor Green

