# Local demo launcher for the one owner-approved Windows checkout.
# Never stops an existing process or sends a request to the bot.
$ErrorActionPreference = "Stop"

$expectedRoot = "C:\Cursor Projects\artgents-bot-active"
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
if (-not [string]::Equals($repoRoot.TrimEnd("\"), $expectedRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Wrong checkout: $repoRoot. Use $expectedRoot."
}

$gitRootOutput = & git -C $repoRoot rev-parse --show-toplevel
if ($LASTEXITCODE -ne 0) {
    throw "Git root check failed."
}
$gitRoot = [IO.Path]::GetFullPath(($gitRootOutput | Select-Object -Last 1).Trim())
if (-not [string]::Equals($gitRoot.TrimEnd("\"), $expectedRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Unexpected Git root: $gitRoot."
}

$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$envFile = Join-Path $repoRoot ".env"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Missing Python environment in $repoRoot."
}
if (-not (Test-Path -LiteralPath $envFile -PathType Leaf)) {
    throw "Missing local .env in $repoRoot."
}

$listeners = @(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object { $_.LocalPort -eq 9001 })
if ($listeners.Count -gt 0) {
    $pids = ($listeners | ForEach-Object { $_.OwningProcess } | Sort-Object -Unique) -join ", "
    throw "Port 9001 is already in use by PID $pids. Do not open the widget until you identify that process."
}

$branch = (& git -C $repoRoot branch --show-current | Select-Object -Last 1).Trim()
$head = (& git -C $repoRoot rev-parse --short HEAD | Select-Object -Last 1).Trim()
if ($LASTEXITCODE -ne 0) {
    throw "Git revision check failed."
}
Write-Host "Bot folder: $repoRoot"
Write-Host "Branch: $branch; commit: $head"
Write-Host "Widget: http://127.0.0.1:9001/static/widget-test.html"
Write-Host "Stop this bot with Ctrl+C."

Push-Location -LiteralPath $repoRoot
try {
    $logCheck = @'
from flask.cli import load_dotenv
load_dotenv()
from pathlib import Path
from core.d2_full_audit import full_audit_enabled, full_audit_path, full_audit
from logging_setup import LOG_FILE
paths = [Path(LOG_FILE)]
enabled = full_audit_enabled()
if enabled:
    paths.append(full_audit_path())
for path in paths:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8"):
        pass
print(f"Application log: {Path(LOG_FILE).resolve()}", flush=True)
print(f"Full dialogue audit: {'ON' if enabled else 'OFF'}; {full_audit_path().resolve()}", flush=True)
if enabled:
    full_audit("local_launcher_startup", trace_id="local-launcher")
'@
    $logCheck | & $python -
    if ($LASTEXITCODE -ne 0) {
        throw "Log write check failed. Bot was not started."
    }
    & $python -m flask --app app run --host 127.0.0.1 --port 9001 --no-reload
} finally {
    Pop-Location
}
