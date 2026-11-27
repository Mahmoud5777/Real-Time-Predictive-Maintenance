[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][ValidateSet('central','fog-a','fog-b','fog-c')][string]$Role,
  [string]$ConfigPath = (Join-Path $PSScriptRoot 'config\deployment.json')
)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'Validate-DeploymentJson.ps1') -ConfigPath $ConfigPath
$cfg = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$outDir = Join-Path $PSScriptRoot 'config\generated'
New-Item -ItemType Directory -Path $outDir -Force | Out-Null
$target = Join-Path $outDir ".env.$Role"
if (Test-Path -LiteralPath $target) {
  $backup = "$target.bak-$(Get-Date -Format 'yyyyMMdd-HHmmss-fff')"
  Copy-Item -LiteralPath $target -Destination $backup
  Write-Host "Sauvegarde créée: $backup" -ForegroundColor Yellow
}
$prefix = [string]$cfg.deployment.dockerComposeProjectPrefix
$lines = @(
  "COMPOSE_PROJECT_NAME=$prefix-physical-$($Role.Replace('-',''))",
  "CENTRAL_IP=$($cfg.centralIp)",
  "MQTT_PORT=$($cfg.network.mqttPort)",
  "CENTRAL_LAN_IP=$($cfg.centralIp)"
)
if ($Role -eq 'central') {
  $lines += "FOG_A_IP=$($cfg.fogAIp)", "FOG_B_IP=$($cfg.fogBIp)", "FOG_C_IP=$($cfg.fogCIp)", "FOG_A_PORT=$($cfg.fogPorts.'fog-a')", "FOG_B_PORT=$($cfg.fogPorts.'fog-b')", "FOG_C_PORT=$($cfg.fogPorts.'fog-c')", "SCHEDULER_PORT=$($cfg.schedulerPort)", "PROMETHEUS_PORT=$($cfg.monitoring.prometheusPort)", "GRAFANA_PORT=$($cfg.monitoring.grafanaPort)", "BLACKBOX_PORT=$($cfg.monitoring.blackboxPort)"
} else {
  $portKey = $Role
  $envKey = $Role.Replace('-','_').ToUpperInvariant() + '_PORT'
  $lines += "$envKey=$($cfg.fogPorts.$portKey)"
}
Set-Content -LiteralPath $target -Value $lines -Encoding ascii
if ($Role -eq 'central') {
  $template = Join-Path (Split-Path $PSScriptRoot -Parent) 'Lot4_LAN_Integration\monitoring\prometheus-lan.template.yml'
  $promPath = Join-Path $outDir 'prometheus.yml'
  $prom = Get-Content -LiteralPath $template -Raw
  $replacements = @{
    '${CENTRAL_LAN_IP}'=[string]$cfg.centralIp; '${FOG_A_IP}'=[string]$cfg.fogAIp; '${FOG_B_IP}'=[string]$cfg.fogBIp; '${FOG_C_IP}'=[string]$cfg.fogCIp;
    ':8100'=[string]":$($cfg.schedulerPort)"; ':8101'=[string]":$($cfg.fogPorts.'fog-a')"; ':8102'=[string]":$($cfg.fogPorts.'fog-b')"; ':8103'=[string]":$($cfg.fogPorts.'fog-c')"; ':1883'=[string]":$($cfg.network.mqttPort)"
  }
  foreach ($key in $replacements.Keys) { $prom = $prom.Replace($key,$replacements[$key]) }
  if (Test-Path -LiteralPath $promPath) {
    $promBackup = "$promPath.bak-$(Get-Date -Format 'yyyyMMdd-HHmmss-fff')"
    Copy-Item -LiteralPath $promPath -Destination $promBackup
    Write-Host "Sauvegarde créée: $promBackup" -ForegroundColor Yellow
  }
  Set-Content -LiteralPath $promPath -Value $prom -Encoding utf8
}
Write-Host "Configuration préparée pour $Role : $target" -ForegroundColor Green
