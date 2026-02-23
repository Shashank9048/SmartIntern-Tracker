$port = 8000
$tcp = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue

if ($tcp) {
    echo "Killing process on port $port..."
    Stop-Process -Id $tcp.OwningProcess -Force
} else {
    echo "Port $port is free."
}

echo "Starting uvicorn..."
cd "SmartIntern-backend"
uvicorn api.index:app --reload --port 8000
