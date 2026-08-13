$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PidFile = Join-Path $ProjectRoot ".runtime\backend.pid"
if (-not (Test-Path -LiteralPath $PidFile)) {
    Write-Host "没有找到由 start-local.ps1 记录的后端进程。"
    exit 0
}

$BackendPid = [int](Get-Content -LiteralPath $PidFile -Encoding ascii)
$Process = Get-CimInstance Win32_Process -Filter "ProcessId = $BackendPid" -ErrorAction SilentlyContinue
if ($Process -and $Process.CommandLine -like "*backend.main:app*") {
    Stop-Process -Id $BackendPid
    Write-Host "本地后端已停止。"
}
else {
    Write-Host "PID 已失效或不属于 Resume Matcher，未停止任何进程。"
}
