$ErrorActionPreference = 'Stop'
$Root = (Get-Location).Path
$Patch = Join-Path $PSScriptRoot '..'
$Target = Join-Path $Root 'Lot4_LAN_Integration'
if (!(Test-Path (Join-Path $Root 'Real-Time-Predictive-Maintenance\docker-compose.yml'))) { throw 'Run this script from the repository root.' }
$files = @(
  @{Source='central\docker-compose.lan-central.yml';Dest='central\docker-compose.lan-central.yml'},
  @{Source='central\.env.central.example';Dest='central\.env.central.example'},
  @{Source='central\docker-compose.central-local-sim.yml';Dest='central\docker-compose.central-local-sim.yml'},
  @{Source='fog-node\docker-compose.fog-remote.yml';Dest='fog-node\docker-compose.fog-remote.yml'},
  @{Source='fog-node\docker-compose.fog-local-sim.yml';Dest='fog-node\docker-compose.fog-local-sim.yml'},
  @{Source='fog-node\.env.fog.example';Dest='fog-node\.env.fog.example'}
)
foreach($f in $files){
  $src=Join-Path $Patch $f.Source; $dst=Join-Path $Target $f.Dest
  if(!(Test-Path $src)){throw "Patch source missing: $src"}
  $parent=Split-Path $dst -Parent; New-Item -ItemType Directory -Force -Path $parent | Out-Null
  Copy-Item $src $dst -Force
}
Write-Host 'Lot4 v3 patch installed. MP2 base compose was not modified.' -ForegroundColor Green
