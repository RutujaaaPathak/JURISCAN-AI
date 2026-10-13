# JurisScan-AI frontend launcher (used by the local demo scheduled task).
# Runs the Vite dev server and logs to logs/frontend.log.
# Safe to run manually in a terminal too:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-frontend.ps1

$root = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

Set-Location (Join-Path $root "frontend")

& npm.cmd run dev *> (Join-Path $logDir "frontend.log")
