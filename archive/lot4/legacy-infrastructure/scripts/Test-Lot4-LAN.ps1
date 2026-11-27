param(
  [Parameter(Mandatory=$true)][string]$CentralIP,
  [Parameter(Mandatory=$true)][string]$FogAIP,
  [Parameter(Mandatory=$true)][string]$FogBIP,
  [Parameter(Mandatory=$true)][string]$FogCIP
)
$ErrorActionPreference = "Continue"
$targets = @(
  @{Name="Central MQTT"; Host=$CentralIP; Port=1883},
  @{Name="Fog A API"; Host=$FogAIP; Port=8101},
  @{Name="Fog B API"; Host=$FogBIP; Port=8102},
  @{Name="Fog C API"; Host=$FogCIP; Port=8103}
)
$targets | ForEach-Object {
  Write-Host "`n--- $($_.Name) $($_.Host):$($_.Port) ---" -ForegroundColor Cyan
  Test-NetConnection -ComputerName $_.Host -Port $_.Port -InformationLevel Detailed
}
Write-Host "`nScheduler health: http://${CentralIP}:8100/health"
