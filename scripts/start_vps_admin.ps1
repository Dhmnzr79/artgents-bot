# Private SSH forwarding only. Does not start/restart/deploy anything on the VPS.
$ErrorActionPreference = "Stop"
$keyPath = Join-Path $env:USERPROFILE ".ssh\artgents_timeweb_ed25519"
if (-not (Test-Path -LiteralPath $keyPath -PathType Leaf)) { throw "SSH key not found: $keyPath" }
$null = Get-Command ssh -ErrorAction Stop
$listeners = @(Get-NetTCPConnection -State Listen -ErrorAction Stop | Where-Object { $_.LocalPort -eq 19100 })
if ($listeners.Count -gt 0) { throw "Port 19100 is busy. Identify the existing tunnel first; no process was stopped." }
Write-Host "VPS admin: http://127.0.0.1:19100/"
Write-Host "Keep this window open, then open that address in your browser."
Write-Host "Use your existing admin login and password in the browser."
Write-Host "Ctrl+C closes the tunnel. The bot and admin on the VPS keep running."
& ssh -N -T -o ExitOnForwardFailure=yes -o StrictHostKeyChecking=yes `
    -o ServerAliveInterval=30 -o ServerAliveCountMax=3 `
    -L "127.0.0.1:19100:127.0.0.1:9100" -i $keyPath deploy@5.129.195.70
if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 130) { throw "SSH tunnel closed with code $LASTEXITCODE." }
