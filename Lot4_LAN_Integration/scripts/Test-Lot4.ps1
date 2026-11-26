[CmdletBinding()]
param([switch]$SkipRuntime,[string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path)
$ErrorActionPreference = 'Stop'
$powershellExe = (Get-Process -Id $PID).Path
& $powershellExe -NoProfile -File (Join-Path $PSScriptRoot 'Validate-Lot4-Config.ps1') -RepositoryRoot $RepositoryRoot
if ($LASTEXITCODE -ne 0) { throw 'La validation statique/configuration a echoue.' }
if ($SkipRuntime) { Write-Host 'Controles runtime ignores a la demande.'; exit 0 }
$failed = New-Object System.Collections.Generic.List[string]
$expectedContainers = @('lot4-grafana','lot4-prometheus','lot4-blackbox-exporter','mp2-scheduler-lan-sim','lot4-sim-mosquitto','mp2-fog-a-lan-sim','mp2-fog-b-lan-sim','mp2-fog-c-lan-sim')
foreach ($container in $expectedContainers) {
  $state = & docker inspect --format '{{.State.Status}}' $container 2>$null
  if ($LASTEXITCODE -ne 0 -or $state -ne 'running') { Write-Host "CONTENEUR FAIL: $container ($state)" -ForegroundColor Red; $failed.Add("container:$container") }
  else { Write-Host "CONTENEUR PASS: $container" -ForegroundColor Green }
}
$healthUrls = @('http://localhost:8110/health','http://localhost:8201/health','http://localhost:8202/health','http://localhost:8203/health','http://localhost:9090/-/healthy','http://localhost:9115/-/healthy','http://localhost:3002/api/health')
foreach ($url in $healthUrls) {
  try { $null = Invoke-RestMethod -Uri $url -TimeoutSec 5; Write-Host "HTTP PASS: $url" -ForegroundColor Green }
  catch { Write-Host "HTTP FAIL: $url - $($_.Exception.Message)" -ForegroundColor Red; $failed.Add("http:$url") }
}
$targetResponse = Invoke-RestMethod -Uri 'http://localhost:9090/api/v1/targets' -TimeoutSec 5
$targets = @($targetResponse.data.activeTargets)
foreach ($job in @('prometheus','lot4-scheduler','lot4-fog-nodes','lot4-health','lot4-mqtt','mp2-scheduler','mp2-fog-nodes','mp2-health','mp2-mqtt')) {
  $jobTargets = @($targets | Where-Object { $_.labels.job -eq $job })
  if (-not $jobTargets.Count) { Write-Host "TARGET FAIL: aucun target pour $job" -ForegroundColor Red; $failed.Add("target-missing:$job"); continue }
  $down = @($jobTargets | Where-Object health -ne 'up')
  if ($down.Count) { Write-Host "TARGET FAIL: $job ($($down.Count)/$($jobTargets.Count) indisponible(s))" -ForegroundColor Red; $failed.Add("target-down:$job") }
  else { Write-Host "TARGET PASS: $job ($($jobTargets.Count))" -ForegroundColor Green }
}
$dashboardPath = Join-Path $RepositoryRoot 'Lot4_LAN_Integration\monitoring\grafana\dashboards\lot4-overview.json'
$dashboard = Get-Content -LiteralPath $dashboardPath -Raw | ConvertFrom-Json
foreach ($panel in $dashboard.panels) {
  $escaped = [uri]::EscapeDataString($panel.targets[0].expr)
  try {
    $query = Invoke-RestMethod -Uri "http://localhost:9090/api/v1/query?query=$escaped" -TimeoutSec 5
    if ($query.status -ne 'success') { throw 'Prometheus a refuse la requete.' }
    $seriesCount = $query.data.result.Count
    if ($panel.id -le 6 -and -not $seriesCount) { throw "Aucune serie de supervision pour le panneau $($panel.id)." }
    if (-not $seriesCount) { Write-Host "PROMQL PASS (aucun evenement observe): panneau $($panel.id) - $($panel.title)" -ForegroundColor Yellow }
    else { Write-Host "PROMQL PASS: panneau $($panel.id) - $($panel.title) ($seriesCount serie(s))" -ForegroundColor Green }
  } catch { Write-Host "PROMQL FAIL: panneau $($panel.id) - $($_.Exception.Message)" -ForegroundColor Red; $failed.Add("promql:$($panel.id)") }
}
$monitoringEnv = Join-Path $RepositoryRoot 'Lot4_LAN_Integration\monitoring\.env'
if (-not (Test-Path -LiteralPath $monitoringEnv)) { $failed.Add('grafana-env-missing') }
else {
  $settings = @{}
  foreach ($line in Get-Content -LiteralPath $monitoringEnv) { if ($line -match '^\s*([A-Z_]+)\s*=\s*(.*?)\s*$') { $settings[$matches[1]] = $matches[2] } }
  if (-not $settings['GRAFANA_ADMIN_USER'] -or -not $settings['GRAFANA_ADMIN_PASSWORD']) { $failed.Add('grafana-credentials-missing') }
  else {
    $auth = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("$($settings['GRAFANA_ADMIN_USER']):$($settings['GRAFANA_ADMIN_PASSWORD'])"))
    $headers = @{Authorization="Basic $auth"}
    try {
      $loaded = Invoke-RestMethod -Uri 'http://localhost:3002/api/dashboards/uid/lot4-overview' -Headers $headers -TimeoutSec 5
      $datasources = Invoke-RestMethod -Uri 'http://localhost:3002/api/datasources' -Headers $headers -TimeoutSec 5
      $promDatasource = @($datasources | Where-Object { $_.uid -eq 'prometheus' -and $_.url -eq 'http://lot4-prometheus:9090' })
      $proxyResult = Invoke-RestMethod -Uri 'http://localhost:3002/api/datasources/proxy/uid/prometheus/api/v1/query?query=up' -Headers $headers -TimeoutSec 10
      $expected = Get-Content -LiteralPath $dashboardPath -Raw | ConvertFrom-Json
      if ($loaded.dashboard.panels.Count -ne 10 -or $promDatasource.Count -ne 1 -or $proxyResult.status -ne 'success' -or -not $proxyResult.data.result.Count) { throw 'Le dashboard ou la datasource provisionnee ne correspondent pas.' }
      foreach ($panel in $expected.panels) {
        $actual = @($loaded.dashboard.panels | Where-Object id -eq $panel.id | Select-Object -First 1)
        if (-not $actual.Count -or $actual[0].targets[0].expr -ne $panel.targets[0].expr) { throw "La requete du panneau $($panel.id) ne correspond pas au fichier provisionne." }
      }
      Write-Host "Grafana API PASS: $($loaded.dashboard.uid), 10 panneaux synchronises, datasource Prometheus joignable (version $($loaded.dashboard.version))" -ForegroundColor Green
    } catch { Write-Host 'Grafana API FAIL: dashboard ou datasource non charge/synchronise.' -ForegroundColor Red; $failed.Add('grafana-api') }
  }
}
if ($failed.Count) { Write-Error "Validation runtime Lot 4 en echec: $($failed -join ', ')"; exit 1 }
Write-Host 'VALIDATION LOT 4 (configuration + runtime local): PASS' -ForegroundColor Green
