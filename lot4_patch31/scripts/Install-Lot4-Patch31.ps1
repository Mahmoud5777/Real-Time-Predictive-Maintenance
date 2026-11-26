$ErrorActionPreference='Stop'
$Root=(Get-Location).Path
$Target=Join-Path $Root 'Lot4_LAN_Integration\central\docker-compose.lan-central.yml'
if(!(Test-Path $Target)){throw "Target not found: $Target. Run from repository root and apply Lot4 v3 first."}
Copy-Item (Join-Path $PSScriptRoot '..\central\docker-compose.lan-central.yml') $Target -Force
Write-Host 'Lot4 patch 3.1 installed: scheduler local dependencies cleared.' -ForegroundColor Green
