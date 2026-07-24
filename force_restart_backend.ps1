$port = 8000
# Loop to kill any process on port 8000
for ($i = 0; $i -lt 5; $i++) {
    $processes = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
    if ($processes) {
        foreach ($procId in $processes) {
            Write-Host "Killing process $procId on port $port (Attempt $($i+1))"
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
        Start-Sleep -Seconds 2
    }
    else {
        Write-Host "Port $port is free"
        break
    }
}

# Verify
$check = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
if ($check) {
    Write-Host "ERROR: Port $port is still in use by process $($check.OwningProcess)"
    exit 1
}

Write-Host "Starting uvicorn..."
cd "SmartIntern-backend"
# Run using virtual environment to ensure all packages (e.g., apscheduler) are found
python -m uvicorn api.index:app --host 127.0.0.1 --port 8000
