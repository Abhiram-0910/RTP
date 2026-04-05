# ============================================================
#  MIRAI V2 — Permanent Startup Script
#  Starts: Docker (PostgreSQL) → FastAPI Backend → React Frontend
#  Run from: c:\Projects\RTP
# ============================================================

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ProjectRoot) { $ProjectRoot = "c:\Projects\RTP" }

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "   MIRAI V2 — Full Stack Startup" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ── Step 1: Docker (PostgreSQL) ───────────────────────────────
Write-Host "[1/3] Starting Docker containers..." -ForegroundColor Yellow
Set-Location $ProjectRoot
docker-compose up -d

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] docker-compose failed. Is Docker Desktop running?" -ForegroundColor Red
    pause
    exit 1
}

Start-Sleep -Seconds 3
Write-Host "       Postgres container is up." -ForegroundColor Green
Write-Host ""

# ── Step 2: FastAPI Backend ───────────────────────────────────
Write-Host "[2/3] Launching FastAPI backend (port 8000)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$ProjectRoot'; " +
    "`$env:PYTHONIOENCODING='utf-8'; " +
    "Write-Host '--- MIRAI Backend ---' -ForegroundColor Cyan; " +
    "python -m uvicorn backend.enhanced_main:app --reload --port 8000"
)
Start-Sleep -Seconds 6
Write-Host "       Backend window launched." -ForegroundColor Green
Write-Host ""

# ── Step 3: React Frontend ────────────────────────────────────
Write-Host "[3/3] Launching React frontend (port 5173)..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "Set-Location '$ProjectRoot\frontend-react'; " +
    "Write-Host '--- MIRAI Frontend ---' -ForegroundColor Cyan; " +
    "npm run dev"
)
Write-Host "       Frontend window launched." -ForegroundColor Green
Write-Host ""

# ── Summary ───────────────────────────────────────────────────
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  MIRAI V2 is starting up!" -ForegroundColor Green
Write-Host ""
Write-Host "  Backend  →  http://localhost:8000"       -ForegroundColor White
Write-Host "  API Docs →  http://localhost:8000/docs"  -ForegroundColor White
Write-Host "  Frontend →  http://localhost:5173"       -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Login: admin / mirai2024" -ForegroundColor DarkGray
Write-Host ""
Write-Host "  Press any key to close this launcher..." -ForegroundColor DarkGray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
