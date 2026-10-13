# Call the retrieval service over HTTP (demo/debug).
# The service listens on the server's 127.0.0.1:8100 only, so this opens a
# one-shot SSH port-forward and posts to /search.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File rag\client\ask_http.ps1 -QuestionFile rag\fixtures\my_q.txt -TopK 5
#
# NOTE: keep this file ASCII-only. Windows PowerShell reads .ps1 as GBK without a BOM,
#       and Chinese characters can break string parsing.

param(
    [string]$Question = "",
    [string]$QuestionFile = "",
    [int]$TopK = 3,
    [int]$LocalPort = 18100,
    [switch]$Ask
)

$ErrorActionPreference = "Stop"
$RagRoot = Split-Path -Parent $PSScriptRoot
$ProjectRoot = Split-Path -Parent $RagRoot
$Key = Join-Path $ProjectRoot "key\cursor-pilot.pem"
$HostName = "52.199.126.245"
$Endpoint = "search"
if ($Ask) {
    $Endpoint = "ask"
    if (-not $PSBoundParameters.ContainsKey('TopK')) { $TopK = 5 }
}

if ($QuestionFile) {
    $Question = [IO.File]::ReadAllText((Resolve-Path $QuestionFile).Path, [Text.Encoding]::UTF8).Trim()
}
if (-not $Question) {
    throw "provide -Question or -QuestionFile"
}

$tempKey = Join-Path $env:TEMP ("travel_ask_{0}.pem" -f [guid]::NewGuid().ToString('N'))
$tunnel = $null
try {
    Copy-Item -LiteralPath $Key -Destination $tempKey
    $acl = New-Object System.Security.AccessControl.FileSecurity
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $acl.SetOwner([System.Security.Principal.NTAccount]$identity)
    $acl.SetAccessRuleProtection($true, $false)
    $acl.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule($identity, 'FullControl', 'Allow')))
    Set-Acl -LiteralPath $tempKey -AclObject $acl
    $sshExe = Join-Path $env:WINDIR 'System32\OpenSSH\ssh.exe'
    $tunnel = Start-Process $sshExe -ArgumentList @(
        '-i', ('"{0}"' -f $tempKey), '-N',
        '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
        '-o', 'ExitOnForwardFailure=yes', '-o', 'ConnectTimeout=15',
        '-L', "${LocalPort}:127.0.0.1:8100", "ubuntu@$HostName"
    ) -PassThru -WindowStyle Hidden
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        if ($tunnel.HasExited) { throw 'SSH tunnel exited before becoming ready' }
        $tcp = New-Object Net.Sockets.TcpClient
        try { $tcp.Connect('127.0.0.1', $LocalPort); $ready = $true } catch {} finally { $tcp.Dispose() }
        if ($ready) { break }
        Start-Sleep -Milliseconds 500
    }
    if (-not $ready) { throw 'SSH tunnel did not become ready' }
    $body = @{ question = $Question; top_k = $TopK } | ConvertTo-Json -Compress
    $bytes = [Text.Encoding]::UTF8.GetBytes($body)
    $resp = Invoke-RestMethod -Uri "http://127.0.0.1:$LocalPort/$Endpoint" -Method Post `
        -ContentType "application/json; charset=utf-8" -Body $bytes -TimeoutSec 120

    if ($Ask) {
        Write-Output "Q: $($resp.question)"
        Write-Output "status=$($resp.status)  elapsed_ms=$($resp.elapsed_ms)"
        Write-Output $resp.answer
        foreach ($warning in $resp.warnings) { Write-Output $warning }
        foreach ($citation in $resp.citations) {
            Write-Output ("[{0}] {1}/{2} collected_at={3} {4}" -f $citation.source_id, $citation.name, $citation.theme, $citation.collected_at, $citation.source_url)
        }
        return
    }

    Write-Output "Q: $($resp.question)"
    Write-Output "hits=$($resp.hits.Count)  elapsed_ms=$($resp.elapsed_ms)"
    $i = 0
    foreach ($h in $resp.hits) {
        $i++
        $preview = ($h.text -replace "\r?\n", " ")
        if ($preview.Length -gt 160) { $preview = $preview.Substring(0, 160) + "..." }
        $line = "{0}. {1} / {2}  sim={3:N4}  chunk_id={4}" -f $i, $h.name, $h.theme, $h.similarity, $h.chunk_id
        Write-Output $line
        Write-Output "   $preview"
    }
}
finally {
    if ($tunnel -and -not $tunnel.HasExited) { Stop-Process -Id $tunnel.Id -Force }
    Remove-Item -LiteralPath $tempKey -Force -ErrorAction SilentlyContinue
}
