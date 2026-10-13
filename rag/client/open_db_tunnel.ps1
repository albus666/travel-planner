# Forward the server's Postgres (127.0.0.1:5432) to localhost:5432, so a local
# Python process can connect directly. Not needed when using the HTTP service.
#
# Keep this window open; run your query in another terminal.
#
# Usage (from project root):
#   powershell -ExecutionPolicy Bypass -File rag\client\open_db_tunnel.ps1
#
# NOTE: keep this file ASCII-only (Windows PowerShell reads .ps1 as GBK without a BOM).

$ErrorActionPreference = "Stop"
# client -> rag -> project root
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Key = Join-Path $ProjectRoot "key\cursor-pilot.pem"
$HostName = "52.199.126.245"

if (-not (Test-Path $Key)) {
    Write-Error "key not found: $Key"
}

Write-Host "SSH tunnel: local 5432 -> ${HostName}:127.0.0.1:5432"
Write-Host "Keep this window open. Ctrl+C to close the tunnel."
ssh -i $Key -N -L 5432:127.0.0.1:5432 "ubuntu@$HostName"
