[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][ValidateSet('central','fog-a','fog-b','fog-c')][string]$Role,
  [string]$ConfigPath = (Join-Path $PSScriptRoot 'config\deployment.json'),
  [switch]$GenerateEnv
)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'Validate-DeploymentJson.ps1') -ConfigPath $ConfigPath
$cfg = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
if (-not $cfg.addressesConfirmed) { throw 'Les adresses deployment.json sont des exemples/non confirmées. Confirmer les quatre IPv4 avant tout déploiement.' }
$expectedIP = switch ($Role) { central {$cfg.centralIp} 'fog-a' {$cfg.fogAIp} 'fog-b' {$cfg.fogBIp} 'fog-c' {$cfg.fogCIp} }
$localIPs = @(Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } | Select-Object -ExpandProperty IPAddress)
if ($localIPs -notcontains [string]$expectedIP) { throw "Ce PC ne possède pas l'adresse attendue pour $Role ($expectedIP). Exécution locale uniquement." }
if ($GenerateEnv) { & (Join-Path $PSScriptRoot 'Set-Lot4ConfigFromJson.ps1') -Role $Role -ConfigPath $ConfigPath }
$envPath = Join-Path $PSScriptRoot "config\generated\.env.$Role"
if (-not (Test-Path -LiteralPath $envPath -PathType Leaf)) { throw "Configuration de rôle absente: $envPath. Relancer avec -GenerateEnv." }
$composeDir = Join-Path $PSScriptRoot 'compose'
$compose = if ($Role -eq 'central') { Join-Path $composeDir 'docker-compose.central.yml' } else { Join-Path $composeDir 'docker-compose.fogs.yml' }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker CLI introuvable.' }
if ($Role -eq 'central') { docker compose --env-file $envPath -f $compose up -d --build }
else { docker compose --env-file $envPath -f $compose --profile $Role up -d --build $Role }
if ($LASTEXITCODE -ne 0) { throw "Échec du déploiement local du rôle $Role." }
