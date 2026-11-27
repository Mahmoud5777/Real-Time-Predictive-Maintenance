[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker CLI est introuvable.' }
$containers = @(
  'mp2-scheduler-lan-sim','lot4-sim-mosquitto',
  'mp2-fog-a-lan-sim','mp2-fog-b-lan-sim','mp2-fog-c-lan-sim',
  'mp2-fog-a-remote','mp2-fog-b-remote','mp2-fog-c-remote'
)
foreach ($container in $containers) {
  $id = & docker ps -q --filter "name=^${container}$"
  if ($LASTEXITCODE -ne 0) { throw "Impossible de lister les conteneurs Docker pour $container." }
  if (-not $id) { Write-Host "Deja arrete/absent: $container"; continue }
  & docker stop $container
  if ($LASTEXITCODE -ne 0) { throw "Echec de l'arret du conteneur Lot 4 $container." }
  Write-Host "Arrete: $container"
}
Write-Host 'Les services centraux MP2, la supervision partagee, MP3/MP4, les reseaux et volumes restent intacts.' -ForegroundColor Green
