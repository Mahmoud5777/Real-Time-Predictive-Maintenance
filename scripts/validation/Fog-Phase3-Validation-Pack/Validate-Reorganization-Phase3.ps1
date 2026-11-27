# Phase 3 static validation - ASCII-only script
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$PackDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $PackDir
$ReportDir = Join-Path $RepoRoot 'reorganization-reports\phase3-validation'
New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null

$checks = New-Object System.Collections.Generic.List[object]
$issues = New-Object System.Collections.Generic.List[object]

function Add-Check {
    param([string]$Name, [string]$Status, [string]$Details)
    $checks.Add([pscustomobject]@{ Check = $Name; Status = $Status; Details = $Details })
}
function Add-Issue {
    param([string]$Category, [string]$Path, [string]$Details)
    $issues.Add([pscustomobject]@{ Category = $Category; Path = $Path; Details = $Details })
}

# Expected migrated structure
$expectedDirs = @(
    'projects\mp1\simulator',
    'projects\mp1\industrial-simulation',
    'projects\mp2',
    'projects\mp3',
    'projects\mp4',
    'deployment\lot4\automation',
    'deployment\lot4\core',
    'deployment\lot4\alternative-deployment',
    'archive\lot4\lot4v3',
    'archive\lot4\lot4_patch31',
    'archive\lot4\legacy-infrastructure'
)
$missingDirs = @()
foreach ($dir in $expectedDirs) {
    if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot $dir) -PathType Container)) {
        $missingDirs += $dir
    }
}
if ($missingDirs.Count -eq 0) {
    Add-Check 'Migrated directories' 'PASS' 'All expected directories exist.'
} else {
    Add-Check 'Migrated directories' 'FAIL' ($missingDirs -join '; ')
    foreach ($dir in $missingDirs) { Add-Issue 'MissingDirectory' $dir 'Expected migrated directory not found.' }
}

# Key files (presence only)
$expectedFiles = @(
    'projects\mp2\docker-compose.yml',
    'projects\mp2\fog_nodes\common\mp1_inference.py',
    'projects\mp2\tests\test_mp3_adapter.py',
    'projects\mp3\mp3-cloud',
    'projects\mp4\frontend',
    '.github\workflows\mp4-ci.yml',
    'deployment\lot4\automation\Deploy-Lot4.ps1',
    'deployment\lot4\core\scripts\Test-Lot4.ps1'
)
$missingFiles = @()
foreach ($item in $expectedFiles) {
    if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot $item))) { $missingFiles += $item }
}
if ($missingFiles.Count -eq 0) {
    Add-Check 'Essential files and folders' 'PASS' 'All expected entries exist.'
} else {
    Add-Check 'Essential files and folders' 'FAIL' ($missingFiles -join '; ')
    foreach ($item in $missingFiles) { Add-Issue 'MissingEntry' $item 'Expected file or folder not found.' }
}

