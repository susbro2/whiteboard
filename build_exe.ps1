$ErrorActionPreference = 'Stop'

Write-Host "== Building standalone EXE with PyInstaller ==" -ForegroundColor Cyan

if (-not (Test-Path .venv)) {
  Write-Host "Creating virtual environment (.venv)..."
  python -m venv .venv
}

.\.venv\Scripts\python -m pip install -U pip
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\pip install pyinstaller

Write-Host "Running PyInstaller..." -ForegroundColor Yellow
.\.venv\Scripts\pyinstaller --noconfirm --onefile --windowed --name Whiteboard whiteboard.py

Write-Host "Done. Find the EXE at .\\dist\\Whiteboard.exe" -ForegroundColor Green
