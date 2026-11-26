param([ValidateSet("central","fog-a","fog-b","fog-c")][string]$Role)
$Ports = switch ($Role) {
  "central" { @(1883,8100) }
  "fog-a"   { @(8101) }
  "fog-b"   { @(8102) }
  "fog-c"   { @(8103) }
}
foreach ($Port in $Ports) {
  $Name = "Lot4-$Role-TCP-$Port"
  if (-not (Get-NetFirewallRule -DisplayName $Name -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $Name -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -Profile Private | Out-Null
  }
}
Write-Host "Firewall configured for $Role" -ForegroundColor Green