# PowerShell parse checks without executing scripts
$psFiles = Get-ChildItem -LiteralPath $RepoRoot -Recurse -File -Filter '*.ps1' -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch '[\\/]archive[\\/]' -and $_.FullName -notmatch '[\\/]\.git[\\/]' -and $_.FullName -notmatch '[\\/]\.venv[\\/]' -and $_.FullName -notmatch '[\\/]Fog-Phase3-Validation-Pack[\\/]' }
$parseErrors = 0
foreach ($file in $psFiles) {
    $tokens = $null
    $parseErrs = $null
    [void][System.Management.Automation.Language.Parser]::ParseFile($file.FullName, [ref]$tokens, [ref]$parseErrs)
    if ($parseErrs.Count -gt 0) {
        $parseErrors += $parseErrs.Count
        foreach ($err in $parseErrs) {
            $rel = $file.FullName.Substring($RepoRoot.Length).TrimStart('\')
            Add-Issue 'PowerShellSyntax' $rel ('Line {0}: {1}' -f $err.Extent.StartLineNumber, $err.Message)
        }
    }
}
if ($parseErrors -eq 0) {
    Add-Check 'PowerShell syntax' 'PASS' ('Parsed {0} PowerShell files; no syntax errors.' -f $psFiles.Count)
} else {
    Add-Check 'PowerShell syntax' 'FAIL' ('{0} syntax errors in {1} files scanned.' -f $parseErrors, $psFiles.Count)
}

# JSON parse checks
$jsonFiles = Get-ChildItem -LiteralPath $RepoRoot -Recurse -File -Filter '*.json' -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notmatch '[\\/]archive[\\/]' -and $_.FullName -notmatch '[\\/]\.git[\\/]' -and $_.FullName -notmatch '[\\/]\.venv[\\/]' }
$jsonErrors = 0
foreach ($file in $jsonFiles) {
    try {
        $raw = Get-Content -LiteralPath $file.FullName -Raw
        if ([string]::IsNullOrWhiteSpace($raw)) { throw 'Empty JSON file.' }
        $null = $raw | ConvertFrom-Json -ErrorAction Stop
    } catch {
        $jsonErrors++
        $rel = $file.FullName.Substring($RepoRoot.Length).TrimStart('\')
        Add-Issue 'JsonValidation' $rel $_.Exception.Message
    }
}
if ($jsonErrors -eq 0) {
    Add-Check 'JSON validation' 'PASS' ('Validated {0} JSON files.' -f $jsonFiles.Count)
} else {
    Add-Check 'JSON validation' 'FAIL' ('{0} invalid JSON files out of {1}.' -f $jsonErrors, $jsonFiles.Count)
}

# Review legacy references in active project/deployment/docs roots only; do not edit files.
$scanRoots = @('projects', 'deployment', '.github')
$legacyTokens = @('Real-Time-Predictive-Maintenance', 'MP3_Backend_Source', 'Project_Monitoring', 'Lot4_LAN_Integration', 'Lot4_Automation', 'Lot4_LAN_Deployment', 'mp1-simulator')
$tokenHits = 0
foreach ($rootName in $scanRoots) {
    $scanPath = Join-Path $RepoRoot $rootName
    if (Test-Path -LiteralPath $scanPath) {
        $scanFiles = Get-ChildItem -LiteralPath $scanPath -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Extension -in @('.ps1', '.yml', '.yaml', '.json', '.py', '.md', '.txt', '.toml', '.ini', '.conf', '.sh', '.bat', '.env.example') }
        foreach ($file in $scanFiles) {
            try { $contentLines = Get-Content -LiteralPath $file.FullName -ErrorAction Stop } catch { continue }
            foreach ($line in $contentLines) {
                foreach ($token in $legacyTokens) {
                    if ($line.Contains($token)) {
                        $tokenHits++
                        $relPath = $file.FullName.Substring($RepoRoot.Length).TrimStart('\')
                        Add-Issue 'LegacyReferenceReview' $relPath ('Legacy token found: {0}' -f $token)
                        break
                    }
                }
            }
        }
    }
}
Add-Check 'Legacy reference review' 'REVIEW' ('Found {0} lines with legacy tokens in active roots. Review only; no automatic changes.' -f $tokenHits)

# Save reports
$checks | Export-Csv -LiteralPath (Join-Path $ReportDir 'phase3-validation-checks.csv') -NoTypeInformation -Encoding UTF8
$issues | Export-Csv -LiteralPath (Join-Path $ReportDir 'phase3-validation-issues.csv') -NoTypeInformation -Encoding UTF8
$failed = @($checks | Where-Object { $_.Status -eq 'FAIL' }).Count
$review = @($checks | Where-Object { $_.Status -eq 'REVIEW' }).Count
$summaryLines = @(
    'Phase 3 static validation summary',
    ('Repository root: {0}' -f $RepoRoot),
    ('Checks: {0}' -f $checks.Count),
    ('Failed checks: {0}' -f $failed),
    ('Review checks: {0}' -f $review),
    ('Issues recorded: {0}' -f $issues.Count),
    '',
    'Check results:'
)
foreach ($check in $checks) {
    $summaryLines += ('[{0}] {1} - {2}' -f $check.Status, $check.Check, $check.Details)
}
$summaryLines += ''
$summaryLines += ('Reports directory: {0}' -f $ReportDir)
Set-Content -LiteralPath (Join-Path $ReportDir 'phase3-validation-summary.txt') -Value $summaryLines -Encoding UTF8

Write-Host 'Phase 3 static validation completed.'
Write-Host ('Failed checks: {0} | Review checks: {1} | Issues: {2}' -f $failed, $review, $issues.Count)
Write-Host ('Reports: {0}' -f $ReportDir)
