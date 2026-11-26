Write-Host "Stopping Lot4 deployment containers only..." -ForegroundColor Yellow
docker stop mp2-scheduler-lan-sim mp2-fog-a-lan-sim mp2-fog-b-lan-sim mp2-fog-c-lan-sim 2>$null
docker stop mp2-scheduler-lan-central mp2-fog-a-remote mp2-fog-b-remote mp2-fog-c-remote 2>$null
Write-Host "Stop command completed." -ForegroundColor Green
