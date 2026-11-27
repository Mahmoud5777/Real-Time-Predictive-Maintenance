[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$CentralIP,
    [Parameter(Mandatory=$true)][string]$FogAIP,
    [Parameter(Mandatory=$true)][string]$FogBIP,
    [Parameter(Mandatory=$true)][string]$FogCIP
)
$ErrorActionPreference = "Continue"
$targets = @(
    @{Name="Central MQTT"; Host=$CentralIP; Port=1883; Url=$null},
    @{Name="Central Scheduler"; Host=$CentralIP; Port=8100; Url="http://${CentralIP}:8100/health"},
    @{Name="Fog A"; Host=$FogAIP; Port=8101; Url="http://${FogAIP}:8101/health"},
    @{Name="Fog B"; Host=$FogBIP; Port=8102; Url="http://${FogBIP}:8102/health"},
    @{Name="Fog C"; Host=$FogCIP; Port=8103; Url="http://${FogCIP}:8103/health"}
)
$failed=0
foreach($t in $targets) {
    $tcp=Test-NetConnection -ComputerName $t.Host -Port $t.Port -WarningAction SilentlyContinue
    $ok=[bool]$tcp.TcpTestSucceeded
    if ($ok -and $t.Url) {
        try { $r=Invoke-RestMethod -Uri $t.Url -TimeoutSec 5; $ok=$true } catch { $ok=$false }
    }
    $state=if($ok){"PASS"}else{"FAIL";$failed++}
    Write-Host ("{0,-20} {1}:{2} {3}" -f $t.Name,$t.Host,$t.Port,$state) -ForegroundColor $(if($ok){"Green"}else{"Red"})
}
if($failed -gt 0){ throw "$failed endpoint(s) failed." }
Write-Host "LOT4 LAN CONNECTIVITY: PASS" -ForegroundColor Green
