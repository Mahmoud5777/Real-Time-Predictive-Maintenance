[CmdletBinding()]
param([string]$ConfigPath = (Join-Path $PSScriptRoot 'config\deployment.json'))
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'Validate-DeploymentJson.ps1') -ConfigPath $ConfigPath
$cfg = Get-Content -LiteralPath $ConfigPath -Raw | ConvertFrom-Json
$targets = @(
  [pscustomobject]@{Name='MQTT central';Host=[string]$cfg.centralIp;Port=[int]$cfg.network.mqttPort;Url=$null},
  [pscustomobject]@{Name='Scheduler';Host=[string]$cfg.centralIp;Port=[int]$cfg.schedulerPort;Url="http://$($cfg.centralIp):$($cfg.schedulerPort)/health"},
  [pscustomobject]@{Name='Fog A';Host=[string]$cfg.fogAIp;Port=[int]$cfg.fogPorts.'fog-a';Url="http://$($cfg.fogAIp):$($cfg.fogPorts.'fog-a')/health"},
  [pscustomobject]@{Name='Fog B';Host=[string]$cfg.fogBIp;Port=[int]$cfg.fogPorts.'fog-b';Url="http://$($cfg.fogBIp):$($cfg.fogPorts.'fog-b')/health"},
  [pscustomobject]@{Name='Fog C';Host=[string]$cfg.fogCIp;Port=[int]$cfg.fogPorts.'fog-c';Url="http://$($cfg.fogCIp):$($cfg.fogPorts.'fog-c')/health"}
)
$failed = 0
foreach ($target in $targets) {
  $tcp = Test-NetConnection -ComputerName $target.Host -Port $target.Port -WarningAction SilentlyContinue
  $ok = [bool]$tcp.TcpTestSucceeded
  if ($ok -and $target.Url) { try { Invoke-RestMethod -Uri $target.Url -TimeoutSec 5 | Out-Null } catch { $ok=$false } }
  Write-Host ("{0,-18} {1}:{2} {3}" -f $target.Name,$target.Host,$target.Port,$(if($ok){'PASS'}else{'FAIL'})) -ForegroundColor $(if($ok){'Green'}else{'Red'})
  if (-not $ok) { $failed++ }
}
if ($failed) { throw "$failed endpoint(s) unreachable or unhealthy." }
Write-Host 'LOT4 LAN CONNECTIVITY: PASS' -ForegroundColor Green
