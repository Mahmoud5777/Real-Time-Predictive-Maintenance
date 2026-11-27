[CmdletBinding()]
param([string]$ConfigPath = (Join-Path $PSScriptRoot 'config\deployment.json'))
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Write-Host '[1/4] Validation du JSON et des dépendances' -ForegroundColor Cyan
& (Join-Path $PSScriptRoot 'Validate-DeploymentJson.ps1') -ConfigPath $ConfigPath
Write-Host '[2/4] Analyse syntaxique PowerShell' -ForegroundColor Cyan
$scripts = @('Validate-DeploymentJson.ps1','Set-Lot4ConfigFromJson.ps1','Deploy-FromJson.ps1','Test-DeploymentFromJson.ps1','Test-Lot4Preparation.ps1')
foreach ($script in $scripts) {
  $path = Join-Path $PSScriptRoot $script
  $tokens=$null; $errors=$null
  [System.Management.Automation.Language.Parser]::ParseFile($path,[ref]$tokens,[ref]$errors) | Out-Null
  if ($errors.Count) { throw "Syntaxe PowerShell invalide dans $script : $($errors -join '; ')" }
}
Write-Host '[3/4] Vérification des Compose et chemins de build' -ForegroundColor Cyan
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Docker CLI requis pour docker compose config.' }
$cfg = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$envNames = @('COMPOSE_PROJECT_NAME','CENTRAL_IP','MQTT_PORT','CENTRAL_LAN_IP','GRAFANA_ADMIN_PASSWORD','FOG_A_IP','FOG_B_IP','FOG_C_IP','SCHEDULER_PORT','PROMETHEUS_PORT','GRAFANA_PORT','BLACKBOX_PORT','FOG_A_PORT','FOG_B_PORT','FOG_C_PORT')
$oldEnv=@{}
foreach ($n in $envNames) { $oldEnv[$n]=[Environment]::GetEnvironmentVariable($n,'Process') }
try {
  $env:COMPOSE_PROJECT_NAME="$($cfg.deployment.dockerComposeProjectPrefix)-validation"
  $env:CENTRAL_IP=[string]$cfg.centralIp; $env:CENTRAL_LAN_IP=[string]$cfg.centralIp; $env:MQTT_PORT=[string]$cfg.network.mqttPort
  $env:FOG_A_IP=[string]$cfg.fogAIp; $env:FOG_B_IP=[string]$cfg.fogBIp; $env:FOG_C_IP=[string]$cfg.fogCIp
  $env:SCHEDULER_PORT=[string]$cfg.schedulerPort; $env:PROMETHEUS_PORT=[string]$cfg.monitoring.prometheusPort; $env:GRAFANA_PORT=[string]$cfg.monitoring.grafanaPort; $env:BLACKBOX_PORT=[string]$cfg.monitoring.blackboxPort
  $env:FOG_A_PORT=[string]$cfg.fogPorts.'fog-a'; $env:FOG_B_PORT=[string]$cfg.fogPorts.'fog-b'; $env:FOG_C_PORT=[string]$cfg.fogPorts.'fog-c'
  $env:GRAFANA_ADMIN_PASSWORD='validation-only'
  $composeDir=Join-Path $PSScriptRoot 'compose'
  $central=Join-Path $composeDir 'docker-compose.central.yml'; $fogs=Join-Path $composeDir 'docker-compose.fogs.yml'
  foreach ($path in @($central,$fogs)) { if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Compose absent: $path" } }
  docker compose -f $central config --quiet
  if ($LASTEXITCODE -ne 0) { throw 'docker compose config a échoué pour central.' }
  foreach ($role in @('fog-a','fog-b','fog-c')) {
    docker compose -f $fogs --profile $role config --quiet
    if ($LASTEXITCODE -ne 0) { throw "docker compose config a échoué pour $role." }
  }
} finally {
  foreach ($n in $envNames) { [Environment]::SetEnvironmentVariable($n,$oldEnv[$n],'Process') }
}
Write-Host '[4/4] Préparation Lot 4 valide. Aucun conteneur démarré.' -ForegroundColor Green
