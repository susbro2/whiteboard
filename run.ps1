Param(
  [switch]$Reinstall
)

$ErrorActionPreference = 'Stop'

Write-Host "== Whiteboard: preparing environment ==" -ForegroundColor Cyan

if ($Reinstall -and (Test-Path .venv)) {
  Remove-Item -Recurse -Force .venv
}

if (-not (Test-Path .venv)) {
  Write-Host "Creating virtual environment (.venv)..."
  python -m venv .venv
}

Write-Host "Upgrading pip..."
.\.venv\Scripts\python -m pip install -U pip

Write-Host "Installing requirements..."
.\.venv\Scripts\pip install -r requirements.txt

Write-Host "Launching app..." -ForegroundColor Green
.\.venv\Scripts\python whiteboard.py
