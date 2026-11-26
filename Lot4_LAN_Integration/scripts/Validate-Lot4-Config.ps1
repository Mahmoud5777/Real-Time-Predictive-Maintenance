$ErrorActionPreference = 'Continue'
$Root = (Get-Location).Path
$Bundle = Join-Path $Root 'Lot4_LAN_Integration'
Write-Host '=== LOT 4 CONFIG VALIDATION ===' -ForegroundColor Cyan
if (!(Test-Path $Bundle)) { Write-Error "Bundle folder missing: $Bundle"; exit 2 }
$required = @('README_LOT4_LAN.md','central\docker-compose.lan-central.yml','central\.env.central.example','fog-node\docker-compose.fog-remote.yml','fog-node\.env.fog.example','monitoring\prometheus-lan.template.yml','scripts\Start-FogPC.ps1','scripts\Stop-FogPC.ps1','scripts\Set-Lot4-Firewall.ps1','scripts\Test-Lot4-LAN.ps1','scripts\Render-Prometheus-LAN.ps1')
$missing = @($required | Where-Object { !(Test-Path (Join-Path $Bundle $_)) })
if ($missing.Count) { Write-Host "Missing files: $($missing -join ', ')" -ForegroundColor Red } else { Write-Host 'Bundle file inventory: PASS' -ForegroundColor Green }
$rootCompose = Join-Path $Root 'Real-Time-Predictive-Maintenance\docker-compose.yml'
if (!(Test-Path $rootCompose)) { Write-Host "MP2 Compose not found: $rootCompose" -ForegroundColor Yellow } else { Write-Host 'MP2 Compose found' -ForegroundColor Green }
$docker = Get-Command docker -ErrorAction SilentlyContinue
if (!$docker) { Write-Host 'Docker CLI missing; skip compose config checks' -ForegroundColor Yellow; exit 1 }
$centralEnv = Join-Path $Bundle 'central\.env'
if (!(Test-Path $centralEnv)) { Copy-Item (Join-Path $Bundle 'central\.env.central.example') $centralEnv; Write-Host 'Created central/.env from example; edit IP addresses before LAN deployment.' -ForegroundColor Yellow }
$fogEnv = Join-Path $Root '.env'
if (!(Test-Path $fogEnv)) { Copy-Item (Join-Path $Bundle 'fog-node\.env.fog.example') $fogEnv; Write-Host 'Created root .env from Fog example. Set CENTRAL_LAN_IP before launching Fog.' -ForegroundColor Yellow }
Write-Host '--- Fog Compose syntax check (profiles) ---'
docker compose -f (Join-Path $Bundle 'fog-node\docker-compose.fog-remote.yml') --env-file $fogEnv --profile fog-a config --quiet
$fogA = $LASTEXITCODE
docker compose -f (Join-Path $Bundle 'fog-node\docker-compose.fog-remote.yml') --env-file $fogEnv --profile fog-b config --quiet
$fogB = $LASTEXITCODE
docker compose -f (Join-Path $Bundle 'fog-node\docker-compose.fog-remote.yml') --env-file $fogEnv --profile fog-c config --quiet
$fogC = $LASTEXITCODE
Write-Host "Fog profiles config: A=$fogA B=$fogB C=$fogC (0=PASS)"
Write-Host 'Central overlay requires real IPs in central/.env and should be validated after editing that file.'
if ($fogA -eq 0 -and $fogB -eq 0 -and $fogC -eq 0 -and $missing.Count -eq 0) { Write-Host 'LOCAL CONFIG VALIDATION: PASS' -ForegroundColor Green } else { Write-Host 'LOCAL CONFIG VALIDATION: CHECK FAILURES ABOVE' -ForegroundColor Yellow }
