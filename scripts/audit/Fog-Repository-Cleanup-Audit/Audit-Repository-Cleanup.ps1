[CmdletBinding()]
param(
    [string]$RepositoryRoot = (Get-Location).Path,
    [string]$ReportDirectory = "reorganization-reports\repository-cleanup-audit"
)
$ErrorActionPreference = 'Stop'
$RepositoryRoot = (Resolve-Path $RepositoryRoot).Path
$ReportPath = Join-Path $RepositoryRoot $ReportDirectory
New-Item -ItemType Directory -Path $ReportPath -Force | Out-Null

Write-Host 'Repository cleanup audit (READ-ONLY)' -ForegroundColor Cyan
Write-Host "Root: $RepositoryRoot"
Write-Host 'No files will be renamed, moved, or deleted.' -ForegroundColor Yellow

# Git tracking map
$trackedSet = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
$gitAvailable = $true
try {
    $trackedLines = git -C $RepositoryRoot ls-files --cached
    if ($LASTEXITCODE -ne 0) { throw 'git ls-files failed' }
    foreach ($line in $trackedLines) { [void]$trackedSet.Add(($line -replace '/', '\')) }
} catch {
    $gitAvailable = $false
    Write-Warning "Could not retrieve Git tracked files: $($_.Exception.Message)"
}

$skipDirs = @('.git','node_modules','.venv','venv','__pycache__','.pytest_cache','.mypy_cache','.ruff_cache','dist','build','coverage','vendor')
$allFiles = Get-ChildItem -LiteralPath $RepositoryRoot -Recurse -File -Force -ErrorAction SilentlyContinue | Where-Object {
    $relative = $_.FullName.Substring($RepositoryRoot.Length).TrimStart('\','/')
    $segments = $relative -split '[\\/]'
    -not ($segments | Where-Object { $skipDirs -contains $_ }) -and
    $_.FullName -notlike "$ReportPath*"
}

$inventory = foreach ($file in $allFiles) {
    $rel = $file.FullName.Substring($RepositoryRoot.Length).TrimStart('\','/') -replace '/', '\'
    $tracked = $trackedSet.Contains($rel)
    $status = if ($tracked) { 'TRACKED' } else { 'UNTRACKED_OR_IGNORED' }
    $name = $file.Name
    $nameIssues = @()
    if ($name -match '\s') { $nameIssues += 'Whitespace in filename' }
    if ($name -match '[^\x00-\x7F]') { $nameIssues += 'Non-ASCII filename' }
    if ($name -match '[A-Z]') { $nameIssues += 'Uppercase letters (review convention)' }
    if ($name -match '^(copy|copie|backup|old|ancien|final|new|temp|tmp)[-_ ]' -or $name -match '(backup|old|obsolete|final|copy|copie|temp|tmp)' ) { $nameIssues += 'Possible version/temp/backup naming' }
    if ($name -match '\.\w+\.\w+$') { $nameIssues += 'Multiple extensions (review)' }
    $candidate = 'Review'
    if ($rel -match '(^|[\\/])(node_modules|\.venv|venv|__pycache__|\.pytest_cache|\.mypy_cache|\.ruff_cache|dist|build|coverage)([\\/]|$)' -or $name -match '\.(pyc|pyo|log|tmp|bak|backup|swp)$') { $candidate = 'LikelyGeneratedOrTemporary' }
    [PSCustomObject]@{
        RelativePath = $rel
        FileName = $name
        Extension = $file.Extension
        Bytes = $file.Length
        LastWriteTime = $file.LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss')
        GitTracking = $status
        NamingReview = ($nameIssues -join '; ')
        CleanupClassification = $candidate
    }
}

$inventory | Sort-Object RelativePath | Export-Csv (Join-Path $ReportPath 'file-inventory.csv') -NoTypeInformation -Encoding UTF8

# Hash duplicate scan, limited to inventory files; report duplicates but do not remove.
$duplicateGroups = @()
$hashMap = @{}
foreach ($file in $allFiles) {
    try {
        $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
        if (-not $hashMap.ContainsKey($hash)) { $hashMap[$hash] = @() }
        $hashMap[$hash] += $file.FullName.Substring($RepositoryRoot.Length).TrimStart('\','/') -replace '/', '\'
    } catch { }
}
foreach ($hash in $hashMap.Keys) {
    if ($hashMap[$hash].Count -gt 1) {
        $duplicateGroups += [PSCustomObject]@{ SHA256 = $hash; Count = $hashMap[$hash].Count; Files = ($hashMap[$hash] -join ' | ') }
    }
}
$duplicateGroups | Sort-Object Count -Descending | Export-Csv (Join-Path $ReportPath 'duplicate-files-by-hash.csv') -NoTypeInformation -Encoding UTF8

# Git status and untracked list
$gitStatus = @()
if ($gitAvailable) {
    $gitStatus = git -C $RepositoryRoot status --short --ignored=matching
    $gitStatus | Set-Content (Join-Path $ReportPath 'git-status-short.txt') -Encoding UTF8
    $untracked = git -C $RepositoryRoot ls-files --others --exclude-standard
    $untracked | Set-Content (Join-Path $ReportPath 'git-untracked-not-ignored.txt') -Encoding UTF8
    $ignored = git -C $RepositoryRoot ls-files --others --ignored --exclude-standard
    $ignored | Set-Content (Join-Path $ReportPath 'git-ignored-files.txt') -Encoding UTF8
}

# Top-level directory size / file count summary
$topSummary = foreach ($dir in Get-ChildItem -LiteralPath $RepositoryRoot -Directory -Force | Where-Object { $_.Name -ne '.git' }) {
    $children = Get-ChildItem -LiteralPath $dir.FullName -Recurse -File -Force -ErrorAction SilentlyContinue
    [PSCustomObject]@{ Directory = $dir.Name; FileCount = ($children | Measure-Object).Count; TotalBytes = ($children | Measure-Object -Property Length -Sum).Sum }
}
$topSummary | Sort-Object Directory | Export-Csv (Join-Path $ReportPath 'top-level-summary.csv') -NoTypeInformation -Encoding UTF8

$trackedCount = ($inventory | Where-Object GitTracking -eq 'TRACKED' | Measure-Object).Count
$untrackedCount = ($inventory | Where-Object GitTracking -eq 'UNTRACKED_OR_IGNORED' | Measure-Object).Count
$namingCount = ($inventory | Where-Object { $_.NamingReview } | Measure-Object).Count
$summary = @(
    'Repository Cleanup Audit — READ ONLY',
    "Root: $RepositoryRoot",
    "Files inventoried (excluding common generated directories): $($inventory.Count)",
    "Tracked files: $trackedCount",
    "Untracked or ignored files: $untrackedCount",
    "Files with naming review flags: $namingCount",
    "Duplicate-content groups: $($duplicateGroups.Count)",
    "Top-level directories: $($topSummary.Count)",
    '',
    'Reports: file-inventory.csv, duplicate-files-by-hash.csv, git-status-short.txt, git-untracked-not-ignored.txt, git-ignored-files.txt, top-level-summary.csv',
    'This audit does not delete, rename, move, or edit files.'
)
$summary | Set-Content (Join-Path $ReportPath 'SUMMARY.txt') -Encoding UTF8
$summary | ForEach-Object { Write-Host $_ }
Write-Host "Report directory: $ReportPath" -ForegroundColor Green
