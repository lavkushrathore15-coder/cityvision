# CITYVISION AI - Windows PowerShell Environment Setup Script

Write-Host "=== Setting up CITYVISION AI Environment ===" -ForegroundColor Cyan

# 1. Check Python
$pythonVersion = python --version 2>&1
Write-Host "Detected: $pythonVersion" -ForegroundColor Green

# 2. Setup Virtual Environment
if (-not (Test-Path ".venv")) {
    Write-Host "Creating Python virtual environment in .venv..." -ForegroundColor Yellow
    python -m venv .venv
} else {
    Write-Host "Virtual environment .venv already exists." -ForegroundColor Green
}

# 3. Upgrade pip and install requirements
Write-Host "Installing Python requirements..." -ForegroundColor Yellow
& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt

# 4. Copy .env if not present
if (-not (Test-Path ".env")) {
    Write-Host "Creating .env from .env.example..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
}

# 5. Frontend setup
Write-Host "Setting up Frontend..." -ForegroundColor Cyan
Push-Location frontend
& "cmd.exe" /c npm install
Pop-Location

Write-Host "=== Setup Completed Successfully ===" -ForegroundColor Green
Write-Host "To run backend: .\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload"
Write-Host "To run frontend: cd frontend && npm run dev"
