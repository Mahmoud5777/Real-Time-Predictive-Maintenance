[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][ValidateSet('fog-a','fog-b','fog-c')][string]$Node,
  [string]$CentralIP,
  [string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
)
$ErrorActionPreference = 'Stop'
$compose = Join-Path $RepositoryRoot 'Lot4_LAN_Integration\fog-node\docker-compose.fog-remote.yml'
$envPath = Join-Path $RepositoryRoot 'Lot4_LAN_Integration\fog-node\.env.fog'
$envExample = Join-Path $RepositoryRoot 'Lot4_LAN_Integration\fog-node\.env.fog.example'
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker CLI est introuvable.' }
if (-not (Test-Path -LiteralPath $compose)) { throw "Compose introuvable: $compose" }
if (-not (Test-Path -LiteralPath $envExample)) { throw "Exemple d'environnement introuvable: $envExample" }
if (-not (Test-Path -LiteralPath $envPath)) { $envPath = $envExample }
if ($CentralIP) {
  $parsed = $null
  if (-not [System.Net.IPAddress]::TryParse($CentralIP,[ref]$parsed) -or $parsed.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) { throw 'CentralIP doit etre une adresse IPv4 valide.' }
}
$oldCentralIP = $env:CENTRAL_LAN_IP
try {
  if ($CentralIP) { $env:CENTRAL_LAN_IP = $CentralIP }
  elseif (-not $env:CENTRAL_LAN_IP -and (Get-Content -LiteralPath $envPath -Raw) -notmatch '(?m)^CENTRAL_LAN_IP=\d{1,3}(\.\d{1,3}){3}\s*$') { throw 'Definir CENTRAL_LAN_IP dans .env.fog ou passer -CentralIP.' }
  & docker compose -f $compose --env-file $envPath --profile $Node config --quiet
  if ($LASTEXITCODE -ne 0) { throw 'La configuration Compose Fog est invalide.' }
  & docker compose -f $compose --env-file $envPath --profile $Node up -d --build
  if ($LASTEXITCODE -ne 0) { throw "Echec du demarrage Docker Compose pour $Node." }
  Write-Host "Noeud $Node demarre." -ForegroundColor Green
} finally {
  if ($null -eq $oldCentralIP) { Remove-Item Env:\CENTRAL_LAN_IP -ErrorAction SilentlyContinue } else { $env:CENTRAL_LAN_IP = $oldCentralIP }
}
