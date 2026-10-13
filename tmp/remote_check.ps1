param([string]$ScriptFile)
$ErrorActionPreference = 'Stop'
$taskKey = Join-Path $env:TEMP ('travel-planner-' + [guid]::NewGuid().ToString() + '.pem')
try {
    Copy-Item -LiteralPath "$PSScriptRoot\..\key\cursor-pilot.pem" -Destination $taskKey
    $taskAcl = New-Object System.Security.AccessControl.FileSecurity
    $taskIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $taskAcl.SetOwner([System.Security.Principal.NTAccount]$taskIdentity)
    $taskAcl.SetAccessRuleProtection($true, $false)
    $taskAcl.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule($taskIdentity, 'FullControl', 'Allow')))
    Set-Acl -LiteralPath $taskKey -AclObject $taskAcl
    $taskText = [IO.File]::ReadAllText((Resolve-Path $ScriptFile).Path).Replace("`r", '')
    $taskB64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($taskText))
    $taskB64 | & C:\Windows\System32\OpenSSH\ssh.exe -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=yes -i $taskKey ubuntu@52.199.126.245 "tr -d '\r' | base64 -d | bash"
    if ($LASTEXITCODE -ne 0) { throw "Remote exit: $LASTEXITCODE" }
} finally { if (Test-Path -LiteralPath $taskKey) { Remove-Item -LiteralPath $taskKey -Force } }
