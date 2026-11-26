param(
  [string]$CentralHost = "",
  [string[]]$FogHosts = @(),
  [int]$MqttPort = 1883,
  [int[]]$FogPorts = @(8001,8002,8003)
)
$ErrorActionPreference = "Continue"
Write-Host "=== LAN deployment connectivity check ===" -ForegroundColor Cyan
if ($CentralHost) {
  Write-Host "Central MQTT $CentralHost:$MqttPort"
  Test-NetConnection $CentralHost -Port $MqttPort | Select-Object ComputerName,RemotePort,TcpTestSucceeded
}
for ($i=0; $i -lt $FogHosts.Count; $i++) {
  $port = if ($i -lt $FogPorts.Count) { $FogPorts[$i] } else { 8001 }
  Write-Host "Fog host $($FogHosts[$i]):$port"
  Test-NetConnection $FogHosts[$i] -Port $port | Select-Object ComputerName,RemotePort,TcpTestSucceeded
  try { Invoke-RestMethod "http://$($FogHosts[$i]):$port/health" -TimeoutSec 4 | ConvertTo-Json -Depth 4 } catch { Write-Warning "Health endpoint unavailable: $($_.Exception.Message)" }
}
