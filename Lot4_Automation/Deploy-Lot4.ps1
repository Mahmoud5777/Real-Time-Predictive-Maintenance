[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("central","fog-a","fog-b","fog-c")]
    [string]$Role
)
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Bundle = Join-Path $RepoRoot "Lot4_LAN_Integration"
$MP2 = Join-Path $RepoRoot "Real-Time-Predictive-Maintenance"

if ($Role -eq "central") {
    $envFile = Join-Path $Bundle "central\.env"
    $base = Join-Path $MP2 "docker-compose.yml"
    $overlay = Join-Path $Bundle "central\docker-compose.lan-central.yml"
    if (!(Test-Path $envFile)) { throw "Missing central\.env. Run Install-Lot4.ps1 -Role central and configure IPs." }
    if (!(Test-Path $base)) { throw "MP2 docker-compose.yml not found." }
    docker compose --env-file $envFile -f $base -f $overlay config --quiet
    if ($LASTEXITCODE -ne 0) { throw "Central Compose validation failed." }
    docker compose --env-file $envFile -f $base -f $overlay up -d --build mosquitto scheduler
} else {
    $envFile = Join-Path $Bundle "fog-node\.env.fog"
    $compose = Join-Path $Bundle "fog-node\docker-compose.fog-remote.yml"
    if (!(Test-Path $envFile)) { throw "Missing fog-node\.env.fog. Run Install-Lot4.ps1 -Role $Role and configure CENTRAL_LAN_IP." }
    docker compose --env-file $envFile -f $compose --profile $Role config --quiet
    if ($LASTEXITCODE -ne 0) { throw "$Role Compose validation failed." }
    docker compose --env-file $envFile -f $compose --profile $Role up -d --build
}
if ($LASTEXITCODE -ne 0) { throw "Docker Compose deployment failed for $Role." }
Write-Host "$Role deployment command completed." -ForegroundColor Green
