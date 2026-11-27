$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RepositoryRoot = (Resolve-Path (Join-Path $Root '..')).Path
$Central = Join-Path $Root 'central'
$MP2 = Join-Path $RepositoryRoot 'Real-Time-Predictive-Maintenance'
$Overlay = "$Central\docker-compose.lan-central.yml"
$EnvFile = "$Central\.env"

# Detect MP2 base Compose file
$Candidates = @("docker-compose.yml","docker-compose.yaml","compose.yml","compose.yaml")
$Base = $Candidates | ForEach-Object { Join-Path $MP2 $_ } | Where-Object { Test-Path $_ } | Select-Object -First 1
if (!$Base) { throw "MP2 base Compose file not found in $MP2" }
if (!(Test-Path $EnvFile)) { throw "Central .env missing. Configure it first." }

docker compose --env-file $EnvFile -f $Base -f $Overlay config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Central Compose configuration is invalid.' }
docker compose --env-file $EnvFile -f $Base -f $Overlay up -d --build mosquitto scheduler
if ($LASTEXITCODE -ne 0) { throw "Central startup failed." }

Write-Host "Central services started. Firewall rules were not changed; see README.md." -ForegroundColor Green
