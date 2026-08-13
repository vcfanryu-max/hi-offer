param(
    [switch]$DebugMode
)

$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$PythonCandidates = @(
    (Join-Path $ProjectRoot ".venv\Scripts\python.exe"),
    (Join-Path (Split-Path $ProjectRoot -Parent) ".venv\Scripts\python.exe")
)
$Python = $PythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $Python) {
    throw "未找到 Python 虚拟环境。请先按 README 完成第一次安装。"
}
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw "未找到 npm。请先安装 Node.js 20.9 或更高版本。"
}

$RuntimeDir = Join-Path $ProjectRoot ".runtime"
New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
$PreviousDebug = $env:DEBUG
if ($DebugMode) {
    $env:DEBUG = "true"
}
$Backend = Start-Process -FilePath $Python `
    -ArgumentList @("-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory $ProjectRoot `
    -WindowStyle Hidden `
    -PassThru
$Backend.Id | Set-Content -LiteralPath (Join-Path $RuntimeDir "backend.pid") -Encoding ascii
if ($DebugMode) {
    Write-Host "Development Debug Mode: ON（不会记录或显示 API Key）"
}

try {
    Write-Host "Backend: http://127.0.0.1:8000"
    Write-Host "Web:     http://localhost:3000"
    Write-Host "按 Ctrl+C 停止。"
    & npm.cmd --prefix (Join-Path $ProjectRoot "frontend") run dev
}
finally {
    if ($Backend -and -not $Backend.HasExited) {
        Stop-Process -Id $Backend.Id -ErrorAction SilentlyContinue
    }
    $env:DEBUG = $PreviousDebug
}
