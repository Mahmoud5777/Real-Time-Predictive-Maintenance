$ErrorActionPreference='Stop'
$Root=(Get-Location).Path
$Lot4=Join-Path $Root 'Lot4_LAN_Integration'
$MP2=Join-Path $Root 'Real-Time-Predictive-Maintenance'
$CentralEnv=Join-Path $Lot4 'central\.env'
$FogEnv=Join-Path $Lot4 'fog-node\.env.fog'
if(!(Test-Path $CentralEnv)){Copy-Item (Join-Path $Lot4 'central\.env.central.example') $CentralEnv}
if(!(Test-Path $FogEnv)){Copy-Item (Join-Path $Lot4 'fog-node\.env.fog.example') $FogEnv}
Write-Host 'Checking central LAN overlay...' -ForegroundColor Cyan
docker compose --env-file $CentralEnv -f (Join-Path $MP2 'docker-compose.yml') -f (Join-Path $Lot4 'central\docker-compose.lan-central.yml') config --quiet
if($LASTEXITCODE -ne 0){throw 'Central compose config invalid.'}
Write-Host 'Checking central Scheduler local-simulation override...' -ForegroundColor Cyan
docker compose --env-file $CentralEnv -f (Join-Path $MP2 'docker-compose.yml') -f (Join-Path $Lot4 'central\docker-compose.lan-central.yml') -f (Join-Path $Lot4 'central\docker-compose.central-local-sim.yml') config --quiet
if($LASTEXITCODE -ne 0){throw 'Central local-simulation compose config invalid.'}
Write-Host 'Checking local simulation compose...' -ForegroundColor Cyan
docker compose -f (Join-Path $Lot4 'fog-node\docker-compose.fog-local-sim.yml') config --quiet
if($LASTEXITCODE -ne 0){throw 'Local Fog simulation compose invalid.'}
foreach($profile in @('fog-a','fog-b','fog-c')){
  Write-Host "Checking remote profile $profile..." -ForegroundColor Cyan
  docker compose --env-file $FogEnv -f (Join-Path $Lot4 'fog-node\docker-compose.fog-remote.yml') --profile $profile config --quiet
  if($LASTEXITCODE -ne 0){throw "Remote profile $profile invalid."}
}
Write-Host 'LOT4 V3 CONFIG VALIDATION: PASS (no containers started)' -ForegroundColor Green
