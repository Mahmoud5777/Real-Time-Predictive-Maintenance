# Run as Administrator. Scope is restricted to the specified remote IPs/subnet.
param(
 [string]$RemoteAddress="LocalSubnet",
 [int[]]$Ports=@(1883,8000,8001,8002,8003,8004,3001)
)
$ErrorActionPreference="Stop"
foreach($p in $Ports) {
  $name="FogPredictiveMaintenance-LAN-$p"
  if(Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue) {
    Remove-NetFirewallRule -DisplayName $name
  }
  New-NetFirewallRule -DisplayName $name -Direction Inbound -Action Allow -Protocol TCP -LocalPort $p -RemoteAddress $RemoteAddress -Profile Private
}
Write-Host "Rules created. Review Windows Firewall and restrict RemoteAddress to trusted LAN IPs." -ForegroundColor Green
