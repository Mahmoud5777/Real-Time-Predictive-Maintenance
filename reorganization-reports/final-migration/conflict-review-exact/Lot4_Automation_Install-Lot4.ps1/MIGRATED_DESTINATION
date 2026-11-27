[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("central","fog-a","fog-b","fog-c")]
    [string]$Role
)
$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$Bundle = Join-Path $RepoRoot "deployment\lot4\core"
$Config = Join-Path $PSScriptRoot "config\deployment.json"

if (!(Get-Command docker -ErrorAction SilentlyContinue)) { throw "Docker CLI not found. Install Docker Desktop first." }
docker info *> $null
if ($LASTEXITCODE -ne 0) { throw "Docker Engine is not running. Start Docker Desktop, then retry." }
if (!(Test-Path $Bundle)) { throw "deployment\lot4\core not found under $RepoRoot." }

$cfg = Get-Content $Config -Raw | ConvertFrom-Json
if ($Role -eq "central") {
    $envPath = Join-Path $Bundle "central\.env"
    if (!(Test-Path $envPath)) {
        Copy-Item (Join-Path $Bundle "central\.env.central.example") $envPath
    }
    Write-Host "Central role prepared. Configure central\.env using deployment.json values." -ForegroundColor Green
} else {
    $envPath = Join-Path $Bundle "fog-node\.env.fog"
    if (!(Test-Path $envPath)) {
        Copy-Item (Join-Path $Bundle "fog-node\.env.fog.example") $envPath
    }
    Write-Host "$Role role prepared. Configure CENTRAL_LAN_IP in fog-node\.env.fog." -ForegroundColor Green
}
Write-Host "Role: $Role"
Write-Host "Repository: $RepoRoot"
Write-Host "Next: run Deploy-Lot4.ps1 -Role $Role"
