$port = 8000
# Loop to kill any process on port 8000 (excluding 0)
for ($i = 0; $i -lt 5; $i++) {
    $processes = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -gt 0 } | Select-Object -ExpandProperty OwningProcess -Unique
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
$check = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -gt 0 }
if ($check) {
    Write-Host "ERROR: Port $port is still in use by process $($check.OwningProcess)"
    exit 1
}

Write-Host "Starting uvicorn..."
cd "SmartIntern-backend"
python -m uvicorn api.index:app --host 127.0.0.1 --port 8000
