[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$CentralIP,
    [Parameter(Mandatory=$true)][string]$FogAIP,
    [Parameter(Mandatory=$true)][string]$FogBIP,
    [Parameter(Mandatory=$true)][string]$FogCIP
)
$ErrorActionPreference="Stop"
$RepoRoot=(Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$source=Join-Path $RepoRoot "Lot4_LAN_Integration\monitoring\prometheus-lan.template.yml"
$destination=Join-Path $RepoRoot "Lot4_LAN_Integration\monitoring\prometheus-lan.yml"
if(!(Test-Path $source)){throw "Prometheus template not found: $source"}
$content=Get-Content $source -Raw
$map=@{
    '${CENTRAL_LAN_IP}'=$CentralIP
    '${FOG_A_IP}'=$FogAIP
    '${FOG_B_IP}'=$FogBIP
    '${FOG_C_IP}'=$FogCIP
}
foreach($key in $map.Keys){$content=$content.Replace($key,$map[$key])}
Set-Content -Path $destination -Value $content -Encoding ascii
Write-Host "Prometheus LAN targets rendered to $destination" -ForegroundColor Green
Write-Warning "This script renders targets only. It does not deploy Prometheus or guarantee /metrics endpoints."
