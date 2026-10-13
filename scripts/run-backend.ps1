# JurisScan-AI backend launcher (used by the local demo scheduled task).
# Runs the FastAPI app from the project virtualenv and logs to logs/backend.log.
# Safe to run manually in a terminal too:
#   powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run-backend.ps1

$root = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

Set-Location (Join-Path $root "backend")
$python = Join-Path $root ".venv\Scripts\python.exe"

& $python -m uvicorn main:app --host 127.0.0.1 --port 8000 *> (Join-Path $logDir "backend.log")
