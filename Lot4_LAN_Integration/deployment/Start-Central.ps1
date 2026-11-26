$Root = Split-Path $PSScriptRoot -Parent
$Central = "$Root\central"
$MP2 = (Resolve-Path "$Root\..\Real-Time-Predictive-Maintenance").Path
$Overlay = "$Central\docker-compose.lan-central.yml"
$EnvFile = "$Central\.env"

# Detect MP2 base Compose file
$Candidates = @("docker-compose.yml","docker-compose.yaml","compose.yml","compose.yaml")
$Base = $Candidates | ForEach-Object { Join-Path $MP2 $_ } | Where-Object { Test-Path $_ } | Select-Object -First 1
if (!$Base) { throw "MP2 base Compose file not found in $MP2" }
if (!(Test-Path $EnvFile)) { throw "Central .env missing. Configure it first." }

docker compose --env-file $EnvFile -f $Base -f $Overlay up -d mosquitto scheduler
if ($LASTEXITCODE -ne 0) { throw "Central startup failed." }

& "$PSScriptRoot\Configure-Firewall.ps1" central
Write-Host "Central services started." -ForegroundColor Green
