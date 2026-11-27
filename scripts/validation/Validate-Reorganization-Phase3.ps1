[CmdletBinding()]
param(
    [string]$RepoRoot = "",
    [switch]$VerboseReport
)
$ErrorActionPreference = 'Stop'

# Resolve repository root: default to the parent of this pack folder, or current folder if script is at repo root.
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    $parentDir = Split-Path -Parent $scriptDir
    if ((Test-Path (Join-Path $parentDir 'projects')) -and (Test-Path (Join-Path $parentDir 'deployment'))) {
        $RepoRoot = $parentDir
    } elseif ((Test-Path (Join-Path $scriptDir 'projects')) -and (Test-Path (Join-Path $scriptDir 'deployment'))) {
        $RepoRoot = $scriptDir
    } else {
        $RepoRoot = (Get-Location).Path
    }
}
$RepoRoot = (Resolve-Path $RepoRoot).Path
$reportDir = Join-Path $RepoRoot 'reorganization-reports\phase3-validation'
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null

$checks = [System.Collections.Generic.List[object]]::new()
$issues = [System.Collections.Generic.List[object]]::new()
function Add-Check([string]$Name,[string]$Status,[string]$Details) {
    $checks.Add([pscustomobject]@{check=$Name;status=$Status;details=$Details})
}
function Add-Issue([string]$Type,[string]$Path,[string]$Details) {
    $issues.Add([pscustomobject]@{type=$Type;path=$Path;details=$Details})
}

# Required migrated directories
$requiredDirs = @(
 'projects\mp1\simulator','projects\mp1\industrial-simulation',
 'projects\mp2','projects\mp3','projects\mp4',
 'deployment\lot4\automation','deployment\lot4\core',
 'deployment\lot4\alternative-deployment',
 'archive\lot4\lot4v3','archive\lot4\lot4_patch31',
 'archive\lot4\legacy-infrastructure'
)
$missingDirs = @($requiredDirs | Where-Object { -not (Test-Path (Join-Path $RepoRoot $_) -PathType Container) })
if ($missingDirs.Count -eq 0) { Add-Check 'Migrated directory structure' 'PASS' "All $($requiredDirs.Count) required directories exist." }
else { Add-Check 'Migrated directory structure' 'FAIL' "Missing: $($missingDirs -join '; ')"; foreach($d in $missingDirs){Add-Issue 'MissingDirectory' $d 'Required migrated directory not found.'} }

# Essential files (presence only; avoid assuming every project has a single entrypoint)
$requiredFiles = @(
 'projects\mp2\docker-compose.yml',
 'projects\mp2\fog_nodes\common\mp1_inference.py',
 'projects\mp2\tests\test_mp3_adapter.py',
 '.github\workflows\mp4-ci.yml',
 'deployment\lot4\automation\Deploy-Lot4.ps1',
 'deployment\lot4\core\scripts\Test-Lot4.ps1'
)
$missingFiles = @($requiredFiles | Where-Object { -not (Test-Path (Join-Path $RepoRoot $_) -PathType Leaf) })
if ($missingFiles.Count -eq 0) { Add-Check 'Essential migrated files' 'PASS' "All $($requiredFiles.Count) expected files exist." }
else { Add-Check 'Essential migrated files' 'FAIL' "Missing: $($missingFiles -join '; ')"; foreach($f in $missingFiles){Add-Issue 'MissingFile' $f 'Expected migrated file not found.'} }

