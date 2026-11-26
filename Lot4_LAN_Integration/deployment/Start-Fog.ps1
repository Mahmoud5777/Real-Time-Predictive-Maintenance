param([Parameter(Mandatory=$true)][ValidateSet('fog-a','fog-b','fog-c')][string]$Role,[string]$CentralIP)
$startScript = Join-Path (Join-Path (Split-Path $PSScriptRoot -Parent) 'scripts') 'Start-FogPC.ps1'
if (-not (Test-Path -LiteralPath $startScript)) { throw "Fog start script not found: $startScript" }
if ($CentralIP) { & $startScript -Node $Role -CentralIP $CentralIP }
else { & $startScript -Node $Role }
Write-Host "$Role demarre. Le pare-feu n a pas ete modifie." -ForegroundColor Green

