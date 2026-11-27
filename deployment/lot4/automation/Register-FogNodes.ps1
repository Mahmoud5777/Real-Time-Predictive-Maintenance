[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$FogAIP,
    [Parameter(Mandatory=$true)][string]$FogBIP,
    [Parameter(Mandatory=$true)][string]$FogCIP
)
$nodes=@(
    @{Name="fog-a";Url="http://${FogAIP}:8101/health"},
    @{Name="fog-b";Url="http://${FogBIP}:8102/health"},
    @{Name="fog-c";Url="http://${FogCIP}:8103/health"}
)
$bad=@()
foreach($n in $nodes){
    try {
        $response=Invoke-RestMethod -Uri $n.Url -TimeoutSec 8
        Write-Host "$($n.Name): reachable ($($n.Url))" -ForegroundColor Green
    } catch {
        $bad += $n.Name
        Write-Warning "$($n.Name) not reachable: $($_.Exception.Message)"
    }
}
if($bad.Count){throw "Fog nodes not reachable: $($bad -join ', '). Start them and retry."}
Write-Host "All three Fog nodes are reachable. Scheduler uses their IPs from central .env." -ForegroundColor Green
