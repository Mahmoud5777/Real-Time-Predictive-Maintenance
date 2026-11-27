[CmdletBinding()]
param(
    [string]$RepositoryRoot = (Get-Location).Path,
    [switch]$Execute
)
$ErrorActionPreference = 'Stop'
$RepositoryRoot = (Resolve-Path -LiteralPath $RepositoryRoot).Path

$Mappings = @(
    @{ Source='mp1-simulator'; Destination='projects/mp1/simulator' },
    @{ Source='MP1_Industrial_Simulation'; Destination='projects/mp1/industrial-simulation' },
    @{ Source='Real-Time-Predictive-Maintenance'; Destination='projects/mp2' },
    @{ Source='MP3_Backend_Source'; Destination='projects/mp3' },
    @{ Source='Project_Monitoring'; Destination='projects/mp4' },
    @{ Source='Lot4_Automation'; Destination='deployment/lot4/automation' },
    @{ Source='Lot4_LAN_Integration'; Destination='deployment/lot4/core' },
    @{ Source='Lot4_LAN_Deployment'; Destination='deployment/lot4/alternative-deployment' },
    @{ Source='lot4v3'; Destination='archive/lot4/lot4v3' },
    @{ Source='lot4_patch31'; Destination='archive/lot4/lot4_patch31' },
    @{ Source='central'; Destination='archive/lot4/legacy-infrastructure/central' },
    @{ Source='fog-node'; Destination='archive/lot4/legacy-infrastructure/fog-node' },
    @{ Source='monitoring'; Destination='archive/lot4/legacy-infrastructure/monitoring' },
    @{ Source='scripts'; Destination='archive/lot4/legacy-infrastructure/scripts' }
)
$ExcludedDirectoryNames = @('.git','.venv','venv','node_modules','__pycache__','.pytest_cache','.mypy_cache','.ruff_cache','dist','build','.next','site-packages')
$ExcludedFilePatterns = @('*.pyc','*.log')

Write-Host "Repository: $RepositoryRoot" -ForegroundColor Cyan
Write-Host "Mode: $(if($Execute){'EXECUTION - COPY ONLY'}else{'DRY RUN - NO FILES COPIED'})" -ForegroundColor Yellow
Write-Host "Old directories will NOT be moved or deleted. Existing destination directories cause a stop."

foreach ($Mapping in $Mappings) {
    $SourcePath = Join-Path $RepositoryRoot $Mapping.Source
    $DestinationPath = Join-Path $RepositoryRoot $Mapping.Destination
    if (-not (Test-Path -LiteralPath $SourcePath -PathType Container)) {
        Write-Warning "Source absent, skipped: $($Mapping.Source)"
        continue
    }
    if (Test-Path -LiteralPath $DestinationPath) {
        throw "Destination already exists; refusing to overwrite: $($Mapping.Destination)"
    }
    $Items = Get-ChildItem -LiteralPath $SourcePath -Recurse -File -Force | Where-Object {
        $Relative = $_.FullName.Substring($SourcePath.Length).TrimStart('\','/')
        $Segments = $Relative -split '[\\/]'
        -not ($Segments | Where-Object { $_ -in $ExcludedDirectoryNames -or $_ -like '.venv*' -or $_ -like 'venv-*' }) -and
        $_.Extension -notin @('.pyc','.log')
    }
    Write-Host ("{0} -> {1} ({2} files selected)" -f $Mapping.Source,$Mapping.Destination,$Items.Count)
    if ($Execute) {
        New-Item -ItemType Directory -Path $DestinationPath -Force | Out-Null
        foreach ($Item in $Items) {
            $Relative = $Item.FullName.Substring($SourcePath.Length).TrimStart('\','/')
            $Target = Join-Path $DestinationPath $Relative
            $TargetDir = Split-Path -Parent $Target
            if (-not (Test-Path -LiteralPath $TargetDir)) { New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null }
            Copy-Item -LiteralPath $Item.FullName -Destination $Target -Force:$false
        }
        Write-Host "Copied (source retained): $($Mapping.Destination)" -ForegroundColor Green
    }
}
if (-not $Execute) {
    Write-Host "`nDry-run complete. Re-run with -Execute to copy files into the new structure." -ForegroundColor Green
} else {
    Write-Host "`nCopy phase complete. No source folders deleted, no Git actions, no Docker actions." -ForegroundColor Green
}
