[CmdletBinding()]
param(
    [string]$RepositoryRoot = (Get-Location).Path
)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath $RepositoryRoot).Path
$Targets = @(
    'projects\mp1\simulator','projects\mp1\industrial-simulation','projects\mp2','projects\mp3','projects\mp4',
    'deployment\lot4\automation','deployment\lot4\core','deployment\lot4\alternative-deployment',
    'archive\lot4\lot4v3','archive\lot4\lot4_patch31','archive\lot4\legacy-infrastructure',
    '.github','docs'
)
$OldTokens = @(
    'mp1-simulator','MP1_Industrial_Simulation','Real-Time-Predictive-Maintenance','MP3_Backend_Source',
    'Project_Monitoring','Lot4_Automation','Lot4_LAN_Integration','Lot4_LAN_Deployment','lot4v3','lot4_patch31'
)
$TextExtensions = @('.py','.ps1','.psm1','.yml','.yaml','.json','.toml','.ini','.cfg','.conf','.md','.txt','.sh','.bat','.xml','.html','.js','.jsx','.ts','.tsx','.css','.sql','.properties')
$SkipDirs = @('.git','.venv','venv','node_modules','__pycache__','.pytest_cache','.mypy_cache')
$Findings = [System.Collections.Generic.List[object]]::new()
$Scanned = 0
foreach ($Target in $Targets) {
    $Path = Join-Path $Root $Target
    if (-not (Test-Path -LiteralPath $Path)) { continue }
    Get-ChildItem -LiteralPath $Path -Recurse -File -Force | Where-Object {
        $ext = $_.Extension.ToLowerInvariant()
        $relative = $_.FullName.Substring($Root.Length).TrimStart('\')
        $parts = $relative -split '\\'
        ($TextExtensions -contains $ext) -and -not ($parts | Where-Object { $SkipDirs -contains $_ }) -and $_.Name -notmatch '^\.env($|\.)'
    } | ForEach-Object {
        $File = $_
        $Scanned++
        try { $Lines = Get-Content -LiteralPath $File.FullName -ErrorAction Stop } catch { return }
        $LineNo = 0
        foreach ($Line in $Lines) {
            $LineNo++
            foreach ($Token in $OldTokens) {
                if ($Line -match [regex]::Escape($Token)) {
                    $Findings.Add([PSCustomObject]@{
                        File = $File.FullName.Substring($Root.Length).TrimStart('\')
                        Line = $LineNo
                        LegacyToken = $Token
                        Text = $Line.Trim()
                    })
                }
            }
        }
    }
}
$ReportDir = Join-Path $Root 'reorganization-reports\phase2-path-audit'
New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null
$Csv = Join-Path $ReportDir 'legacy-path-findings.csv'
$Txt = Join-Path $ReportDir 'legacy-path-audit.txt'
$Findings | Sort-Object File,Line,LegacyToken | Export-Csv -LiteralPath $Csv -NoTypeInformation -Encoding UTF8
$Summary = @(
    "Phase 2 legacy-path audit",
    "Repository: $Root",
    "Files scanned: $Scanned",
    "Legacy token findings: $($Findings.Count)",
    "CSV: $Csv",
    "Note: This is a reference-token inventory, not a claim that every match is a broken path. Documentation and archived/historical references may be intentional. No files were modified."
)
$Summary | Set-Content -LiteralPath $Txt -Encoding UTF8
$Summary | ForEach-Object { Write-Host $_ }
Write-Host "Report CSV: $Csv"
Write-Host "Report TXT: $Txt"
