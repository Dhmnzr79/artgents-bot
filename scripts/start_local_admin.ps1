# Read-only D2 admin. No bot/model/email requests, no automatic process termination.
$ErrorActionPreference = "Stop"
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$expectedRoot = "C:\Cursor Projects\artgents-bot-active"
if (-not [string]::Equals($repoRoot.TrimEnd("\"), $expectedRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Wrong checkout: $repoRoot. Use $expectedRoot."
}
$gitRoot = & git -C $repoRoot rev-parse --show-toplevel
if ($LASTEXITCODE -ne 0 -or -not [string]::Equals([IO.Path]::GetFullPath(($gitRoot | Select-Object -Last 1).Trim()), $repoRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Git root mismatch."
}
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) { throw "Missing local .venv." }
$listeners = @(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object { $_.LocalPort -eq 9100 })
if ($listeners.Count -gt 0) { throw "Port 9100 is busy. Identify the existing admin or SSH tunnel first." }
$previousEnv = $env:APP_ENV
$previousClients = $env:ALLOWED_CLIENTS
$previousDebug = $env:FLASK_DEBUG
Push-Location -LiteralPath $repoRoot
try {
    $env:APP_ENV = "local"
    $env:FLASK_DEBUG = "0"
    $env:ALLOWED_CLIENTS = "demo,demo_medical,nikadent"
    Write-Host "Admin: http://127.0.0.1:9100/"
    Write-Host "Artgents admin, read-only. Keep this terminal open. Stop with Ctrl+C."
    & $python -m flask --app admin_dashboard.app run --host 127.0.0.1 --port 9100 --no-reload --no-debugger
} finally {
    $env:APP_ENV = $previousEnv
    $env:ALLOWED_CLIENTS = $previousClients
    $env:FLASK_DEBUG = $previousDebug
    Pop-Location
}
