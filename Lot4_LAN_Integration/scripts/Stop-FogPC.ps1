[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][ValidateSet('fog-a','fog-b','fog-c')][string]$Node,
  [string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
)
$ErrorActionPreference = 'Stop'
$compose = Join-Path $RepositoryRoot 'Lot4_LAN_Integration\fog-node\docker-compose.fog-remote.yml'
$envPath = Join-Path $RepositoryRoot 'Lot4_LAN_Integration\fog-node\.env.fog'
if (-not (Test-Path -LiteralPath $envPath)) { $envPath = Join-Path $RepositoryRoot 'Lot4_LAN_Integration\fog-node\.env.fog.example' }
if (-not (Test-Path -LiteralPath $compose) -or -not (Test-Path -LiteralPath $envPath)) { throw 'Fichiers Compose ou environnement Fog introuvables.' }
& docker compose -f $compose --env-file $envPath --profile $Node stop
if ($LASTEXITCODE -ne 0) { throw "Arret du seul noeud Lot 4 $Node impossible." }
Write-Host "Noeud $Node arrete. Les autres lots, reseaux et volumes restent intacts." -ForegroundColor Green
