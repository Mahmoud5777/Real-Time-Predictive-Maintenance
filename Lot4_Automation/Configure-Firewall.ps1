[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidateSet("central","fog-a","fog-b","fog-c")][string]$Role,
    [string]$RemoteAddress="LocalSubnet"
)
$principal=New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw "Run PowerShell as Administrator for firewall configuration."}
$ports=switch($Role){"central" {@(1883,8100)} "fog-a" {@(8101)} "fog-b" {@(8102)} "fog-c" {@(8103)}}
foreach($port in $ports){
    $name="Lot4-$Role-TCP-$port"
    if(Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue){Remove-NetFirewallRule -DisplayName $name}
    New-NetFirewallRule -DisplayName $name -Direction Inbound -Action Allow -Protocol TCP -LocalPort $port -RemoteAddress $RemoteAddress -Profile Any | Out-Null
}
Write-Host "Firewall rules configured for $Role (remote scope: $RemoteAddress)." -ForegroundColor Green
