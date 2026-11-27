[CmdletBinding()]
param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$RepoRoot = (Get-Location).Path
$required = @('projects\mp1\simulator','projects\mp2','projects\mp3','projects\mp4','deployment\lot4\automation','deployment\lot4\core')
foreach ($p in $required) { if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot $p) -PathType Container)) { throw "Structure migrée manquante: $p. Lance le script depuis la racine du repository." } }

# Exact textual patches only. Historical archive folders are never scanned.
$patches = [ordered]@{}
function Add-Patch([string]$File, [string]$Old, [string]$New) {
  if (-not $patches.Contains($File)) { $patches[$File] = [System.Collections.Generic.List[object]]::new() }
  $patches[$File].Add([pscustomobject]@{Old=$Old;New=$New})
}

# MP2 -> MP1 and MP3 local repository paths
Add-Patch 'projects\mp2\docker-compose.yml' '../mp1-simulator:/app/mp1-simulator:ro' '../mp1/simulator:/app/mp1-simulator:ro'
Add-Patch 'projects\mp2\fog_nodes\common\mp1_inference.py' '<repository>/Real-Time-Predictive-Maintenance/fog_nodes/common' '<repository>/projects/mp2/fog_nodes/common'
Add-Patch 'projects\mp2\fog_nodes\common\mp1_inference.py' '<repository>/mp1-simulator' '<repository>/projects/mp1/simulator'
Add-Patch 'projects\mp2\fog_nodes\common\mp1_inference.py' '            here.parents[2] / "mp1-simulator",' '            here.parents[2] / "mp1-simulator",  # Docker mount at /app/mp1-simulator'
Add-Patch 'projects\mp2\fog_nodes\common\mp1_inference.py' '            here.parents[3] / "mp1-simulator",' '            here.parents[3] / "mp1" / "simulator",  # migrated local MP1\n            here.parents[4] / "mp1-simulator",  # legacy layout fallback'
Add-Patch 'projects\mp2\tests\test_mp3_adapter.py' 'Path(__file__).resolve().parents[2] / "MP3_Backend_Source" / "mp3-cloud"' 'Path(__file__).resolve().parents[2] / "mp3" / "mp3-cloud"'
Add-Patch 'projects\mp1\industrial-simulation\README.md' 'MP3_Backend_Source/' 'projects/mp3/'

# MP4 workflow: paths now point to projects/mp4
Add-Patch '.github\workflows\mp4-ci.yml' 'Project_Monitoring/frontend' 'projects/mp4/frontend'
Add-Patch '.github\workflows\mp4-ci.yml' 'Project_Monitoring/.github/workflows' 'projects/mp4/.github/workflows'
# MP4 documentation path mentions (active docs only)
foreach ($f in @('projects\mp4\docs\demo-guide.md','projects\mp4\docs\docker.md','projects\mp4\docs\monitoring.md')) { Add-Patch $f 'Project_Monitoring' 'projects/mp4' }

# Lot4 Automation PowerShell: repository root is 3 levels above automation folder
foreach ($f in @('Stop-Lot4.ps1','Deploy-Lot4.ps1','Install-Lot4.ps1','Configure-Monitoring.ps1','Set-Lot4Config.ps1')) {
  $p = "deployment\lot4\automation\$f"
  Add-Patch $p 'Join-Path $PSScriptRoot ".."' 'Join-Path $PSScriptRoot "..\..\.."'
  Add-Patch $p 'Join-Path $RepoRoot "Lot4_LAN_Integration"' 'Join-Path $RepoRoot "deployment\lot4\core"'
  Add-Patch $p 'Join-Path $RepoRoot "Real-Time-Predictive-Maintenance"' 'Join-Path $RepoRoot "projects\mp2"'
  Add-Patch $p 'Lot4_LAN_Integration not found under' 'deployment\lot4\core not found under'
  Add-Patch $p 'Lot4_LAN_Integration\monitoring' 'deployment\lot4\core\monitoring'
}
Add-Patch 'deployment\lot4\automation\Test-Lot4Preparation.ps1' "Join-Path `$PSScriptRoot '..'" "Join-Path `$PSScriptRoot '..\..\..'"
Add-Patch 'deployment\lot4\automation\Validate-DeploymentJson.ps1' "Join-Path `$PSScriptRoot '..'" "Join-Path `$PSScriptRoot '..\..\..'"
Add-Patch 'deployment\lot4\automation\Validate-DeploymentJson.ps1' "'Real-Time-Predictive-Maintenance\Dockerfile','Real-Time-Predictive-Maintenance\mosquitto\mosquitto.conf','Lot4_LAN_Integration\monitoring\prometheus-lan.template.yml','Lot4_LAN_Integration\monitoring\alert_rules.yml','Lot4_LAN_Integration\monitoring\blackbox.yml'" "'projects\mp2\Dockerfile','projects\mp2\mosquitto\mosquitto.conf','deployment\lot4\core\monitoring\prometheus-lan.template.yml','deployment\lot4\core\monitoring\alert_rules.yml','deployment\lot4\core\monitoring\blackbox.yml'"
Add-Patch 'deployment\lot4\automation\Validate-DeploymentJson.ps1' "'mp1-simulator','Lot4_LAN_Integration\monitoring\grafana\provisioning\dashboards','Lot4_LAN_Integration\monitoring\grafana\provisioning\datasources'" "'projects\mp1\simulator','deployment\lot4\core\monitoring\grafana\provisioning\dashboards','deployment\lot4\core\monitoring\grafana\provisioning\datasources'"
Add-Patch 'deployment\lot4\automation\Set-Lot4ConfigFromJson.ps1' "'Lot4_LAN_Integration\monitoring\prometheus-lan.template.yml'" "'core\monitoring\prometheus-lan.template.yml'"

