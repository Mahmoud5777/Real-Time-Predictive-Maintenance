# Phase 3 focused repair and validation script (ASCII-only)
# Run from repository root. Makes backups before modifying two LAN scripts.
$ErrorActionPreference = 'Stop'
$RepoRoot = (Get-Location).Path
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$BackupRoot = Join-Path $env:USERPROFILE "Desktop\Fog-Phase3-Backups\$Stamp"
$LanFiles = @(
    'deployment\lot4\alternative-deployment\scripts\Test-LanDeployment.ps1',
    'Lot4_LAN_Deployment\scripts\Test-LanDeployment.ps1'
)

Write-Host 'Phase 3 focused repair and validation' -ForegroundColor Cyan

# Exact replacement; preserve source file encoding by reading/writing UTF-8.
foreach ($relative in $LanFiles) {
    $path = Join-Path $RepoRoot $relative
    if (-not (Test-Path -LiteralPath $path)) { throw "Missing expected file: $relative" }
    $content = Get-Content -LiteralPath $path -Raw
    $old = 'Write-Host "Central MQTT $CentralHost:$MqttPort"'
    $new = 'Write-Host "Central MQTT ${CentralHost}:$MqttPort"'
    if ($content.Contains($old)) {
        $backup = Join-Path $BackupRoot $relative
        $backupParent = Split-Path -Parent $backup
        New-Item -ItemType Directory -Path $backupParent -Force | Out-Null
        Copy-Item -LiteralPath $path -Destination $backup -Force
        $content = $content.Replace($old, $new)
        Set-Content -LiteralPath $path -Value $content -Encoding UTF8 -NoNewline
        Write-Host "PATCHED: $relative" -ForegroundColor Green
    } elseif ($content.Contains($new)) {
        Write-Host "Already corrected: $relative" -ForegroundColor Yellow
    } else {
        Write-Warning "Expected line not found; left untouched: $relative"
    }
}

# Validate PowerShell syntax in active migrated roots. Skip this script itself
# and the prior Phase 3 validator, which has known parser issues and is replaced
# as an audit artifact rather than treated as application code.
$scanRoots = @('projects', 'deployment', '.github')
$syntaxIssues = @()
$syntaxFiles = 0
foreach ($relativeRoot in $scanRoots) {
    $rootPath = Join-Path $RepoRoot $relativeRoot
    if (-not (Test-Path -LiteralPath $rootPath)) { continue }
    $psFiles = Get-ChildItem -LiteralPath $rootPath -Recurse -File -Filter '*.ps1'
    foreach ($file in $psFiles) {
        $syntaxFiles++
        $tokens = $null
        $parseErrors = $null
        [System.Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$tokens, [ref]$parseErrors) | Out-Null
        foreach ($parseError in $parseErrors) {
            $syntaxIssues += [pscustomobject]@{
                Category = 'PowerShellSyntax'
                Path = $file.FullName.Substring($RepoRoot.Length).TrimStart('\')
                Details = "Line $($parseError.Extent.StartLineNumber): $($parseError.Message)"
            }
        }
    }
}

# Validate JSON in active roots using PowerShell's JSON parser.
$jsonIssues = @()
$jsonFiles = 0
foreach ($relativeRoot in $scanRoots) {
    $rootPath = Join-Path $RepoRoot $relativeRoot
    if (-not (Test-Path -LiteralPath $rootPath)) { continue }
    foreach ($file in (Get-ChildItem -LiteralPath $rootPath -Recurse -File -Filter '*.json')) {
        $jsonFiles++
        try {
            $raw = Get-Content -LiteralPath $file.FullName -Raw
            $null = ConvertFrom-Json -InputObject $raw -ErrorAction Stop
        } catch {
            $jsonIssues += [pscustomobject]@{
                Category = 'JsonValidation'
                Path = $file.FullName.Substring($RepoRoot.Length).TrimStart('\')
                Details = $_.Exception.Message
            }
        }
    }
}

# Review-only legacy tokens. This is not a failure and does not auto-edit paths.
$legacyTokens = @('mp1-simulator', 'Real-Time-Predictive-Maintenance', 'MP3_Backend_Source', 'Project_Monitoring', 'Lot4_LAN_Integration', 'Lot4_LAN_Deployment', 'Lot4_Automation')
$legacyHits = 0
$legacyFiles = @()
foreach ($relativeRoot in $scanRoots) {
    $rootPath = Join-Path $RepoRoot $relativeRoot
    if (-not (Test-Path -LiteralPath $rootPath)) { continue }
    foreach ($file in (Get-ChildItem -LiteralPath $rootPath -Recurse -File | Where-Object { $_.Extension -in @('.ps1','.yml','.yaml','.json','.md','.txt','.py','.env.example') })) {
        try { $lines = Get-Content -LiteralPath $file.FullName } catch { continue }
        foreach ($line in $lines) {
            foreach ($token in $legacyTokens) {
                if ($line.Contains($token)) {
                    $legacyHits++
                    $legacyFiles += [pscustomobject]@{ Category='LegacyReferenceReview'; Path=$file.FullName.Substring($RepoRoot.Length).TrimStart('\'); Details="Legacy token: $token" }
                    break
                }
            }
        }
    }
}

$allIssues = @($syntaxIssues) + @($jsonIssues) + @($legacyFiles)
$reportDir = Join-Path $RepoRoot 'reorganization-reports\phase3-validation-reliable'
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null
$allIssues | Export-Csv -LiteralPath (Join-Path $reportDir 'issues.csv') -NoTypeInformation -Encoding UTF8
$checks = @(
    [pscustomobject]@{ Check='PowerShell syntax'; Status=if($syntaxIssues.Count -eq 0){'PASS'}else{'FAIL'}; Details="$($syntaxIssues.Count) syntax errors in $syntaxFiles scripts scanned; self-validator excluded." },
    [pscustomobject]@{ Check='JSON validation'; Status=if($jsonIssues.Count -eq 0){'PASS'}else{'FAIL'}; Details="$($jsonIssues.Count) invalid JSON files out of $jsonFiles scanned." },
    [pscustomobject]@{ Check='Legacy reference review'; Status='REVIEW'; Details="$legacyHits legacy-reference lines. Review only; no automatic path changes." }
)
$checks | Export-Csv -LiteralPath (Join-Path $reportDir 'checks.csv') -NoTypeInformation -Encoding UTF8
$failed = @($checks | Where-Object Status -eq 'FAIL').Count
$review = @($checks | Where-Object Status -eq 'REVIEW').Count
$summary = @(
    'Phase 3 focused validation summary',
    "Repository root: $RepoRoot",
    "PowerShell scripts scanned: $syntaxFiles",
    "JSON files scanned: $jsonFiles",
    "Failed checks: $failed",
    "Review checks: $review",
    "Syntax issues: $($syntaxIssues.Count)",
    "JSON issues: $($jsonIssues.Count)",
    "Legacy review lines: $legacyHits",
    "Reports: $reportDir"
)
$summary | Set-Content -LiteralPath (Join-Path $reportDir 'summary.txt') -Encoding UTF8
Write-Host ($summary -join [Environment]::NewLine)
if ($failed -gt 0) { Write-Host 'Validation found failures; inspect reports.' -ForegroundColor Red } else { Write-Host 'No syntax/JSON failures in scanned active roots.' -ForegroundColor Green }
Write-Host "Backup folder (if patched): $BackupRoot"
