[CmdletBinding()]
param([string]$RepositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..')).Path)

$ErrorActionPreference = 'Stop'
$source = Join-Path $RepositoryRoot 'deployment\lot4\core\monitoring\grafana\dashboards\lot4-overview.json'
$provisioned = Join-Path $RepositoryRoot 'deployment\lot4\core\monitoring\grafana\provisioning\dashboards\lot4-overview.json'
if (-not (Test-Path -LiteralPath $source)) { throw "Dashboard source introuvable: $source" }

$dashboard = Get-Content -LiteralPath $source -Raw | ConvertFrom-Json
$definitions = @{
  1 = @{ Title='Disponibilite des services'; Unit='short'; Expr='up{job=~"lot4-scheduler|lot4-fog-nodes|mp2-scheduler|mp2-fog-nodes"}'; Legend='{{job}} / {{instance}}'; Description='1 = cible de metriques joignable; 0 = cible indisponible.' }
  2 = @{ Title='Health checks HTTP'; Unit='short'; Expr='probe_success{job=~"lot4-health|mp2-health"}'; Legend='{{deployment}} / {{service}} / {{fog_id}}'; Description='Sonde Blackbox GET /health. 1 = HTTP 200; 0 = echec.' }
  3 = @{ Title='Disponibilite MQTT (TCP)'; Unit='short'; Expr='probe_success{job=~"lot4-mqtt|mp2-mqtt"}'; Legend='{{deployment}} / {{instance}}'; Description='Sonde TCP sur le port MQTT; verifie accessibilite reseau, pas la publication metier.' }
  4 = @{ Title='Utilisation CPU des Fog nodes'; Unit='percent'; Expr='fog_cpu_usage_percent{job=~"lot4-fog-nodes|mp2-fog-nodes"}'; Legend='{{fog_id}} ({{job}})'; Description='Dernier snapshot du service. Absence de serie signifie qu aucun snapshot n est disponible.' }
  5 = @{ Title='Utilisation RAM des Fog nodes'; Unit='percent'; Expr='fog_ram_usage_percent{job=~"lot4-fog-nodes|mp2-fog-nodes"}'; Legend='{{fog_id}} ({{job}})'; Description='Dernier snapshot du service. Absence de serie signifie qu aucun snapshot n est disponible.' }
  6 = @{ Title='Taille des files d attente'; Unit='short'; Expr='fog_queue_size{job=~"lot4-fog-nodes|mp2-fog-nodes"}'; Legend='{{fog_id}} ({{job}})'; Description='Nombre de taches en attente au dernier snapshot. 0 est une file vide; aucune donnee signifie aucun snapshot.' }
  7 = @{ Title='Taches terminees (debit)'; Unit='ops'; Expr='sum by (job, fog_id) (rate(fog_tasks_completed_total{job=~"lot4-scheduler|mp2-scheduler"}[5m]))'; Legend='{{job}} / {{fog_id}}'; Description='Taux de completions par seconde sur 5 minutes. Aucune serie signifie aucun evenement recent.' }
  8 = @{ Title='Latence moyenne de dispatch'; Unit='s'; Expr='sum by (job) (rate(scheduler_dispatch_latency_seconds_sum{job=~"lot4-scheduler|mp2-scheduler"}[5m])) / (sum by (job) (rate(scheduler_dispatch_latency_seconds_count{job=~"lot4-scheduler|mp2-scheduler"}[5m])) > 0)'; Legend='{{job}}'; Description='Moyenne sur 5 minutes avec _sum/_count. Vide si aucun dispatch n a ete observe.' }
  9 = @{ Title='RTO moyen de recuperation'; Unit='s'; Expr='sum by (job, failed_fog) (rate(fog_recovery_rto_seconds_sum{job=~"lot4-scheduler|mp2-scheduler"}[5m])) / (sum by (job, failed_fog) (rate(fog_recovery_rto_seconds_count{job=~"lot4-scheduler|mp2-scheduler"}[5m])) > 0)'; Legend='{{job}} / {{failed_fog}}'; Description='Moyenne histogramme sur 5 minutes. Vide si aucune recuperation n a eu lieu.' }
  10 = @{ Title='Migrations observees (derniere heure)'; Unit='short'; Expr='sum by (job, source, destination, kind) (increase(fog_migrations_total{job=~"lot4-scheduler|mp2-scheduler"}[1h]))'; Legend='{{job}} / {{source}} -> {{destination}}'; Description='Augmentation du compteur sur une heure. Vide si aucune migration n a ete enregistree.' }
}

foreach ($panel in $dashboard.panels) {
  $definition = $definitions[[int]$panel.id]
  if ($null -eq $definition) { continue }
  $panel.title = $definition.Title
  $panel | Add-Member -NotePropertyName description -NotePropertyValue $definition.Description -Force
  $panel.fieldConfig.defaults.unit = $definition.Unit
  $panel.targets[0].expr = $definition.Expr
  $panel.targets[0].legendFormat = $definition.Legend
}
$dashboard.refresh = '15s'
$dashboard.time.from = 'now-1h'
$dashboard.time.to = 'now'
$dashboard | Add-Member -NotePropertyName editable -NotePropertyValue $true -Force
$json = $dashboard | ConvertTo-Json -Depth 100
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($source,$json,$utf8)
[System.IO.File]::WriteAllText($provisioned,$json,$utf8)
Write-Host "Dashboard lot4-overview mis Ã  jour dans les deux fichiers." -ForegroundColor Green