# Lot4 automation Compose relative paths (relative to deployment/lot4/automation/compose)
foreach ($f in @('docker-compose.central.yml','docker-compose.fogs.yml')) {
  $p = "deployment\lot4\automation\compose\$f"
  Add-Patch $p '../../Real-Time-Predictive-Maintenance' '../../../../projects/mp2'
  Add-Patch $p '../../mp1-simulator' '../../../../projects/mp1/simulator'
  Add-Patch $p '../../Lot4_LAN_Integration/monitoring' '../../core/monitoring'
  Add-Patch $p '../../Lot4_LAN_Integration\monitoring' '../../core\monitoring'
}

# Lot4 Core scripts: RepositoryRoot defaults and core bundle paths
foreach ($f in @('Render-Prometheus-LAN.ps1','Start-FogPC.ps1','Stop-FogPC.ps1','Test-Lot4.ps1','Validate-Lot4-Config.ps1','Update-Lot4-Dashboard.ps1')) {
  $p = "deployment\lot4\core\scripts\$f"
  Add-Patch $p "Join-Path `$PSScriptRoot '..\..'" "Join-Path `$PSScriptRoot '..\..\..\..'"
  Add-Patch $p 'Lot4_LAN_Integration\' 'deployment\lot4\core\'
  Add-Patch $p 'Real-Time-Predictive-Maintenance\' 'projects\mp2\'
}
Add-Patch 'deployment\lot4\core\deployment\Start-Central.ps1' "Join-Path `$Root '..'" "Join-Path `$Root '..\..\..'"
Add-Patch 'deployment\lot4\core\deployment\Start-Central.ps1' "'Real-Time-Predictive-Maintenance'" "'projects\mp2'"
Add-Patch 'deployment\lot4\core\deployment\Configure-Firewall.ps1' "Split-Path `$PSScriptRoot -Parent" "Split-Path `$PSScriptRoot -Parent"

# Core Compose files: paths relative to deployment/lot4/core/<compose-folder>
foreach ($f in @('docker-compose.fog-remote.yml','docker-compose.fog-local-sim.yml')) {
  $p = "deployment\lot4\core\fog-node\$f"
  Add-Patch $p '../../Real-Time-Predictive-Maintenance' '../../../../projects/mp2'
  Add-Patch $p '../../mp1-simulator' '../../../../projects/mp1/simulator'
}
# Active Core README command examples; historical archive docs remain untouched
Add-Patch 'deployment\lot4\core\README.md' 'Lot4_LAN_Integration' 'deployment\lot4\core'
Add-Patch 'deployment\lot4\core\README.md' 'Real-Time-Predictive-Maintenance' 'projects\mp2'

# Automation README path examples (documentation in the active deployment bundle)
Add-Patch 'deployment\lot4\automation\README_DEPLOYMENT.md' 'Lot4_Automation' 'deployment\lot4\automation'
Add-Patch 'deployment\lot4\automation\README_DEPLOYMENT.md' 'Lot4_LAN_Integration' 'deployment\lot4\core'

# Plan / dry run
$changes = [System.Collections.Generic.List[object]]::new()
foreach ($relative in $patches.Keys) {
  $full = Join-Path $RepoRoot $relative
  if (-not (Test-Path -LiteralPath $full -PathType Leaf)) { Write-Warning "Target absent, ignoré: $relative"; continue }
  $original = Get-Content -LiteralPath $full -Raw
  $updated = $original
  $count = 0
  foreach ($rule in $patches[$relative]) {
    $occurrences = ([regex]::Matches($updated, [regex]::Escape($rule.Old))).Count
    if ($occurrences -gt 0) { $updated = $updated.Replace($rule.Old, $rule.New); $count += $occurrences }
  }
  if ($updated -ne $original) { $changes.Add([pscustomobject]@{Relative=$relative;Full=$full;Original=$original;Updated=$updated;Matches=$count}) }
}
Write-Host "Phase 2 path corrections | Root: $RepoRoot"
Write-Host "Files with changes: $($changes.Count) | Text replacements matched: $(($changes | Measure-Object Matches -Sum).Sum)"
foreach ($c in $changes) { Write-Host ("{0} ({1} matches)" -f $c.Relative,$c.Matches) }
if (-not $Apply) { Write-Host 'DRY RUN: no files changed. Re-run with -Apply to apply these targeted edits.'; exit 0 }
if ($changes.Count -eq 0) { Write-Host 'No targeted edits required.'; exit 0 }
$backupRoot = Join-Path $env:USERPROFILE ("Desktop\Fog-Reorg-Phase2-Backups\{0}" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backupRoot -Force | Out-Null
foreach ($c in $changes) {
  $backupPath = Join-Path $backupRoot $c.Relative
  New-Item -ItemType Directory -Path (Split-Path $backupPath -Parent) -Force | Out-Null
  Copy-Item -LiteralPath $c.Full -Destination $backupPath -Force
  Set-Content -LiteralPath $c.Full -Value $c.Updated -Encoding UTF8 -NoNewline
}
Write-Host "APPLIED. Backup directory: $backupRoot" -ForegroundColor Green
Write-Host 'No Docker/Git commands were run. Historical archive directories were not scanned.'
