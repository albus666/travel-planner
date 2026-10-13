param([int]$LocalPort=18100,[switch]$NoBrowser)
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$url="http://127.0.0.1:$LocalPort/ui/"
try {
    $existing=Invoke-WebRequest -Uri "http://127.0.0.1:$LocalPort/health" -TimeoutSec 2 -UseBasicParsing
    if ($existing.StatusCode -eq 200) {
        Write-Output "Existing tunnel: $url"
        if (-not $NoBrowser) { Start-Process $url }
        return
    }
} catch {}
$taskKey=Join-Path $env:TEMP ('travel-web-'+[guid]::NewGuid().ToString()+'.pem')
$taskSsh=$null
try {
    Copy-Item -LiteralPath (Join-Path $projectRoot 'key/cursor-pilot.pem') -Destination $taskKey
    $acl=New-Object System.Security.AccessControl.FileSecurity
    $identity=[System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $acl.SetOwner([System.Security.Principal.NTAccount]$identity)
    $acl.SetAccessRuleProtection($true,$false)
    $acl.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule($identity,'FullControl','Allow')))
    Set-Acl -LiteralPath $taskKey -AclObject $acl
    $sshArgs=@('-N','-o','BatchMode=yes','-o','ExitOnForwardFailure=yes','-o','StrictHostKeyChecking=yes',
               '-o','ServerAliveInterval=30','-i',('"'+$taskKey+'"'),'-L',"127.0.0.1:${LocalPort}:127.0.0.1:8100",'ubuntu@52.199.126.245')
    $taskSsh=Start-Process -FilePath 'C:\Windows\System32\OpenSSH\ssh.exe' -ArgumentList $sshArgs -WindowStyle Hidden -PassThru
    $connected=$false
    for ($attempt=0;$attempt -lt 20;$attempt++) {
        Start-Sleep -Milliseconds 500
        if ($taskSsh.HasExited) { throw 'SSH tunnel exited; check network and SSH access.' }
        try {
            $response=Invoke-WebRequest -Uri "http://127.0.0.1:$LocalPort/health" -TimeoutSec 2 -UseBasicParsing
            if ($response.StatusCode -eq 200) { $connected=$true;break }
        } catch {}
    }
    if (-not $connected) { throw 'Could not connect to server through SSH tunnel.' }
    Write-Output "Ready: $url"
    Write-Output "SSH PID: $($taskSsh.Id). To close: Stop-Process -Id $($taskSsh.Id)"
    if (-not $NoBrowser) { Start-Process $url }
} catch {
    if ($taskSsh -and -not $taskSsh.HasExited) { Stop-Process -Id $taskSsh.Id }
    throw
} finally {
    if (Test-Path -LiteralPath $taskKey) { Remove-Item -LiteralPath $taskKey -Force }
}