# Parse PowerShell syntax without executing scripts.
$psFiles = @(Get-ChildItem -Path $RepoRoot -Recurse -File -Filter '*.ps1' -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notmatch '[\\/]archive[\\/]|[\\/]\.git[\\/]|[\\/]\.venv[\\/]|[\\/]venv[\\/]|[\\/]node_modules[\\/]' })
$parseErrors = 0
foreach($file in $psFiles) {
    $tokens=$null; $parseErrs=$null
    [void][System.Management.Automation.Language.Parser]::ParseFile($file.FullName,[ref]$tokens,[ref]$parseErrs)
    if ($parseErrs -and $parseErrs.Count) {
        $parseErrors += $parseErrs.Count
        foreach($e in $parseErrs){ Add-Issue 'PowerShellSyntax' ($file.FullName.Substring($RepoRoot.Length).TrimStart('\')) ("Line {0}: {1}" -f $e.Extent.StartLineNumber,$e.Message) }
    }
}
if($parseErrors -eq 0){Add-Check 'PowerShell syntax' 'PASS' "Parsed $($psFiles.Count) PowerShell files; no parse errors."}
else{Add-Check 'PowerShell syntax' 'FAIL' "$parseErrors parse error(s) across scanned scripts."}

# Validate JSON files (ignore generated/cache/archive/venv locations).
$jsonFiles = @(Get-ChildItem -Path $RepoRoot -Recurse -File -Filter '*.json' -ErrorAction SilentlyContinue | Where-Object { $_.FullName -notmatch '[\\/]archive[\\/]|[\\/]\.git[\\/]|[\\/]\.venv[\\/]|[\\/]venv[\\/]|[\\/]node_modules[\\/]|[\\/]__pycache__[\\/]' })
$jsonErrors=0
foreach($file in $jsonFiles){
    try { $raw=Get-Content -LiteralPath $file.FullName -Raw; if(-not [string]::IsNullOrWhiteSpace($raw)){ $null=ConvertFrom-Json -InputObject $raw -ErrorAction Stop } }
    catch { $jsonErrors++; Add-Issue 'JSONSyntax' ($file.FullName.Substring($RepoRoot.Length).TrimStart('\')) $_.Exception.Message }
}
if($jsonErrors -eq 0){Add-Check 'JSON syntax' 'PASS' "Checked $($jsonFiles.Count) JSON files; no parse errors."}
else{Add-Check 'JSON syntax' 'FAIL' "$jsonErrors invalid JSON file(s) out of $($jsonFiles.Count)."}

# Legacy path tokens are review findings only, not automatically errors. Archives excluded.
$legacyTokens = @('Real-Time-Predictive-Maintenance','MP3_Backend_Source','Project_Monitoring','Lot4_LAN_Integration','Lot4_Automation','mp1-simulator')
$textExts = @('.ps1','.yml','.yaml','.md','.py','.json','.txt','.toml','.ini','.cfg','.bat','.sh','.env.example')
$scanRoots = @('projects','deployment\lot4','.github')
$tokenHits=0
foreach($relRoot in $scanRoots){
  $abs=Join-Path $RepoRoot $relRoot
  if(Test-Path $abs){
    $files=Get-ChildItem -Path $abs -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $textExts -contains $_.Extension.ToLowerInvariant() -and $_.FullName -notmatch '[\\/]\.git[\\/]|[\\/]\.venv[\\/]|[\\/]venv[\\/]|[\\/]node_modules[\\/]|[\\/]__pycache__[\\/]' }
    foreach($file in $files){
      $lines=Get-Content -LiteralPath $file.FullName -ErrorAction SilentlyContinue
      $lineNo=0
      foreach($line in $lines){
        $lineNo++
        foreach($token in $legacyTokens){ if($line.Contains($token)){ $tokenHits++; Add-Issue 'LegacyPathTokenReview' ($file.FullName.Substring($RepoRoot.Length).TrimStart('\')) ("Line {0}: token {1}; review whether historical, documentation, or stale path." -f $lineNo,$token) } }
      }
    }
  }
}
Add-Check 'Legacy path token review' 'REVIEW' "$tokenHits legacy token hit(s); findings are review-only and do not trigger changes."

# Output reports
$checks | Export-Csv -LiteralPath (Join-Path $reportDir 'phase3-validation-checks.csv') -NoTypeInformation -Encoding UTF8
$issues | Export-Csv -LiteralPath (Join-Path $reportDir 'phase3-validation-issues.csv') -NoTypeInformation -Encoding UTF8
$failCount=@($checks | Where-Object status -eq 'FAIL').Count
$summaryLines=@(
 'Collaborative Fog Computing — Phase 3 Static Validation',
 ('Repository root: {0}' -f $RepoRoot),
 ('Generated: {0}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')),
 ('PowerShell files parsed: {0}' -f $psFiles.Count),
 ('JSON files checked: {0}' -f $jsonFiles.Count),
 ('Legacy path token hits (review only): {0}' -f $tokenHits),
 ('Validation checks: {0}' -f $checks.Count),
 ('Failed checks: {0}' -f $failCount),
 '',
 'CHECK DETAILS:',
 ($checks | ForEach-Object { '[{0}] {1} — {2}' -f $_.status,$_.check,$_.details }),
 '',
 ('Issue rows: {0}' -f $issues.Count),
 'No Docker commands, service starts/stops, or Git operations were performed.'
)
$summaryLines | Out-File -LiteralPath (Join-Path $reportDir 'phase3-validation-summary.txt') -Encoding UTF8
Write-Host ''
Write-Host 'PHASE 3 STATIC VALIDATION COMPLETE' -ForegroundColor Cyan
Write-Host "Repository: $RepoRoot"
Write-Host "Checks: $($checks.Count) | Failed: $failCount | Findings: $($issues.Count) | Legacy token hits: $tokenHits"
Write-Host "Reports: $reportDir"
if($VerboseReport){ $checks | Format-Table -AutoSize; if($issues.Count){$issues | Format-Table -Wrap -AutoSize} }
if($failCount -gt 0){ exit 1 }
