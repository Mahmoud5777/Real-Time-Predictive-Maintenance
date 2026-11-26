[CmdletBinding()]
param([string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path)
$ErrorActionPreference = 'Stop'
$bundle = Join-Path $RepositoryRoot 'Lot4_LAN_Integration'
$failures = New-Object System.Collections.Generic.List[string]
$required = @(
  'README_LOT4_LAN.md','central\docker-compose.lan-central.yml','central\docker-compose.central-local-sim.yml',
  'central\docker-compose.scheduler-lan-sim.yml','central\.env.central.example','fog-node\docker-compose.fog-remote.yml',
  'fog-node\docker-compose.fog-local-sim.yml','fog-node\.env.fog.example','monitoring\prometheus-local.yml',
  'monitoring\prometheus-lan.template.yml','monitoring\prometheus-lan.yml','monitoring\alert_rules.yml',
  'monitoring\blackbox.yml','monitoring\docker-compose.monitoring.yml','monitoring\docker-compose.monitoring-local.yml',
  'monitoring\.env.example','monitoring\grafana\dashboards\lot4-overview.json',
  'monitoring\grafana\provisioning\dashboards\lot4-overview.json',
  'monitoring\grafana\provisioning\datasources\prometheus.yml'
)
foreach ($relative in $required) {
  if (-not (Test-Path -LiteralPath (Join-Path $bundle $relative))) { $failures.Add("Fichier requis absent: $relative") }
}
if ($failures.Count) { $failures | ForEach-Object { Write-Error $_ }; exit 2 }

$parserErrors = $null
$scriptsToParse = @(Get-ChildItem -LiteralPath (Join-Path $bundle 'scripts') -Filter '*.ps1' -File) + @(Get-ChildItem -LiteralPath (Join-Path $bundle 'deployment') -Filter '*.ps1' -File)
foreach ($script in $scriptsToParse) {
  $parserTokens = $null
  $parserErrors = $null
  [void][System.Management.Automation.Language.Parser]::ParseFile($script.FullName,[ref]$parserTokens,[ref]$parserErrors)
  if ($parserErrors.Count) {
    foreach ($parseError in $parserErrors) { $failures.Add("PowerShell $($script.Name): $($parseError.Message)") }
    $parserErrors = $null
  }
}
foreach ($dashboardPath in @(
  (Join-Path $bundle 'monitoring\grafana\dashboards\lot4-overview.json'),
  (Join-Path $bundle 'monitoring\grafana\provisioning\dashboards\lot4-overview.json')
)) {
  try {
    $dashboard = Get-Content -LiteralPath $dashboardPath -Raw | ConvertFrom-Json
    if ($dashboard.uid -ne 'lot4-overview' -or $dashboard.panels.Count -ne 10) { $failures.Add("Dashboard invalide ou incomplet: $dashboardPath") }
  } catch { $failures.Add("JSON dashboard invalide: $dashboardPath - $($_.Exception.Message)") }
}
if ((Get-Content (Join-Path $bundle 'monitoring\grafana\dashboards\lot4-overview.json') -Raw) -ne (Get-Content (Join-Path $bundle 'monitoring\grafana\provisioning\dashboards\lot4-overview.json') -Raw)) {
  $failures.Add('Les deux copies du dashboard Grafana divergent.')
}
$exampleText = Get-Content (Join-Path $bundle 'monitoring\.env.example') -Raw
$monitoringCompose = Get-Content (Join-Path $bundle 'monitoring\docker-compose.monitoring.yml') -Raw
if ($exampleText -match '(?im)^GRAFANA_ADMIN_PASSWORD\s*=\s*(admin|password|changeme)\s*$' -or $monitoringCompose -match '(?m)^\s*GF_SECURITY_ADMIN_PASSWORD:\s*(?!\$\{)\S') {
  $failures.Add('Un mot de passe par defaut ou en clair apparait dans la configuration Grafana.')
}
if ($failures.Count) { $failures | ForEach-Object { Write-Error $_ }; exit 2 }

$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker) { Write-Error 'Docker CLI introuvable; validation des fichiers uniquement.'; exit 3 }
function Invoke-ComposeValidation([string[]]$ComposeArgs,[string]$Name) {
  Write-Host "Compose: $Name"
  & docker compose @ComposeArgs config --quiet
  if ($LASTEXITCODE -ne 0) { $failures.Add("docker compose config a echoue: $Name") }
}
$base = Join-Path $RepositoryRoot 'Real-Time-Predictive-Maintenance\docker-compose.yml'
$centralEnv = Join-Path $bundle 'central\.env.central.example'
$fogEnv = Join-Path $bundle 'fog-node\.env.fog.example'
$monitoringEnv = Join-Path $bundle 'monitoring\.env.example'
Invoke-ComposeValidation @('--env-file',$centralEnv,'-f',$base,'-f',(Join-Path $bundle 'central\docker-compose.lan-central.yml')) 'central LAN + MP2'
Invoke-ComposeValidation @('-f',$base,'-f',(Join-Path $bundle 'central\docker-compose.central-local-sim.yml')) 'central local simulation overlay + MP2'
Invoke-ComposeValidation @('-f',(Join-Path $bundle 'central\docker-compose.scheduler-lan-sim.yml')) 'scheduler local simulation'
foreach ($node in @('fog-a','fog-b','fog-c')) {
  Invoke-ComposeValidation @('--env-file',$fogEnv,'-f',(Join-Path $bundle 'fog-node\docker-compose.fog-remote.yml'),'--profile',$node) "Fog distant $node"
}
Invoke-ComposeValidation @('-f',(Join-Path $bundle 'fog-node\docker-compose.fog-local-sim.yml')) 'Fog local simulation'
Invoke-ComposeValidation @('--env-file',$monitoringEnv,'-f',(Join-Path $bundle 'monitoring\docker-compose.monitoring.yml'),'-f',(Join-Path $bundle 'monitoring\docker-compose.monitoring-local.yml')) 'monitoring local'
$promContainer = & docker ps --filter 'name=^lot4-prometheus$' --format '{{.Names}}'
if ($LASTEXITCODE -eq 0 -and $promContainer -eq 'lot4-prometheus') {
  & docker exec lot4-prometheus promtool check config /etc/prometheus/prometheus-local.yml
  if ($LASTEXITCODE -ne 0) { $failures.Add('promtool check config local a echoue.') }
  & docker exec lot4-prometheus promtool check config /etc/prometheus/prometheus-lan.yml
  if ($LASTEXITCODE -ne 0) { $failures.Add('promtool check config LAN a echoue.') }
  & docker exec lot4-prometheus promtool check rules /etc/prometheus/alert_rules.yml
  if ($LASTEXITCODE -ne 0) { $failures.Add('promtool check rules a echoue.') }
} else { Write-Warning 'Prometheus Lot 4 absent: controle promtool runtime ignore.' }
if ($failures.Count) { $failures | ForEach-Object { Write-Error $_ }; exit 1 }
Write-Host 'VALIDATION CONFIGURATION LOT 4: PASS' -ForegroundColor Green
